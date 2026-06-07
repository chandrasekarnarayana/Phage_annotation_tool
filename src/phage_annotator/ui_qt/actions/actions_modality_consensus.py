"""Extracted method group 4 for ActionsMixin."""

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



class ActionsModalityConsensusMixin:
    """Method group 4 extracted from ActionsMixin."""

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
