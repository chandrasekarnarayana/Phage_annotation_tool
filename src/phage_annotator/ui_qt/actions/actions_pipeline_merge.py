"""Analysis, detection, scoring, and interactive learning actions."""

from __future__ import annotations

import csv
import gc
import logging
import pathlib
import time
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.utils.debug import debug_log

logger = logging.getLogger(__name__)

class ActionsPipelineMergeMixin:
    """Mixin for analysis, detection, calibration, and interactive learning actions."""

    # ── Modal consensus ────────────────────────────────────────────────────:
    """Mixin extracted from ActionsMixinAnalysis."""
    pass

    def _merge_modal_consensus(
        self,
        modality_candidates: dict[str, list[PointSuggestion]],
        *,
        k_required: int = 2,
    ) -> list[PointSuggestion]:
        """Merge per-modality candidates and require evidence in >= K modalities."""
        if not modality_candidates:
            return []
        modality_ids = list(modality_candidates.keys())
        seed_modality = "current_view" if "current_view" in modality_ids else modality_ids[0]
        seeds = list(modality_candidates.get(seed_modality, []))
        radius = float(getattr(self._suggestion_model, "min_distance_px", 6))
        r2 = radius * radius
        merged: list[PointSuggestion] = []
        for seed in seeds:
            bundle = {seed_modality: dict(seed.score_components)}
            votes = 1
            score_sum = float(seed.score)
            for modality_id, rows in modality_candidates.items():
                if modality_id == seed_modality:
                    continue
                hit = None
                for row in rows:
                    dx = float(row.x) - float(seed.x)
                    dy = float(row.y) - float(seed.y)
                    if dx * dx + dy * dy <= r2:
                        hit = row
                        break
                if hit is not None:
                    votes += 1
                    score_sum += float(hit.score)
                    bundle[modality_id] = dict(hit.score_components)
            if votes < int(max(1, k_required)):
                continue
            combined = PointSuggestion(
                image_id=seed.image_id,
                image_name=seed.image_name,
                t=seed.t,
                z=seed.z,
                y=seed.y,
                x=seed.x,
                score=float(score_sum / votes),
                label=seed.label,
                suggestion_id=seed.suggestion_id,
                source_model=seed.source_model,
                source_modality="consensus",
                supporting_modalities=sorted(bundle.keys()),
                cross_modality_consistency_score=float(votes / max(1, len(modality_candidates))),
                control_contradiction_score=0.0,
                scale_sigma=seed.scale_sigma,
                psf_radius=seed.psf_radius,
                roi_id=seed.roi_id,
                uncertainty_score=seed.uncertainty_score,
                uncertainty_reason=seed.uncertainty_reason,
                density_context=dict(getattr(seed, "density_context", {}) or {}),
                score_components=dict(seed.score_components),
                status=seed.status,
                meta=dict(seed.meta),
            )
            combined.meta["features"] = bundle
            combined.meta["consensus_votes"] = int(votes)
            combined.meta["supporting_modalities"] = list(combined.supporting_modalities)
            merged.append(combined)
        return merged

    def _rank_and_calibrate_suggestions(self, suggestions: list[PointSuggestion]) -> list[PointSuggestion]:
        """Apply lightweight ranker and calibrated p_accept if available."""
        if not suggestions:
            return suggestions
        annotation_space = str(getattr(self.controller.session_state, "annotation_space", "stack"))
        try:
            ranked = self.controller.score_suggestions_for_context(
                list(suggestions),
                annotation_space=annotation_space,
            )
        except Exception:
            ranked = list(suggestions)
        ranked.sort(
            key=lambda s: (
                -float(getattr(s, "score", 0.0)),
                int(getattr(s, "t", 0)),
                int(getattr(s, "z", 0)),
                float(getattr(s, "y", 0.0)),
                float(getattr(s, "x", 0.0)),
                str(getattr(s, "suggestion_id", "")),
            )
        )

        # Apply experimental sidecar predictions only when explicitly enabled.
        if self._interactive_learning_enabled() and self._interactive_learning_model.is_trained:
            predictions = self._interactive_learning_model.predict(ranked)
            for suggestion, prediction in zip(ranked, predictions):
                suggestion.meta["ml_prediction"] = prediction["accepted"]
                suggestion.meta["ml_confidence"] = prediction["confidence"]
                suggestion.meta["ml_uncertainty"] = prediction["uncertainty"]
                suggestion.meta["ml_method"] = prediction["method"]
        else:
            for suggestion in ranked:
                for key in ("ml_prediction", "ml_confidence", "ml_uncertainty", "ml_method"):
                    suggestion.meta.pop(key, None)

        return ranked

    def _enrich_suggestions_for_training(
        self, suggestions: list[PointSuggestion], image_data: np.ndarray
    ) -> None:
        """Attach microscopy context features and self-confirmation flags."""
        anns = list(self.annotations.get(self.primary_image.id, []))
        h, w = image_data.shape[:2]
        for suggestion in suggestions:
            y = float(suggestion.y)
            x = float(suggestion.x)
            min_border = min(x, y, float(w - 1) - x, float(h - 1) - y)
            nearest_truth = float("inf")
            nearest_any = float("inf")
            for kp in anns:
                if int(kp.t) not in (int(suggestion.t), -1):
                    continue
                if int(kp.z) not in (int(suggestion.z), -1):
                    continue
                dx = float(kp.x) - x
                dy = float(kp.y) - y
                dist = float((dx * dx + dy * dy) ** 0.5)
                nearest_any = min(nearest_any, dist)
                status = str(getattr(kp, "status", "active") or "active").strip().lower()
                source = str(getattr(kp, "source", "manual") or "manual").strip().lower()
                if status in {"rejected", "conflict"} or source in {"suggestion", "proposed"}:
                    continue
                nearest_truth = min(nearest_truth, dist)
            if not np.isfinite(nearest_truth):
                nearest_truth = float(max(h, w))
            if not np.isfinite(nearest_any):
                nearest_any = float(max(h, w))
            suggestion.meta["distance_to_nearest_accepted"] = float(nearest_truth)
            suggestion.meta["distance_to_nearest_truth_strict"] = float(nearest_truth)
            suggestion.meta["distance_to_any_annotation"] = float(nearest_any)
            suggestion.meta["border_proximity"] = float(max(0.0, min_border))
            suggestion.meta["derived_from_accepted_area"] = bool(
                nearest_truth <= float(getattr(suggestion, "psf_radius", 6.0))
            )

    def _note_annotation_edit(self, image_id: Optional[int] = None) -> None:
        """Record latest annotation-edit timestamp for staleness guardrails."""
        target_id = int(self.primary_image.id if image_id is None else image_id)
        by_image = getattr(self, "_annotation_edit_ts_by_image", None)
        if by_image is None:
            by_image = {}
            self._annotation_edit_ts_by_image = by_image
        by_image[target_id] = float(time.time())
