"""Suggestion workflow controller helpers.

The assist pipeline uses three controller-owned update layers:

Layer A: immediate local truth update
    Triggered synchronously after accept/reject/manual add/delete/edit.
    Only nearby suggestions are reclassified and de-duplicated. No full
    regeneration or retraining happens here.

Layer B: debounced local rescoring
    Triggered after a short edit debounce or after a small burst of edits.
    Only the visible/local context is rescored and resorted.

Layer C: retraining / recalibration
    Triggered only when enough feedback has accumulated or when explicitly
    forced. This stays deferred through the existing controller timer so the
    UI-facing edit path is not blocked.
"""

from __future__ import annotations

import collections
import math
import time
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np

from phage_annotator.analysis.suggestion_ranker import (
    LightweightSuggestionRanker,
    expected_calibration_error,
    feature_vector_from_suggestion,
)
from phage_annotator.annotation.core import Keypoint
from phage_annotator.session.signal_hub import emit_annotations_changed, emit_state_changed

if TYPE_CHECKING:
    from phage_annotator.core.annotation import PointSuggestion


class SessionControllerSuggestionsMixin:
    """Controller helpers for suggestion workflow, metrics, and training."""

    @staticmethod
    def _stable_suggestion_sort_key(suggestion: "PointSuggestion") -> tuple[float, int, int, float, float, str]:
        """Deterministic ordering for reproducible review queues."""
        return (
            -float(getattr(suggestion, "score", 0.0)),
            int(getattr(suggestion, "t", 0)),
            int(getattr(suggestion, "z", 0)),
            float(getattr(suggestion, "y", 0.0)),
            float(getattr(suggestion, "x", 0.0)),
            str(getattr(suggestion, "suggestion_id", "")),
        )

    def _normalize_local_context(
        self,
        context: dict[str, object] | None = None,
        changed_point: object | None = None,
    ) -> dict[str, object]:
        """Resolve local assist context from explicit input or current view state."""
        payload = dict(context or {})
        point = changed_point
        payload.setdefault("image_id", int(payload.get("image_id", getattr(point, "image_id", getattr(self.session_state, "active_primary_id", 0)))))
        payload.setdefault("t", int(payload.get("t", getattr(point, "t", getattr(self.view_state, "t", 0)))))
        payload.setdefault("z", int(payload.get("z", getattr(point, "z", getattr(self.view_state, "z", 0)))))
        payload.setdefault("annotation_space", str(payload.get("annotation_space", getattr(self.session_state, "annotation_space", "stack"))))
        payload.setdefault(
            "radius_px",
            float(payload.get("radius_px", getattr(self.session_state, "assist_local_update_radius_px", 24.0))),
        )
        payload.setdefault(
            "rescore_radius_px",
            float(
                payload.get(
                    "rescore_radius_px",
                    getattr(self.session_state, "assist_local_rescore_radius_px", 48.0),
                )
            ),
        )
        payload.setdefault(
            "roi_id",
            str(
                payload.get(
                    "roi_id",
                    getattr(point, "roi_id", getattr(point, "roi_name", "")),
                )
                or ""
            ),
        )
        crop_rect = payload.get("crop_rect", getattr(self.view_state, "crop_rect", None))
        if isinstance(crop_rect, (tuple, list)) and len(crop_rect) == 4:
            payload["crop_rect"] = tuple(float(v) for v in crop_rect)
        x_val = payload.get("x", getattr(point, "x", None))
        y_val = payload.get("y", getattr(point, "y", None))
        if x_val is not None:
            payload["x"] = float(x_val)
        if y_val is not None:
            payload["y"] = float(y_val)
        return payload

    def _row_matches_context(self, row: object, context: dict[str, object]) -> bool:
        """Return True when one row belongs to the requested local assist context."""
        ctx_t = int(context.get("t", -1))
        ctx_z = int(context.get("z", -1))
        row_t = int(getattr(row, "t", -1))
        row_z = int(getattr(row, "z", -1))
        if ctx_t != -1 and row_t not in (ctx_t, -1):
            return False
        if ctx_z != -1 and row_z not in (ctx_z, -1):
            return False
        ctx_roi = str(context.get("roi_id", "") or "")
        if ctx_roi:
            row_roi = str(
                getattr(row, "roi_id", getattr(row, "roi_name", ""))
                or dict(getattr(row, "meta", {}) or {}).get("roi", "")
            )
            if row_roi and row_roi != ctx_roi:
                return False
        return True

    def get_local_neighbors(self, point: object, radius: float) -> dict[str, list[object]]:
        """Return local neighboring annotations and suggestions around one point.

        This is used by Layer A for duplicate suppression/conflict checks and by
        Layer B for local density/spacing estimates. It is intentionally limited
        to one image and one T/Z neighborhood.
        """
        context = self._normalize_local_context(
            {
                "image_id": int(getattr(point, "image_id", getattr(self.session_state, "active_primary_id", 0))),
                "t": int(getattr(point, "t", getattr(self.view_state, "t", 0))),
                "z": int(getattr(point, "z", getattr(self.view_state, "z", 0))),
            },
            changed_point=point,
        )
        image_id = int(context["image_id"])
        x0 = float(context.get("x", getattr(point, "x", 0.0)))
        y0 = float(context.get("y", getattr(point, "y", 0.0)))
        limit = float(radius)

        def _near(rows: list[object]) -> list[object]:
            index = SessionControllerSuggestionsMixin._build_spatial_index(self, list(rows), cell_size=limit)
            out: list[object] = []
            for row in SessionControllerSuggestionsMixin._query_spatial_index(self, index, x=x0, y=y0, radius=limit):
                if not self._row_matches_context(row, context):
                    continue
                dist = self._suggestion_distance_px(
                    x0,
                    y0,
                    float(getattr(row, "x", 0.0)),
                    float(getattr(row, "y", 0.0)),
                )
                if dist <= limit:
                    out.append(row)
            return out

        history_rows = list(self.session_state.suggestion_history.get(image_id, []))
        return {
            "annotations": _near(list(self.session_state.annotations.get(image_id, []))),
            "pending": _near(list(self.session_state.suggestions.get(image_id, []))),
            "rejected_history": [
                row for row in _near(history_rows) if str(getattr(row, "status", "")).strip().lower() == "rejected"
            ],
        }

    def _suggestion_distance_px(self, x0: float, y0: float, x1: float, y1: float) -> float:
        """Return Euclidean distance in image-space pixels."""
        return float(math.hypot(float(x0) - float(x1), float(y0) - float(y1)))

    def _suggestion_relevant_annotations(self, image_id: int, suggestion: "PointSuggestion") -> list[Keypoint]:
        """Return committed annotations relevant to one suggestion's T/Z context."""
        rows = list(self.session_state.annotations.get(int(image_id), []))
        t_idx = int(getattr(suggestion, "t", -1))
        z_idx = int(getattr(suggestion, "z", -1))
        return [
            row
            for row in rows
            if int(getattr(row, "t", -2)) in (t_idx, -1)
            and int(getattr(row, "z", -2)) in (z_idx, -1)
        ]

    def _strict_truth_annotations(self, image_id: int, suggestion: "PointSuggestion") -> list[Keypoint]:
        """Return committed annotations suitable as strict truth for learning/confidence."""
        rows = SessionControllerSuggestionsMixin._suggestion_relevant_annotations(self, image_id, suggestion)
        strict = []
        for row in rows:
            status = str(getattr(row, "status", "active") or "active").strip().lower()
            source = str(getattr(row, "source", "manual") or "manual").strip().lower()
            if status in {"rejected", "conflict"}:
                continue
            if source in {"suggestion", "proposed"}:
                continue
            strict.append(row)
        return strict

    def _spatial_bucket_key(self, x: float, y: float, cell_size: float) -> tuple[int, int]:
        scale = max(1.0, float(cell_size))
        return (int(math.floor(float(x) / scale)), int(math.floor(float(y) / scale)))

    def _build_spatial_index(self, rows: list[object], *, cell_size: float) -> dict[tuple[int, int], list[object]]:
        buckets: dict[tuple[int, int], list[object]] = collections.defaultdict(list)
        for row in rows:
            key = SessionControllerSuggestionsMixin._spatial_bucket_key(
                self,
                float(getattr(row, "x", 0.0)),
                float(getattr(row, "y", 0.0)),
                cell_size,
            )
            buckets[key].append(row)
        return dict(buckets)

    def _query_spatial_index(
        self,
        index: dict[tuple[int, int], list[object]],
        *,
        x: float,
        y: float,
        radius: float,
    ) -> list[object]:
        if not index:
            return []
        cell = max(1.0, float(radius))
        cx, cy = SessionControllerSuggestionsMixin._spatial_bucket_key(self, float(x), float(y), cell)
        span = max(1, int(math.ceil(float(radius) / cell)))
        out: list[object] = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                out.extend(index.get((cx + dx, cy + dy), []))
        return out

    def _radius_scale_for_image(self, image_id: int) -> float:
        """Scale neighborhood radii using pixel size metadata when available."""
        image_state = dict(getattr(self.session_state, "image_states", {}) or {}).get(int(image_id))
        pixel_size_um = float(getattr(image_state, "pixel_size_um", 0.0) or 0.0) if image_state is not None else 0.0
        if pixel_size_um <= 0.0:
            return 1.0
        return max(0.75, min(1.5, pixel_size_um / 0.1))

    def _image_slice_for_context(self, image_id: int, *, t_idx: int, z_idx: int) -> np.ndarray | None:
        """Return a 2D slice from the loaded image array for local assist work."""
        if image_id < 0 or image_id >= len(getattr(self.session_state, "images", [])):
            return None
        image = self.session_state.images[image_id]
        array = getattr(image, "array", None)
        if array is None:
            return None
        arr = np.asarray(array)
        if arr.ndim == 2:
            return arr
        if arr.ndim == 3:
            if bool(getattr(image, "has_time", False)) and not bool(getattr(image, "has_z", False)):
                return np.asarray(arr[max(0, min(arr.shape[0] - 1, int(t_idx)))])
            if bool(getattr(image, "has_z", False)) and not bool(getattr(image, "has_time", False)):
                return np.asarray(arr[max(0, min(arr.shape[0] - 1, int(z_idx)))])
            return np.asarray(arr[0])
        if arr.ndim >= 4:
            t_clamped = max(0, min(arr.shape[0] - 1, int(t_idx)))
            z_clamped = max(0, min(arr.shape[1] - 1, int(z_idx)))
            return np.asarray(arr[t_clamped, z_clamped])
        return None

    def _local_generation_rows(
        self,
        image_id: int,
        *,
        context: dict[str, object],
    ) -> list["PointSuggestion"]:
        """Generate bounded visible-context proposals without global recomputation."""
        if not bool(getattr(self.session_state, "assist_local_generate_visible_candidates", False)):
            return []
        image_slice = self._image_slice_for_context(
            int(image_id),
            t_idx=int(context.get("t", 0)),
            z_idx=int(context.get("z", 0)),
        )
        if image_slice is None:
            return []
        crop_rect = context.get("crop_rect", ())
        roi_shape = "none"
        roi_rect = (0.0, 0.0, 0.0, 0.0)
        if isinstance(crop_rect, tuple) and len(crop_rect) == 4:
            roi_shape = "box"
            roi_rect = tuple(float(v) for v in crop_rect)
        model = getattr(self, "_visible_context_suggestion_model", None)
        if model is None or not hasattr(model, "predict"):
            return []
        try:
            rows = model.predict(
                image_slice,
                image_id=int(image_id),
                image_name=str(getattr(self.session_state.images[int(image_id)], "name", "")),
                t=int(context.get("t", 0)),
                z=int(context.get("z", 0)),
                label=str(getattr(self.session_state, "current_label", "phage")),
                strategy="raw",
                threshold_min_score=float(getattr(self.session_state, "suggestion_score_threshold", 0.0)),
                roi_id=str(context.get("roi_id", "") or ""),
                roi_shape=roi_shape,
                roi_rect=roi_rect,
            )
        except Exception:
            return []
        existing_ids = {
            str(getattr(row, "suggestion_id", ""))
            for row in self.session_state.suggestions.get(int(image_id), [])
        }
        return [row for row in rows if str(getattr(row, "suggestion_id", "")) not in existing_ids]

    def _classify_generated_suggestion(
        self,
        image_id: int,
        suggestion: "PointSuggestion",
        *,
        accepted_rows: list["PointSuggestion"] | None = None,
        exclude_suggestion_id: str = "",
    ) -> str:
        """Classify a generated candidate against committed truth and queued proposals."""
        strict_annotations = SessionControllerSuggestionsMixin._strict_truth_annotations(self, image_id, suggestion)
        all_annotations = SessionControllerSuggestionsMixin._suggestion_relevant_annotations(self, image_id, suggestion)
        pending_rows = list(self.session_state.suggestions.get(int(image_id), []))
        if accepted_rows:
            pending_rows.extend(list(accepted_rows))

        radius_scale = SessionControllerSuggestionsMixin._radius_scale_for_image(self, image_id)
        radius = max(3.0, min(8.0, float(getattr(suggestion, "psf_radius", 6.0)) * radius_scale))
        duplicate_radius = max(1.5, min(radius, float(getattr(suggestion, "psf_radius", 6.0)) * 0.4))
        same_label_min = float("inf")
        other_label_min = float("inf")
        any_annotation_min = float("inf")

        for row in strict_annotations:
            dist = SessionControllerSuggestionsMixin._suggestion_distance_px(
                self,
                float(getattr(suggestion, "x", 0.0)),
                float(getattr(suggestion, "y", 0.0)),
                float(getattr(row, "x", 0.0)),
                float(getattr(row, "y", 0.0)),
            )
            if str(getattr(row, "label", "")) == str(getattr(suggestion, "label", "")):
                same_label_min = min(same_label_min, dist)
            else:
                other_label_min = min(other_label_min, dist)

        for row in all_annotations:
            dist = SessionControllerSuggestionsMixin._suggestion_distance_px(
                self,
                float(getattr(suggestion, "x", 0.0)),
                float(getattr(suggestion, "y", 0.0)),
                float(getattr(row, "x", 0.0)),
                float(getattr(row, "y", 0.0)),
            )
            any_annotation_min = min(any_annotation_min, dist)

        for row in pending_rows:
            if exclude_suggestion_id and str(getattr(row, "suggestion_id", "")) == str(exclude_suggestion_id):
                continue
            dist = SessionControllerSuggestionsMixin._suggestion_distance_px(
                self,
                float(getattr(suggestion, "x", 0.0)),
                float(getattr(suggestion, "y", 0.0)),
                float(getattr(row, "x", 0.0)),
                float(getattr(row, "y", 0.0)),
            )
            if str(getattr(row, "label", "")) == str(getattr(suggestion, "label", "")):
                same_label_min = min(same_label_min, dist)
            else:
                other_label_min = min(other_label_min, dist)

        meta = dict(getattr(suggestion, "meta", {}) or {})
        meta["duplicate_radius_px"] = float(duplicate_radius)
        meta["merge_radius_px"] = float(radius)
        meta["nearest_same_label_px"] = None if same_label_min == float("inf") else float(same_label_min)
        meta["nearest_other_label_px"] = None if other_label_min == float("inf") else float(other_label_min)
        meta["distance_to_any_annotation"] = None if any_annotation_min == float("inf") else float(any_annotation_min)
        meta["radius_scale_px"] = float(radius_scale)

        if same_label_min <= duplicate_radius:
            candidate_class = "duplicate"
        elif other_label_min <= radius:
            candidate_class = "conflict"
        elif same_label_min <= radius:
            candidate_class = "near_existing"
        else:
            candidate_class = "new"

        meta["candidate_class"] = candidate_class
        meta["review_state"] = "needs_review" if candidate_class in {"near_existing", "conflict"} else "new"
        uncertainty_reasons = [str(meta.get("uncertainty_reason", "") or "").strip()]
        if candidate_class == "conflict":
            uncertainty_reasons.append("conflict_with_existing_annotation")
        elif candidate_class == "near_existing":
            uncertainty_reasons.append("near_existing_truth")
        meta["uncertainty_reason"] = ",".join(filter(None, dict.fromkeys(uncertainty_reasons)))
        if same_label_min != float("inf"):
            meta["distance_to_nearest_accepted"] = float(same_label_min)
            meta["distance_to_nearest_truth_strict"] = float(same_label_min)
        suggestion.meta = meta
        return str(candidate_class)

    def _update_local_suggestion_features(
        self,
        image_id: int,
        suggestion: "PointSuggestion",
        *,
        context: dict[str, object],
    ) -> None:
        """Refresh local spacing/density/reject features for one nearby suggestion."""
        radius = float(context.get("rescore_radius_px", getattr(self.session_state, "assist_local_rescore_radius_px", 48.0)))
        neighbors = self.get_local_neighbors(suggestion, radius)
        annotations = [
            row for row in neighbors["annotations"]
            if str(getattr(row, "annotation_id", "")) != str(getattr(suggestion, "suggestion_id", ""))
        ]
        rejected = [
            row for row in neighbors["rejected_history"]
            if str(getattr(row, "suggestion_id", "")) != str(getattr(suggestion, "suggestion_id", ""))
        ]
        same_label = [
            row for row in annotations
            if str(getattr(row, "label", "")) == str(getattr(suggestion, "label", ""))
        ]
        manual_same = [
            row
            for row in same_label
            if str(getattr(row, "source", "manual")).strip().lower().startswith("manual")
        ]
        nearest_same = min(
            (
                self._suggestion_distance_px(
                    float(getattr(suggestion, "x", 0.0)),
                    float(getattr(suggestion, "y", 0.0)),
                    float(getattr(row, "x", 0.0)),
                    float(getattr(row, "y", 0.0)),
                )
                for row in same_label
            ),
            default=radius,
        )
        nearest_reject = min(
            (
                self._suggestion_distance_px(
                    float(getattr(suggestion, "x", 0.0)),
                    float(getattr(suggestion, "y", 0.0)),
                    float(getattr(row, "x", 0.0)),
                    float(getattr(row, "y", 0.0)),
                )
                for row in rejected
            ),
            default=radius,
        )
        area = max(1.0, math.pi * (radius ** 2))
        local_density = float(len(same_label)) / area
        local_density_per_1k_px = float(local_density * 1000.0)
        spacing_consistency = float(
            1.0 - min(1.0, abs(nearest_same - radius * 0.5) / max(radius, 1.0))
        ) if same_label else 0.5
        meta = dict(getattr(suggestion, "meta", {}) or {})
        meta["distance_to_nearest_accepted"] = float(nearest_same)
        meta["distance_to_nearest_truth_strict"] = float(nearest_same)
        meta["distance_to_recent_reject"] = float(nearest_reject)
        meta["distance_to_any_annotation"] = float(
            min(
                (
                    self._suggestion_distance_px(
                        float(getattr(suggestion, "x", 0.0)),
                        float(getattr(suggestion, "y", 0.0)),
                        float(getattr(row, "x", 0.0)),
                        float(getattr(row, "y", 0.0)),
                    )
                    for row in annotations
                ),
                default=nearest_same,
            )
        )
        meta["local_neighbor_count"] = int(len(same_label))
        meta["local_manual_neighbor_count"] = int(len(manual_same))
        meta["local_density"] = float(local_density)
        meta["local_density_per_1k_px"] = float(local_density_per_1k_px)
        meta["spacing_consistency"] = float(spacing_consistency)
        density_context = dict(getattr(suggestion, "density_context", {}) or {})
        density_context.update(
            {
                "local_density": float(local_density),
                "local_density_per_1k_px": float(local_density_per_1k_px),
                "neighbor_count": int(len(same_label)),
                "manual_neighbor_count": int(len(manual_same)),
                "distance_to_nearest_truth": float(nearest_same),
                "distance_to_recent_reject": float(nearest_reject),
                "spacing_consistency": float(spacing_consistency),
                "search_area_px": float(area),
            }
        )
        suggestion.density_context = density_context
        candidate_class = str(meta.get("candidate_class", "") or "")
        uncertainty_reasons: list[str] = []
        if float(meta.get("generator_score", getattr(suggestion, "score", 0.0))) < 0.35:
            uncertainty_reasons.append("low_signal")
        if len(manual_same) > 0 and nearest_same <= max(3.0, radius * 0.5):
            uncertainty_reasons.append("near_existing_truth")
        if candidate_class == "conflict":
            uncertainty_reasons.append("conflict_with_existing_annotation")
        if local_density_per_1k_px > 0.75:
            uncertainty_reasons.append("dense_region_ambiguity")
        uncertainty_score = min(
            1.0,
            0.25 * (1.0 - min(1.0, float(meta.get("generator_score", getattr(suggestion, "score", 0.0)))))
            + 0.35 * min(1.0, local_density_per_1k_px)
            + 0.20 * (1.0 - float(spacing_consistency))
            + 0.20 * max(0.0, 1.0 - min(1.0, nearest_same / max(radius, 1.0))),
        )
        suggestion.uncertainty_score = float(max(float(getattr(suggestion, "uncertainty_score", 0.0) or 0.0), uncertainty_score))
        merged_reason = ",".join(
            filter(
                None,
                dict.fromkeys(
                    [str(getattr(suggestion, "uncertainty_reason", "") or "").strip()]
                    + uncertainty_reasons
                ),
            )
        )
        suggestion.uncertainty_reason = merged_reason
        meta["uncertainty_score"] = float(suggestion.uncertainty_score)
        meta["uncertainty_reason"] = merged_reason
        meta["density_context"] = dict(density_context)
        suggestion.meta = meta

    def _queue_local_rescore(self, context: dict[str, object]) -> None:
        """Debounce Layer B so fast edit bursts do not rescore on every click."""
        self._pending_local_rescore_context = dict(context)
        self._local_rescore_edit_count = int(getattr(self, "_local_rescore_edit_count", 0)) + 1
        threshold = int(getattr(self.session_state, "assist_local_rescore_edit_threshold", 4))
        timer = getattr(self, "_local_suggestion_rescore_timer", None)
        if self._local_rescore_edit_count >= threshold or timer is None:
            self._local_rescore_edit_count = 0
            self.local_rescore_visible_context(dict(context))
            return
        timer.setInterval(int(getattr(self.session_state, "assist_local_rescore_debounce_ms", 700)))
        timer.start()

    def _local_rescore_timer_fired(self) -> None:
        context = dict(getattr(self, "_pending_local_rescore_context", {}) or {})
        self._pending_local_rescore_context = None
        self._local_rescore_edit_count = 0
        if context:
            self.local_rescore_visible_context(context)

    def local_truth_update(self, context: dict[str, object] | None, changed_point: object) -> dict[str, int]:
        """Layer A: reclassify only nearby suggestions after a truth change.

        Triggered immediately after accept/reject/manual add/delete/edit.
        The implementation is intentionally local: only nearby pending
        suggestions are touched, and no full regeneration or retraining occurs.
        """
        resolved = self._normalize_local_context(context, changed_point)
        image_id = int(resolved["image_id"])
        radius = float(resolved.get("radius_px", getattr(self.session_state, "assist_local_update_radius_px", 24.0)))
        pending = self.session_state.suggestions.setdefault(image_id, [])
        history = self.session_state.suggestion_history.setdefault(image_id, [])
        nearby = [
            suggestion
            for suggestion in list(pending)
            if self._row_matches_context(suggestion, resolved)
            and self._suggestion_distance_px(
                float(resolved.get("x", getattr(changed_point, "x", 0.0))),
                float(resolved.get("y", getattr(changed_point, "y", 0.0))),
                float(getattr(suggestion, "x", 0.0)),
                float(getattr(suggestion, "y", 0.0)),
            )
            <= radius
        ]
        suppressed_ids: set[str] = set()
        summary = {
            "local_reclassified": 0,
            "local_duplicates_suppressed": 0,
            "local_conflicts": 0,
            "local_near_existing": 0,
        }
        for suggestion in nearby:
            candidate_class = self._classify_generated_suggestion(
                image_id,
                suggestion,
                exclude_suggestion_id=str(getattr(suggestion, "suggestion_id", "")),
            )
            self._update_local_suggestion_features(image_id, suggestion, context=resolved)
            summary["local_reclassified"] += 1
            if candidate_class == "duplicate":
                suggestion.status = "duplicate"
                suppressed_ids.add(str(getattr(suggestion, "suggestion_id", "")))
                summary["local_duplicates_suppressed"] += 1
            elif candidate_class == "conflict":
                suggestion.status = "proposed"
                summary["local_conflicts"] += 1
            elif candidate_class == "near_existing":
                suggestion.status = "proposed"
                summary["local_near_existing"] += 1
            else:
                suggestion.status = "proposed"
        if suppressed_ids:
            kept = []
            for suggestion in pending:
                sid = str(getattr(suggestion, "suggestion_id", ""))
                if sid in suppressed_ids:
                    if all(str(getattr(row, "suggestion_id", "")) != sid for row in history):
                        history.append(suggestion)
                    continue
                kept.append(suggestion)
            self.session_state.suggestions[image_id] = kept
            pending = kept
        if nearby:
            pending.sort(key=self._stable_suggestion_sort_key)
        self.session_state.last_local_suggestion_update_summary = dict(summary)
        emit_state_changed(self)
        return summary

    def local_rescore_visible_context(self, context: dict[str, object] | None) -> dict[str, int]:
        """Layer B: fast rescoring for the visible/local context only.

        This avoids global recomputation. It reuses the current ranker when
        available, updates local neighborhood features, and resorts the visible
        pending queue without retraining.
        """
        resolved = self._normalize_local_context(context)
        image_id = int(resolved["image_id"])
        radius = float(
            resolved.get(
                "rescore_radius_px",
                getattr(self.session_state, "assist_local_rescore_radius_px", 48.0),
            )
        )
        crop_rect = resolved.get("crop_rect", ())
        pending = self.session_state.suggestions.setdefault(image_id, [])
        visible: list["PointSuggestion"] = []
        for suggestion in pending:
            if not self._row_matches_context(suggestion, resolved):
                continue
            if crop_rect and isinstance(crop_rect, tuple) and len(crop_rect) == 4:
                x0, y0, w, h = crop_rect
                x1 = float(x0) + float(w)
                y1 = float(y0) + float(h)
                sx = float(getattr(suggestion, "x", 0.0))
                sy = float(getattr(suggestion, "y", 0.0))
                pad = float(radius)
                if sx < float(x0) - pad or sx > x1 + pad or sy < float(y0) - pad or sy > y1 + pad:
                    continue
            visible.append(suggestion)
        if not visible:
            return {"rescored_count": 0}

        generated_local = self._local_generation_rows(image_id, context=resolved)
        if generated_local:
            self.append_generated_suggestions(image_id, generated_local, sort_pending=False)
            pending = self.session_state.suggestions.setdefault(image_id, [])
            visible = [
                suggestion for suggestion in pending
                if self._row_matches_context(suggestion, resolved)
            ]

        rescored = self.score_suggestions_for_context(visible, annotation_space=str(resolved["annotation_space"]))
        for suggestion in rescored:
            self._update_local_suggestion_features(image_id, suggestion, context=resolved)
            meta = dict(getattr(suggestion, "meta", {}) or {})
            base_score = float(meta.get("generator_score", getattr(suggestion, "score", 0.0)))
            local_density = float(meta.get("local_density", 0.0))
            nearest_same = float(meta.get("distance_to_nearest_accepted", radius))
            nearest_reject = float(meta.get("distance_to_recent_reject", radius))
            confidence_available = bool(meta.get("confidence_available", False))
            if confidence_available:
                density_penalty = min(0.06, local_density * (math.pi * max(1.0, radius ** 2)) * 0.006)
                proximity_penalty = max(0.0, 1.0 - min(1.0, nearest_same / max(radius, 1.0))) * 0.05
                spacing_bonus = min(0.03, max(0.0, nearest_same / max(radius, 1.0)) * 0.03)
                reject_penalty = max(0.0, 1.0 - min(1.0, nearest_reject / max(radius, 1.0))) * 0.04
                adjustment = spacing_bonus - density_penalty - proximity_penalty - reject_penalty
                bounded_adjustment = max(-0.08, min(0.08, adjustment))
                anchor_score = float(meta.get("p_accept", getattr(suggestion, "score", base_score)))
            else:
                density_penalty = min(0.18, local_density * (math.pi * max(1.0, radius ** 2)) * 0.02)
                proximity_penalty = max(0.0, 1.0 - min(1.0, nearest_same / max(radius, 1.0))) * 0.28
                spacing_bonus = min(0.12, max(0.0, nearest_same / max(radius, 1.0)) * 0.12)
                reject_penalty = max(0.0, 1.0 - min(1.0, nearest_reject / max(radius, 1.0))) * 0.15
                bounded_adjustment = spacing_bonus - density_penalty - proximity_penalty - reject_penalty
                anchor_score = float(base_score)
            local_score = max(
                0.0,
                min(
                    1.0,
                    anchor_score + bounded_adjustment,
                ),
            )
            meta["local_rescore_score"] = float(local_score)
            meta["base_generator_score"] = float(base_score)
            meta["local_rescore_adjustment"] = float(bounded_adjustment)
            suggestion.meta = meta
            suggestion.score = float(local_score)
        pending.sort(key=self._stable_suggestion_sort_key)
        emit_state_changed(self)
        return {"rescored_count": int(len(rescored)), "generated_local_count": int(len(generated_local))}

    def retrain_or_recalibrate_if_ready(
        self,
        context: dict[str, object] | None,
        *,
        force: bool = False,
    ) -> bool:
        """Layer C: deferred retraining/calibration when enough feedback exists."""
        if force:
            trained = bool(self.train_suggestion_ranker_now())
            if trained:
                self.local_rescore_visible_context(context)
            return trained
        pending = int(getattr(self.session_state, "suggestion_training_pending", 0))
        min_pending = int(max(1, getattr(self.session_state, "suggestion_auto_retrain_min_labels", 25)))
        annotation_space = str(context.get("annotation_space", getattr(self.session_state, "annotation_space", "stack"))) if context else str(getattr(self.session_state, "annotation_space", "stack"))
        degradation = self._current_calibration_drift(annotation_space)
        if pending < min_pending and degradation < 0.10:
            return False
        timer = getattr(self, "_ranker_retrain_timer", None)
        if timer is None:
            self._maybe_retrain_suggestion_ranker(force=False)
            self.local_rescore_visible_context(context)
            return True
        timer.start()
        return True

    def set_suggestion_strategy_value(self, strategy: str) -> None:
        self.session_state.suggestion_strategy = str(strategy or "current_view")
        emit_state_changed(self)

    def set_suggestion_score_threshold_value(self, threshold: float) -> None:
        self.session_state.suggestion_score_threshold = float(threshold)
        emit_state_changed(self)

    def append_generated_suggestions(
        self,
        image_id: int,
        suggestions: list["PointSuggestion"],
        *,
        sort_pending: bool = True,
    ) -> dict[str, int]:
        image_key = int(image_id)
        rows = list(suggestions or [])
        pending = self.session_state.suggestions.setdefault(image_key, [])
        history = self.session_state.suggestion_history.setdefault(image_key, [])
        summary = {
            "input_count": int(len(rows)),
            "queued_count": 0,
            "duplicate_count": 0,
            "near_count": 0,
            "conflict_count": 0,
            "new_count": 0,
        }
        accepted_rows: list["PointSuggestion"] = []
        for suggestion in rows:
            candidate_class = SessionControllerSuggestionsMixin._classify_generated_suggestion(
                self,
                image_key,
                suggestion,
                accepted_rows=accepted_rows,
            )
            self._update_local_suggestion_features(
                image_key,
                suggestion,
                context=self._normalize_local_context(
                    {
                        "image_id": image_key,
                        "t": int(getattr(suggestion, "t", 0)),
                        "z": int(getattr(suggestion, "z", 0)),
                        "roi_id": getattr(suggestion, "roi_id", ""),
                    },
                    changed_point=suggestion,
                ),
            )
            if candidate_class == "duplicate":
                suggestion.status = "duplicate"
                history.append(suggestion)
                summary["duplicate_count"] += 1
                continue
            suggestion.status = "proposed"
            pending.append(suggestion)
            history.append(suggestion)
            accepted_rows.append(suggestion)
            summary["queued_count"] += 1
            if candidate_class == "conflict":
                summary["conflict_count"] += 1
            elif candidate_class == "near_existing":
                summary["near_count"] += 1
            else:
                summary["new_count"] += 1
        if sort_pending:
            pending.sort(key=self._stable_suggestion_sort_key)
        self.session_state.last_suggestion_generation_summary = dict(summary)
        if hasattr(self, "update_suggestion_metrics"):
            self.update_suggestion_metrics(
                classified_new=int(summary["new_count"]),
                classified_near_existing=int(summary["near_count"]),
                classified_conflict=int(summary["conflict_count"]),
                classified_duplicate=int(summary["duplicate_count"]),
            )
        if int(summary["conflict_count"]) and hasattr(self, "record_workflow_event"):
            self.record_workflow_event("merge_conflict", count=int(summary["conflict_count"]))
        emit_state_changed(self)
        return summary

    def sort_pending_suggestions(self, image_id: int) -> None:
        image_key = int(image_id)
        pending = self.session_state.suggestions.setdefault(image_key, [])
        pending.sort(key=self._stable_suggestion_sort_key)
        emit_state_changed(self)

    def get_suggestion_decision_context(self, image_id: int, suggestion_id: str) -> dict[str, object]:
        image_key = int(image_id)
        sid = str(suggestion_id or "").strip()
        pending = list(self.session_state.suggestions.get(image_key, []))
        history = list(self.session_state.suggestion_history.get(image_key, []))
        pending_idx = next((i for i, item in enumerate(pending) if str(getattr(item, "suggestion_id", "")) == sid), None)
        hist_idx = next((i for i, item in enumerate(history) if str(getattr(item, "suggestion_id", "")) == sid), None)
        pending_item = pending[pending_idx] if pending_idx is not None else None
        hist_item = history[hist_idx] if hist_idx is not None else None
        suggestion = pending_item if pending_item is not None else hist_item
        return {
            "pending": pending,
            "history": history,
            "pending_idx": pending_idx,
            "history_idx": hist_idx,
            "pending_item": pending_item,
            "history_item": hist_item,
            "suggestion": suggestion,
            "status": str(getattr(suggestion, "status", "proposed")).strip().lower() if suggestion is not None else "",
        }

    def get_visible_suggestions(self, image_id: int, *, t_index: int, z_index: int, min_score: float = 0.0) -> list["PointSuggestion"]:
        image_key = int(image_id)
        t_idx = int(t_index)
        z_idx = int(z_index)
        threshold = float(min_score)
        return [
            suggestion
            for suggestion in self.session_state.suggestions.get(image_key, [])
            if int(getattr(suggestion, "t", -2)) in (t_idx, -1)
            and int(getattr(suggestion, "z", -2)) in (z_idx, -1)
            and float(getattr(suggestion, "score", getattr(suggestion, "confidence", 0.0))) >= threshold
        ]

    def get_slice_suggestions(self, image_id: int, *, t_index: int, z_index: int) -> list["PointSuggestion"]:
        image_key = int(image_id)
        t_idx = int(t_index)
        z_idx = int(z_index)
        pending = [
            suggestion for suggestion in self.session_state.suggestions.get(image_key, [])
            if int(getattr(suggestion, "t", -2)) in (t_idx, -1) and int(getattr(suggestion, "z", -2)) in (z_idx, -1)
        ]
        history_rows = [
            suggestion for suggestion in self.session_state.suggestion_history.get(image_key, [])
            if int(getattr(suggestion, "t", -2)) in (t_idx, -1) and int(getattr(suggestion, "z", -2)) in (z_idx, -1)
        ]
        seen = {str(getattr(suggestion, "suggestion_id", "")) for suggestion in pending}
        merged = list(pending)
        for suggestion in history_rows:
            sid = str(getattr(suggestion, "suggestion_id", ""))
            if sid and sid in seen:
                continue
            merged.append(suggestion)
        return merged

    def remove_annotations_for_suggestion(self, image_id: int, suggestion_id: str) -> int:
        image_key = int(image_id)
        sid = str(suggestion_id or "")
        rows = list(self.session_state.annotations.get(image_key, []))
        kept: List[Keypoint] = []
        removed = 0
        for ann in rows:
            meta = dict(getattr(ann, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                removed += 1
                continue
            kept.append(ann)
        if removed:
            self.session_state.annotations[image_key] = kept
            self.set_dirty(True)
            emit_annotations_changed(self, image_id=image_key, change_type="removed")
        return int(removed)

    def append_annotation_from_suggestion(self, suggestion: "PointSuggestion") -> bool:
        image_id = int(getattr(suggestion, "image_id", -1))
        sid = str(getattr(suggestion, "suggestion_id", ""))
        existing = list(self.session_state.annotations.get(image_id, []))
        for ann in existing:
            meta = dict(getattr(ann, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                return False
        kp = Keypoint(
            image_id=image_id,
            image_name=str(getattr(suggestion, "image_name", "")),
            t=int(getattr(suggestion, "t", -1)),
            z=int(getattr(suggestion, "z", -1)),
            y=float(getattr(suggestion, "y", 0.0)),
            x=float(getattr(suggestion, "x", 0.0)),
            label=str(getattr(suggestion, "label", "")),
            source=f"suggested:{str(getattr(suggestion, 'source_model', 'model'))}",
            meta={
                "proposal_score": float(getattr(suggestion, "score", 0.0)),
                "score": float(getattr(suggestion, "score", 0.0)),
                "suggestion_id": sid,
                "source_model": str(getattr(suggestion, "source_model", "model")),
                "source_modality": str(getattr(suggestion, "source_modality", "raw")),
                "candidate_class": str(dict(getattr(suggestion, "meta", {}) or {}).get("candidate_class", "new")),
                "uncertainty_score": float(getattr(suggestion, "uncertainty_score", 0.0) or 0.0),
                "uncertainty_reason": str(getattr(suggestion, "uncertainty_reason", "") or ""),
                "supporting_modalities": list(getattr(suggestion, "supporting_modalities", []) or []),
                "cross_modality_consistency_score": getattr(suggestion, "cross_modality_consistency_score", None),
                "control_contradiction_score": getattr(suggestion, "control_contradiction_score", None),
                "density_context": dict(getattr(suggestion, "density_context", {}) or {}),
            },
        )
        kp.status = "accepted"
        kp.confidence = float(dict(getattr(suggestion, "meta", {}) or {}).get("p_accept", getattr(suggestion, "score", 0.0)))
        kp.roi_name = str(getattr(suggestion, "roi_id", "") or "")
        kp.notes = str(dict(getattr(suggestion, "meta", {}) or {}).get("notes", "") or "")
        kp.meta["supporting_modalities"] = list(getattr(suggestion, "supporting_modalities", []) or [])
        kp.meta["cross_modality_consistency_score"] = getattr(suggestion, "cross_modality_consistency_score", None)
        kp.meta["control_contradiction_score"] = getattr(suggestion, "control_contradiction_score", None)
        kp.meta["uncertainty_score"] = getattr(suggestion, "uncertainty_score", None)
        kp.meta["uncertainty_reason"] = str(getattr(suggestion, "uncertainty_reason", "") or "")
        kp.meta["density_context"] = dict(getattr(suggestion, "density_context", {}) or {})
        self.session_state.annotations.setdefault(image_id, []).append(kp)
        self.session_state.annotations_loaded[image_id] = True
        self.set_dirty(True)
        emit_annotations_changed(self, image_id=image_id, change_type="added")
        return True

    def update_suggestion_decision(self, image_id: int, suggestion_id: str, status: str) -> bool:
        image_key = int(image_id)
        sid = str(suggestion_id or "").strip()
        target = str(status or "").strip().lower()
        if not sid or target not in {"accepted", "rejected", "proposed"}:
            return False
        pending = self.session_state.suggestions.setdefault(image_key, [])
        history = self.session_state.suggestion_history.setdefault(image_key, [])
        pending_idx = next((i for i, s in enumerate(pending) if str(getattr(s, "suggestion_id", "")) == sid), None)
        hist_idx = next((i for i, s in enumerate(history) if str(getattr(s, "suggestion_id", "")) == sid), None)
        pending_item = pending[pending_idx] if pending_idx is not None else None
        hist_item = history[hist_idx] if hist_idx is not None else None
        suggestion = pending_item if pending_item is not None else hist_item
        if suggestion is None:
            return False
        if target == "accepted":
            if pending_idx is not None:
                pending.pop(pending_idx)
            if hist_idx is None:
                history.append(suggestion)
                hist_idx = len(history) - 1
            history[hist_idx].status = "accepted"
            self.append_annotation_from_suggestion(history[hist_idx])
        elif target == "rejected":
            if pending_idx is not None:
                pending.pop(pending_idx)
            if hist_idx is None:
                history.append(suggestion)
                hist_idx = len(history) - 1
            history[hist_idx].status = "rejected"
            self.remove_annotations_for_suggestion(image_key, sid)
        else:
            self.remove_annotations_for_suggestion(image_key, sid)
            if hist_idx is not None:
                proposal = history.pop(hist_idx)
            else:
                proposal = suggestion
                if pending_idx is not None:
                    pending.pop(pending_idx)
            proposal.status = "proposed"
            if all(str(getattr(s, "suggestion_id", "")) != sid for s in pending):
                pending.append(proposal)
                pending.sort(key=self._stable_suggestion_sort_key)
        self.set_dirty(True)
        emit_annotations_changed(self, image_id=image_key, change_type="modified")
        return True

    def get_suggestion_calibration_samples(self) -> list[tuple[float, int]]:
        history = getattr(self.session_state, "suggestion_history", {}) or {}
        rows: list[tuple[float, int]] = []
        for items in history.values():
            for row in items:
                status = str(getattr(row, "status", ""))
                if status not in ("accepted", "rejected"):
                    continue
                meta = dict(getattr(row, "meta", {}) or {})
                if not bool(meta.get("confidence_available", False)):
                    continue
                p_accept = meta.get("p_accept")
                if p_accept is None:
                    continue
                try:
                    rows.append((float(p_accept), 1 if status == "accepted" else 0))
                except Exception:
                    continue
        return rows

    def update_suggestion_metrics(self, *, generated: int = 0, accepted: int = 0, rejected: int = 0, correction_distance: Optional[float] = None, **extra_counters: float) -> None:
        metrics = self.session_state.suggestion_metrics
        metrics["generated"] = float(metrics.get("generated", 0.0) + int(generated))
        metrics["accepted"] = float(metrics.get("accepted", 0.0) + int(accepted))
        metrics["rejected"] = float(metrics.get("rejected", 0.0) + int(rejected))
        if correction_distance is not None:
            prev = float(metrics.get("mean_correction_distance", 0.0))
            accepted_total = max(1.0, float(metrics.get("accepted", 1.0)))
            metrics["mean_correction_distance"] = prev + ((float(correction_distance) - prev) / accepted_total)
        for key, value in extra_counters.items():
            metric_key = str(key)
            metrics[metric_key] = float(metrics.get(metric_key, 0.0) + float(value))
        if hasattr(self, "record_workflow_event"):
            if int(generated):
                self.record_workflow_event("suggestions_generated", count=int(generated))
            if int(accepted):
                self.record_workflow_event("suggestions_accepted", count=int(accepted))
            if int(rejected):
                self.record_workflow_event("suggestions_rejected", count=int(rejected))

    def restore_suggestion_ranker(self) -> None:
        payload = getattr(self.session_state, "suggestion_ranker_state", {})
        if isinstance(payload, dict) and payload:
            self.suggestion_ranker = LightweightSuggestionRanker.from_dict(payload)
            self.suggestion_rankers_by_space["stack"] = self.suggestion_ranker
            projection_payload = payload.get("projection_ranker")
            if isinstance(projection_payload, dict):
                self.suggestion_rankers_by_space["projection"] = LightweightSuggestionRanker.from_dict(projection_payload)
        else:
            self.suggestion_ranker = LightweightSuggestionRanker()
            self.suggestion_rankers_by_space["stack"] = self.suggestion_ranker
            self.suggestion_rankers_by_space["projection"] = LightweightSuggestionRanker()

    def save_suggestion_ranker_state(self) -> None:
        payload = self.suggestion_rankers_by_space["stack"].to_dict()
        payload["projection_ranker"] = self.suggestion_rankers_by_space["projection"].to_dict()
        self.session_state.suggestion_ranker_state = payload

    def _context_key(self, *, suggestion, annotation_space: str) -> str:
        dataset = str(getattr(suggestion, "image_name", "unknown"))
        modality = str(getattr(suggestion, "source_modality", "raw"))
        return f"{dataset}|{annotation_space}|{modality}"

    def _context_ready(self, annotation_space: str, context_key: str) -> tuple[bool, int]:
        breakdown = self.assist_need_breakdown(annotation_space=annotation_space, context_key=context_key)
        need = int(max(breakdown["need_total"], breakdown["need_pos"], breakdown["need_neg"], breakdown["need_context"]))
        return need <= 0, need

    def assist_need_breakdown(self, *, annotation_space: str, context_key: str) -> Dict[str, int]:
        rows = list(getattr(self.session_state, "suggestion_training_samples", []))
        total = len(rows)
        pos = sum(1 for r in rows if int(r.get("y", 0)) == 1)
        neg = max(0, total - pos)
        ctx = self.session_state.suggestion_context_stats.get(context_key, {"total": 0, "pos": 0, "neg": 0})
        need_total = max(0, int(self.session_state.assist_min_total_labels) - total)
        need_pos = max(0, int(self.session_state.assist_min_positive_labels) - pos)
        need_neg = max(0, int(self.session_state.assist_min_negative_labels) - neg)
        need_ctx = max(0, int(self.session_state.assist_min_labels_per_context) - int(ctx.get("total", 0)))
        return {"need_total": int(need_total), "need_pos": int(need_pos), "need_neg": int(need_neg), "need_context": int(need_ctx), "total": int(total), "pos": int(pos), "neg": int(neg), "context_total": int(ctx.get("total", 0))}

    def assist_status(self, *, annotation_space: str, context_key: str) -> tuple[str, str]:
        if not bool(self.session_state.suggestion_auto_retrain_enabled):
            return "heuristic", "Assist: Heuristic (auto-retrain disabled)"
        ready, need = self._context_ready(annotation_space, context_key)
        return ("learned", "Assist: Learned") if ready else ("unavailable", f"Assist: Unavailable (needs {need} more labels)")

    def score_suggestions_for_context(self, suggestions: List, *, annotation_space: str) -> List:
        if not suggestions:
            return suggestions
        context_key = self._context_key(suggestion=suggestions[0], annotation_space=annotation_space)
        ready, _ = self._context_ready(annotation_space, context_key)
        if not ready:
            for suggestion in suggestions:
                suggestion.meta["confidence_available"] = False
                suggestion.meta["confidence_note"] = "heuristic_only"
                suggestion.meta.setdefault("confidence", float(getattr(suggestion, "score", 0.0)))
                suggestion.meta.setdefault("uncertainty_reason", "heuristic_only")
            return suggestions
        ranker = self.suggestion_rankers_by_space.get(annotation_space, self.suggestion_rankers_by_space["stack"])
        ranked = ranker.apply_to_suggestions(suggestions)
        for suggestion in ranked:
            suggestion.meta["confidence_available"] = True
        ranked.sort(key=self._stable_suggestion_sort_key)
        return ranked

    def observe_suggestion_feedback(self, suggestion, accepted: bool) -> None:
        meta = dict(getattr(suggestion, "meta", {}) or {})
        if bool(meta.get("derived_from_accepted_area", False)) and not bool(meta.get("self_confirmation_marked", False)):
            self.update_suggestion_metrics(training_skipped_self_confirmation=1)
            return
        try:
            features = feature_vector_from_suggestion(suggestion)
        except Exception:
            return
        row = {
            "x": [float(v) for v in features.tolist()],
            "y": int(1 if accepted else 0),
            "timestamp": time.time(),
            "image_id": int(getattr(suggestion, "image_id", -1)),
            "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
            "strategy": str(getattr(suggestion, "source_modality", "raw")),
            "derived_from_accepted_area": bool(meta.get("derived_from_accepted_area", False)),
            "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            "context_key": self._context_key(suggestion=suggestion, annotation_space=str(getattr(self.session_state, "annotation_space", "stack"))),
        }
        self.session_state.suggestion_training_samples.append(row)
        ctx = self.session_state.suggestion_context_stats.setdefault(str(row["context_key"]), {"total": 0, "pos": 0, "neg": 0})
        ctx["total"] = int(ctx.get("total", 0) + 1)
        if int(row["y"]) == 1:
            ctx["pos"] = int(ctx.get("pos", 0) + 1)
        else:
            ctx["neg"] = int(ctx.get("neg", 0) + 1)
        self.session_state.suggestion_training_pending = int(self.session_state.suggestion_training_pending + 1)
        self.retrain_or_recalibrate_if_ready(
            {
                "image_id": int(getattr(suggestion, "image_id", -1)),
                "t": int(getattr(suggestion, "t", getattr(self.view_state, "t", 0))),
                "z": int(getattr(suggestion, "z", getattr(self.view_state, "z", 0))),
                "roi_id": getattr(suggestion, "roi_id", ""),
                "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            }
        )

    def observe_suggestion_correction(self, suggestion, *, dx: float, dy: float) -> None:
        try:
            features = feature_vector_from_suggestion(suggestion)
        except Exception:
            return
        row = {
            "x": [float(v) for v in features.tolist()],
            "y": 1,
            "timestamp": time.time(),
            "image_id": int(getattr(suggestion, "image_id", -1)),
            "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
            "strategy": str(getattr(suggestion, "source_modality", "raw")),
            "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            "context_key": self._context_key(suggestion=suggestion, annotation_space=str(getattr(self.session_state, "annotation_space", "stack"))),
            "correction_dx": float(dx),
            "correction_dy": float(dy),
            "correction_distance": float((float(dx) ** 2 + float(dy) ** 2) ** 0.5),
            "signal_type": "batch_offset",
        }
        self.session_state.suggestion_training_samples.append(row)
        ctx = self.session_state.suggestion_context_stats.setdefault(str(row["context_key"]), {"total": 0, "pos": 0, "neg": 0})
        ctx["total"] = int(ctx.get("total", 0) + 1)
        ctx["pos"] = int(ctx.get("pos", 0) + 1)
        self.session_state.suggestion_training_pending = int(self.session_state.suggestion_training_pending + 1)
        self.retrain_or_recalibrate_if_ready(
            {
                "image_id": int(getattr(suggestion, "image_id", -1)),
                "t": int(getattr(suggestion, "t", getattr(self.view_state, "t", 0))),
                "z": int(getattr(suggestion, "z", getattr(self.view_state, "z", 0))),
                "roi_id": getattr(suggestion, "roi_id", ""),
                "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            }
        )

    def _retrain_timer_fired(self) -> None:
        self._maybe_retrain_suggestion_ranker()

    def _maybe_retrain_suggestion_ranker(self, force: bool = False) -> None:
        if (not force) and (not bool(self.session_state.suggestion_auto_retrain_enabled)):
            return
        pending = int(getattr(self.session_state, "suggestion_training_pending", 0))
        min_pending = int(max(1, self.session_state.suggestion_auto_retrain_min_labels))
        if not force and pending < min_pending:
            return
        rows = list(getattr(self.session_state, "suggestion_training_samples", []))
        if len(rows) < 20:
            return
        trained_any = False
        last_samples = 0
        last_pos = 0
        last_neg = 0
        for space in ("stack", "projection"):
            xs = []
            ys = []
            for row in rows[-4000:]:
                if str(row.get("annotation_space", "stack")) != space:
                    continue
                x = row.get("x")
                y = row.get("y")
                if not isinstance(x, list) or len(x) == 0:
                    continue
                xs.append([float(v) for v in x])
                ys.append(float(y))
            if len(xs) < 20 or len(set(ys)) < 2:
                continue
            x_arr = np.asarray(xs, dtype=np.float64)
            y_arr = np.asarray(ys, dtype=np.float64)
            pos = max(1, int(np.sum(y_arr >= 0.5)))
            neg = max(1, int(np.sum(y_arr < 0.5)))
            pos_w = float(0.5 * y_arr.shape[0] / pos)
            neg_w = float(0.5 * y_arr.shape[0] / neg)
            sample_weight = np.where(y_arr >= 0.5, pos_w, neg_w)
            self.suggestion_rankers_by_space[space].fit(x_arr, y_arr, sample_weight=sample_weight, epochs=(120 if not force else 240))
            self.session_state.suggestion_metrics["calibration_ece"] = float(getattr(self.suggestion_rankers_by_space[space], "calibration_ece", 0.0))
            self.session_state.suggestion_metrics["calibration_brier"] = float(getattr(self.suggestion_rankers_by_space[space], "calibration_brier", 0.0))
            trained_any = True
            last_samples = int(len(xs))
            last_pos = pos
            last_neg = neg
            if space == "stack":
                self.suggestion_ranker = self.suggestion_rankers_by_space["stack"]
        if not trained_any:
            return
        self.session_state.suggestion_training_pending = 0
        self.save_suggestion_ranker_state()
        self.append_audit_event("suggestion_ranker_trained", samples=last_samples, class_balance={"positive": last_pos, "negative": last_neg}, trained_samples=int(self.suggestion_ranker.trained_samples))

    def _current_calibration_drift(self, annotation_space: str) -> float:
        """Estimate calibration drift from recent feedback without blocking the UI."""
        rows = [
            row
            for row in list(getattr(self.session_state, "suggestion_training_samples", []))[-256:]
            if str(row.get("annotation_space", "stack")) == str(annotation_space)
            and isinstance(row.get("x"), list)
        ]
        if len(rows) < 20:
            return 0.0
        ranker = self.suggestion_rankers_by_space.get(str(annotation_space), self.suggestion_rankers_by_space["stack"])
        x_arr = np.asarray([[float(v) for v in row["x"]] for row in rows], dtype=np.float64)
        y_arr = np.asarray([float(row.get("y", 0)) for row in rows], dtype=np.float64)
        probs = ranker.predict_p_accept(x_arr)
        ece = float(expected_calibration_error(probs, y_arr, n_bins=8))
        self.session_state.suggestion_metrics["calibration_drift"] = ece
        return ece

    def train_suggestion_ranker_now(self) -> bool:
        before = int(max(getattr(self.suggestion_rankers_by_space["stack"], "trained_samples", 0), getattr(self.suggestion_rankers_by_space["projection"], "trained_samples", 0)))
        self._maybe_retrain_suggestion_ranker(force=True)
        after = int(max(getattr(self.suggestion_rankers_by_space["stack"], "trained_samples", 0), getattr(self.suggestion_rankers_by_space["projection"], "trained_samples", 0)))
        return after >= before and after > 0
