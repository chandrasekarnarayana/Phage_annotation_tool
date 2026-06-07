"""Extracted method group 5 for ActionsMixin."""

from __future__ import annotations

import gc
import json
import logging
import os
import pathlib
import time
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.assist_context import AssistContextMixin
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.actions.assist_strategy import AssistStrategyMixin
from phage_annotator.ui_qt.actions.standard_workspace import WorkspaceActionsMixin
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.actions.dock_actions import DockActionsMixin
from phage_annotator.ui_qt.actions.export_actions import ExportActionsMixin
from phage_annotator.ui_qt.actions.navigation_actions import NavigationActionsMixin
from phage_annotator.ui_qt.actions.qc_actions import QCActionsMixin
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.io.metadata.reader import MetadataBundle


logger = logging.getLogger(__name__)


from phage_annotator.ui_qt.actions.suggestion_generation_actions import (
    _set_generation_progress,
    accept_high_confidence_suggestions,
    accept_visible_suggestions,
    preview_batch_accept_dialog,
    reject_visible_suggestions,
    suggest_points_current_image,
    suggest_points_current_slice,
)
from phage_annotator.ui_qt.actions.suggestion_generation_impl import (
    accept_suggestions_in_roi,
    clear_suggestions_current_image,
)



class SuggestionGenerationMixin:
    """Method group 5 extracted from ActionsMixin."""

    def _gating_strategy_candidates(
        self,
        *,
        image,
        t_idx: int,
        z_idx: int,
        strategy: str,
        label: str,
    ) -> list[PointSuggestion]:
        """Generate candidates using generalized modality evidence strategies."""
        model = getattr(self, "_suggestion_model", None)
        if model is None or not hasattr(model, "predict"):
            return []
        frames = self._available_modality_frames(image, t_idx, z_idx)
        if not frames:
            return []
        strategy_key = str(strategy or "current_view").lower()
        generation_space = str(
            getattr(self.controller.session_state, "generation_space", "stack")
        ).strip().lower()
        roi_id = "active_roi" if self.roi_shape != "none" else None
        roi_shape = str(self.roi_shape)
        roi_rect = tuple(self.roi_rect)

        def _predict_one(modality_id: str, frame: np.ndarray) -> list[PointSuggestion]:
            """Predict one for the current workflow."""
            rows = model.predict(
                frame,
                image_id=image.id,
                image_name=image.name,
                t=t_idx,
                z=z_idx,
                label=label,
                strategy="raw",
                roi_id=roi_id,
                roi_shape=roi_shape,
                roi_rect=roi_rect,
            )
            for row in rows:
                row.source_modality = modality_id
                row.meta.setdefault("features", {})
                row.meta["features"][modality_id] = dict(row.score_components)
            return self._filter_suggestions_to_active_roi(rows)

        # Projection-space generation changes the evidence basis without
        # changing the annotation truth path. It stays deterministic for
        # identical inputs and avoids hidden count-based suppression.
        if (
            generation_space == "projection"
            and "_full_stack_t" in frames
            and hasattr(model, "predict_from_stack")
        ):
            try:
                rows = model.predict_from_stack(
                    frames["_full_stack_t"],
                    image_id=image.id,
                    image_name=image.name,
                    label=label,
                    z_frame=z_idx,
                    strategy="raw",
                    roi_id=roi_id,
                    roi_shape=roi_shape,
                    roi_rect=roi_rect,
                    refine_from_stack=False,
                )
                for row in rows:
                    row.source_modality = f"{strategy_key}_projection"
                    row.meta.setdefault("features", {})
                    row.meta["generation_space"] = "projection"
                    row.meta["features"][row.source_modality] = dict(row.score_components)
                return self._filter_suggestions_to_active_roi(rows)
            except Exception:
                pass

        # Stack-aware detection: uses full temporal/z stack for enhanced SNR
        if strategy_key in ("stack_aware", "stack-aware"):
            full_stack = frames.get("_full_stack_t")
            if full_stack is not None and hasattr(model, "predict_from_stack"):
                try:
                    rows = model.predict_from_stack(
                        full_stack,
                        image_id=image.id,
                        image_name=image.name,
                        label=label,
                        z_frame=z_idx,
                        strategy="raw",
                        roi_id=roi_id,
                        roi_shape=roi_shape,
                        roi_rect=roi_rect,
                        refine_from_stack=False,  # Optimized: mean projection is optimal
                    )
                    for row in rows:
                        row.source_modality = "stack_aware"
                        row.meta.setdefault("features", {})
                        row.meta["features"]["stack_aware"] = dict(row.score_components)
                    return self._filter_suggestions_to_active_roi(rows)
                except Exception as exc:
                    import sys
                    print(f"Warning: stack-aware prediction failed: {exc}", file=sys.stderr)
            # Fall back to raw if stack unavailable
            return _predict_one("raw", frames["raw"])

        if strategy_key in frames:
            return _predict_one(strategy_key, frames[strategy_key])

        if strategy_key in ("evidence_consensus", "consensus"):
            use_modalities = [mid for mid in ("raw", "corrected", "mean_projection") if mid in frames]
            modality_candidates = {mid: _predict_one(mid, frames[mid]) for mid in use_modalities}
            return self._filter_suggestions_to_active_roi(
                self._merge_modal_consensus(modality_candidates, k_required=2)
            )

        if strategy_key in ("evidence_contradiction",):
            base_ids = [mid for mid in ("raw", "corrected", "mean_projection") if mid in frames]
            modality_candidates = {mid: _predict_one(mid, frames[mid]) for mid in base_ids}
            seeds = self._merge_modal_consensus(modality_candidates, k_required=1)
            cfg = getattr(self, "_suggestion_rule_config", None)
            if cfg is None:
                return self._filter_suggestions_to_active_roi(seeds)
            rule = getattr(cfg, "semantic_rules", {}).get(strategy_key)
            if rule is None:
                return self._filter_suggestions_to_active_roi(seeds)
            for suggestion in seeds:
                features = dict(suggestion.meta.get("features", {}))
                penalty = 0.0
                support_modalities = set(getattr(suggestion, "supporting_modalities", []) or [])
                for modality_id, threshold in dict(rule.positive_modalities).items():
                    peak = float(dict(features.get(modality_id, {})).get("peak", -np.inf))
                    if peak < float(threshold):
                        penalty += 0.15
                    else:
                        support_modalities.add(str(modality_id))
                contradiction = 0.0
                for modality_id, threshold in dict(rule.negative_modalities).items():
                    peak = float(dict(features.get(modality_id, {})).get("peak", 0.0))
                    if peak > float(threshold):
                        contradiction = max(
                            contradiction,
                            min(1.0, (peak - float(threshold)) / max(abs(float(threshold)), 1.0)),
                        )
                        support_modalities.add(str(modality_id))
                suggestion.supporting_modalities = sorted(support_modalities)
                suggestion.control_contradiction_score = float(max(getattr(suggestion, "control_contradiction_score", 0.0) or 0.0, contradiction))
                suggestion.cross_modality_consistency_score = float(max(0.0, 1.0 - penalty - contradiction))
                suggestion.score_components["control_contradiction_score"] = float(suggestion.control_contradiction_score)
                suggestion.score_components["cross_modality_consistency_score"] = float(suggestion.cross_modality_consistency_score)
                suggestion.meta["supporting_modalities"] = list(suggestion.supporting_modalities)
                suggestion.meta["control_contradiction_score"] = float(suggestion.control_contradiction_score)
                suggestion.meta["cross_modality_consistency_score"] = float(suggestion.cross_modality_consistency_score)
                if contradiction > 0.0:
                    suggestion.uncertainty_reason = ",".join(
                        filter(
                            None,
                            dict.fromkeys(
                                [str(getattr(suggestion, "uncertainty_reason", "") or "").strip(), "control_contradiction"]
                            ),
                        )
                    )
                    suggestion.meta["uncertainty_reason"] = suggestion.uncertainty_reason
                    suggestion.uncertainty_score = float(max(float(getattr(suggestion, "uncertainty_score", 0.0) or 0.0), min(1.0, contradiction)))
                    suggestion.meta["uncertainty_score"] = float(suggestion.uncertainty_score)
            return self._filter_suggestions_to_active_roi(seeds)

        # Legacy channel strategies still supported via existing gating.
        seed_id = "current_view" if "current_view" in frames else next(iter(frames.keys()))
        seeded = _predict_one(seed_id, frames[seed_id])
        if strategy_key.startswith("channel_"):
            return self._filter_suggestions_to_active_roi(
                self._apply_cross_channel_gating(
                    seeded,
                    strategy=strategy_key,
                    t_idx=t_idx,
                    z_idx=z_idx,
                )
            )
        return self._filter_suggestions_to_active_roi(seeded)
    def _load_suggestion_rule_config_dialog(self) -> None:
        """Load JSON/YAML experiment rule config for cross-channel gating."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Suggestion Rule Config",
            str(pathlib.Path.cwd()),
            "Config Files (*.json *.yaml *.yml)",
        )
        if not path:
            return
        try:
            self._suggestion_rule_config = load_suggestion_rule_config(pathlib.Path(path))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Rule config load failed", str(exc))
            return
        self._status_success(
            f"Loaded suggestion rule config: {pathlib.Path(path).name}.",
            timeout_ms=3000,
            source="standard.suggestion_rules",
        )
