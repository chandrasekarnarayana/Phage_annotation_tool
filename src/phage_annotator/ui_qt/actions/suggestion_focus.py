"""Extracted method group 10 for ActionsMixin."""

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



class SuggestionFocusMixin:
    """Method group 10 extracted from ActionsMixin."""

    def _reject_current_uncertain_suggestion(self) -> None:
        """Handle the reject current uncertain suggestion helper flow."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]

        if self._interactive_learning_enabled():
            self._interactive_learning_model.add_example(current, accepted=False)

        cmd = RejectSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            if bool(getattr(self, "_timed_session_active", False)):
                self._timed_session_rejects = int(getattr(self, "_timed_session_rejects", 0)) + 1
            self._schedule_suggestion_decision_followup(refresh_table=False, run_qc=False)
    def _show_current_suggestion_patch(self) -> None:
        """Show a small snap-view patch around the current uncertain suggestion."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        suggestion = ranked[self._suggestion_cursor]
        if hasattr(self, "_set_right_dock_mode"):
            self._set_right_dock_mode("inspect")
        frame = self._slice_data(
            self.primary_image,
            t_override=int(suggestion.t),
            z_override=int(suggestion.z),
        )
        if frame is None:
            return
        half = 24
        y = int(round(float(suggestion.y)))
        x = int(round(float(suggestion.x)))
        y0 = max(0, y - half)
        x0 = max(0, x - half)
        y1 = min(frame.shape[0], y + half)
        x1 = min(frame.shape[1], x + half)
        patch = np.asarray(frame[y0:y1, x0:x1], dtype=np.float32)
        if patch.size == 0:
            return
        pmin = float(np.nanmin(patch))
        pmax = float(np.nanmax(patch))
        denom = (pmax - pmin) if pmax > pmin else 1.0
        norm = ((patch - pmin) / denom * 255.0).clip(0, 255).astype(np.uint8)
        rgb = np.stack([norm, norm, norm], axis=-1)
        h, w = rgb.shape[:2]
        image = QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(image.copy()).scaled(
            240,
            240,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.FastTransformation,
        )
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Suggestion Snap View")
        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel(dlg)
        label.setPixmap(pixmap)
        layout.addWidget(label)
        meta = QtWidgets.QLabel(
            f"score={float(suggestion.score):.3f} | id={suggestion.suggestion_id[:8]}",
            dlg,
        )
        layout.addWidget(meta)
        dlg.exec()
