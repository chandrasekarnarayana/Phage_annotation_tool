"""Menu and dialog actions for the GUI."""

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

class ActionsBulkAcceptMixin:
    """Extracted from standard.py."""

    def _suggest_points_current_slice(self) -> None:
        """Generate model suggestions for the current slice."""
        assist_generation.suggest_points_current_slice(self)

    def _suggest_points_current_image(self) -> None:
        """Generate suggestions for all T/Z slices in the active image."""
        assist_generation.suggest_points_current_image(self)

    def _accept_visible_suggestions(self) -> None:
        """Accept visible suggestions as one reviewed batch command."""
        assist_generation.accept_visible_suggestions(self)

    def _accept_high_confidence_suggestions(self) -> None:
        """Accept all visible green suggestions (calibrated p_accept >= 0.75)."""
        assist_generation.accept_high_confidence_suggestions(self)

    def _preview_batch_accept_dialog(
        self,
        *,
        candidates: List[PointSuggestion],
        title: str,
        description: str,
        stale_override_required: bool = False,
    ) -> Optional[List[str]]:
        """Show checkbox preview dialog and return selected suggestion IDs.

        Returns None when user cancels.
        """
        return assist_generation.preview_batch_accept_dialog(
            self,
            candidates=candidates,
            title=title,
            description=description,
            stale_override_required=stale_override_required,
        )

    def _reject_visible_suggestions(self) -> None:
        """Reject all visible suggestions via undoable commands."""
        assist_generation.reject_visible_suggestions(self)

    def _accept_suggestions_in_roi(self) -> None:
        """Accept visible suggestions that are currently inside ROI."""
        assist_generation.accept_suggestions_in_roi(self)

    def _clear_suggestions_current_image(self) -> None:
        """Clear all pending suggestions for active image."""
        assist_generation.clear_suggestions_current_image(self)

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
