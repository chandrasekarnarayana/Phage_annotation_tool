"""Extracted method group 6 for SessionControllerSuggestionsMixin."""

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



class SuggestionTrainingMixin:
    """Method group 6 extracted from SessionControllerSuggestionsMixin."""

    def score_suggestions_for_context(self, suggestions: List, *, annotation_space: str) -> List:
        """Score suggestions for context for the current workflow."""
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
        """Run the observe suggestion feedback workflow."""
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
        """Run the observe suggestion correction workflow."""
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
        """Handle the retrain timer fired helper flow."""
        self._maybe_retrain_suggestion_ranker()
    def _maybe_retrain_suggestion_ranker(self, force: bool = False) -> None:
        """Handle the maybe retrain suggestion ranker helper flow."""
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
        """Train suggestion ranker now for the current workflow."""
        before = int(max(getattr(self.suggestion_rankers_by_space["stack"], "trained_samples", 0), getattr(self.suggestion_rankers_by_space["projection"], "trained_samples", 0)))
        self._maybe_retrain_suggestion_ranker(force=True)
        after = int(max(getattr(self.suggestion_rankers_by_space["stack"], "trained_samples", 0), getattr(self.suggestion_rankers_by_space["projection"], "trained_samples", 0)))
        return after >= before and after > 0
