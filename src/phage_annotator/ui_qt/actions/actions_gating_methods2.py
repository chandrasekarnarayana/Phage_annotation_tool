"""Method group 2 split from actions_gating.py."""

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

class _ActionsGatingMixinMethods2:
    """Methods split from ActionsGatingMixin."""

    def _apply_cross_channel_gating(
        self, suggestions: list[PointSuggestion], *, strategy: str, t_idx: int, z_idx: int
    ) -> list[PointSuggestion]:
        """Filter proposals by per-channel peak/low constraints."""
        strategy_key = str(strategy or "raw").lower()
        if strategy_key not in (
            "channel_a_only",
            "channel_b_only",
            "channel_a_peak_b_low",
            "channel_b_peak_a_low",
        ):
            return suggestions
        image = self.primary_image
        if int(getattr(image, "channel_count", 1)) < 2:
            return suggestions
        if not hasattr(self, "_get_channel_stack"):
            return suggestions
        ch0 = self._get_channel_stack(image, 0)
        ch1 = self._get_channel_stack(image, 1)
        if ch0 is None or ch1 is None:
            return suggestions
        frame0 = ch0[t_idx, z_idx]
        frame1 = ch1[t_idx, z_idx]
        high0 = float(np.nanquantile(frame0, 0.85))
        low0 = float(np.nanquantile(frame0, 0.35))
        high1 = float(np.nanquantile(frame1, 0.85))
        low1 = float(np.nanquantile(frame1, 0.35))
        rule = None
        cfg = getattr(self, "_suggestion_rule_config", None)
        if cfg is not None:
            channels = getattr(cfg, "channels", {})
            if "A" in channels:
                ch = channels["A"]
                high0 = float(ch.peak_min if ch.peak_min is not None else high0)
                low0 = float(ch.background_max)
            if "B" in channels:
                ch = channels["B"]
                high1 = float(ch.peak_min if ch.peak_min is not None else high1)
                low1 = float(ch.background_max)
            semantic_rules = getattr(cfg, "semantic_rules", {})
            rule = semantic_rules.get(strategy_key)
        filtered: list[PointSuggestion] = []
        for suggestion in suggestions:
            y = int(round(float(suggestion.y)))
            x = int(round(float(suggestion.x)))
            if y < 0 or x < 0 or y >= frame0.shape[0] or x >= frame0.shape[1]:
                continue
            v0 = float(frame0[y, x])
            v1 = float(frame1[y, x])
            keep = True
            if strategy_key == "channel_a_only":
                keep = v0 >= v1
            elif strategy_key == "channel_b_only":
                keep = v1 >= v0
            elif strategy_key == "channel_a_peak_b_low":
                keep = (v0 >= high0) and (v1 <= low1)
            elif strategy_key == "channel_b_peak_a_low":
                keep = (v1 >= high1) and (v0 <= low0)
            if keep and rule is not None:
                if rule.channel_a_peak_gt is not None and v0 <= float(rule.channel_a_peak_gt):
                    keep = False
                if rule.channel_b_peak_gt is not None and v1 <= float(rule.channel_b_peak_gt):
                    keep = False
                if rule.channel_a_lt is not None and v0 >= float(rule.channel_a_lt):
                    keep = False
                if rule.channel_b_lt is not None and v1 >= float(rule.channel_b_lt):
                    keep = False
                if rule.roi_id is not None and str(getattr(suggestion, "roi_id", "")) != str(
                    rule.roi_id
                ):
                    keep = False
            if keep:
                filtered.append(suggestion)
        return filtered
