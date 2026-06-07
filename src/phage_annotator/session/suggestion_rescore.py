"""Extracted method group 3 for SessionControllerSuggestionsMixin."""

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



class SuggestionRescoreMixin:
    """Method group 3 extracted from SessionControllerSuggestionsMixin."""

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
        """Handle the local rescore timer fired helper flow."""
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
