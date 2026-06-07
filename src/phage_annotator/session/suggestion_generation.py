"""Extracted method group 2 for SessionControllerSuggestionsMixin."""

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
from phage_annotator.session.suggestion_spatial import SuggestionSpatialMixin

if TYPE_CHECKING:
    from phage_annotator.core.annotation import PointSuggestion



class SuggestionGenerationMixin:
    """Method group 2 extracted from SessionControllerSuggestionsMixin."""

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
        strict_annotations = SuggestionSpatialMixin._strict_truth_annotations(self, image_id, suggestion)
        all_annotations = SuggestionSpatialMixin._suggestion_relevant_annotations(self, image_id, suggestion)
        pending_rows = list(self.session_state.suggestions.get(int(image_id), []))
        if accepted_rows:
            pending_rows.extend(list(accepted_rows))

        radius_scale = SuggestionSpatialMixin._radius_scale_for_image(self, image_id)
        radius = max(3.0, min(8.0, float(getattr(suggestion, "psf_radius", 6.0)) * radius_scale))
        duplicate_radius = max(1.5, min(radius, float(getattr(suggestion, "psf_radius", 6.0)) * 0.4))
        same_label_min = float("inf")
        other_label_min = float("inf")
        any_annotation_min = float("inf")

        for row in strict_annotations:
            dist = self._suggestion_distance_px(
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
            dist = self._suggestion_distance_px(
                float(getattr(suggestion, "x", 0.0)),
                float(getattr(suggestion, "y", 0.0)),
                float(getattr(row, "x", 0.0)),
                float(getattr(row, "y", 0.0)),
            )
            any_annotation_min = min(any_annotation_min, dist)

        for row in pending_rows:
            if exclude_suggestion_id and str(getattr(row, "suggestion_id", "")) == str(exclude_suggestion_id):
                continue
            dist = self._suggestion_distance_px(
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
