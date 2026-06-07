"""Extracted method group 1 for SessionControllerSuggestionsMixin."""

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



class SuggestionSpatialMixin:
    """Method group 1 extracted from SessionControllerSuggestionsMixin."""

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
            """Handle the near helper flow."""
            index = SuggestionSpatialMixin._build_spatial_index(self, list(rows), cell_size=limit)
            out: list[object] = []
            for row in SuggestionSpatialMixin._query_spatial_index(self, index, x=x0, y=y0, radius=limit):
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
        rows = SuggestionSpatialMixin._suggestion_relevant_annotations(self, image_id, suggestion)
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
        """Handle the spatial bucket key helper flow."""
        scale = max(1.0, float(cell_size))
        return (int(math.floor(float(x) / scale)), int(math.floor(float(y) / scale)))
    def _build_spatial_index(self, rows: list[object], *, cell_size: float) -> dict[tuple[int, int], list[object]]:
        """Build spatial index for the current workflow."""
        buckets: dict[tuple[int, int], list[object]] = collections.defaultdict(list)
        for row in rows:
            key = SuggestionSpatialMixin._spatial_bucket_key(
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
        """Handle the query spatial index helper flow."""
        if not index:
            return []
        cell = max(1.0, float(radius))
        cx, cy = SuggestionSpatialMixin._spatial_bucket_key(self, float(x), float(y), cell)
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
