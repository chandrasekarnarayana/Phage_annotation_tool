"""Extracted method group 4 for SessionControllerSuggestionsMixin."""

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
from phage_annotator.session.suggestion_generation import SuggestionGenerationMixin
from phage_annotator.session.signal_hub import emit_annotations_changed, emit_state_changed

if TYPE_CHECKING:
    from phage_annotator.core.annotation import PointSuggestion



class SuggestionPipelineMixin:
    """Method group 4 extracted from SessionControllerSuggestionsMixin."""

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
        """Set suggestion strategy value for the current workflow."""
        self.session_state.suggestion_strategy = str(strategy or "current_view")
        emit_state_changed(self)
    def set_suggestion_score_threshold_value(self, threshold: float) -> None:
        """Set suggestion score threshold value for the current workflow."""
        self.session_state.suggestion_score_threshold = float(threshold)
        emit_state_changed(self)
    def append_generated_suggestions(
        self,
        image_id: int,
        suggestions: list["PointSuggestion"],
        *,
        sort_pending: bool = True,
    ) -> dict[str, int]:
        """Append generated suggestions for the current workflow."""
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
            candidate_class = SuggestionGenerationMixin._classify_generated_suggestion(
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
        """Sort pending suggestions for the current workflow."""
        image_key = int(image_id)
        pending = self.session_state.suggestions.setdefault(image_key, [])
        pending.sort(key=self._stable_suggestion_sort_key)
        emit_state_changed(self)
    def get_suggestion_decision_context(self, image_id: int, suggestion_id: str) -> dict[str, object]:
        """Return suggestion decision context for the current workflow."""
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
        """Return visible suggestions for the current workflow."""
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
