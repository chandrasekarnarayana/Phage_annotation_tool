"""Extracted method group 14 for ActionsMixin."""

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



class ActionsAnnotationReviewMixin:
    """Method group 14 extracted from ActionsMixin."""

    def _set_selected_review_state(self, state: str) -> None:
        """Set review state on selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._status_info(
                "Select one or more annotations first.",
                timeout_ms=2500,
                source="standard.annotation_selection",
            )
            return
        updated = 0
        now_ts = time.time()
        for kp in selected:
            new_meta = dict(kp.meta)
            new_meta["review_state"] = state
            new_meta["reviewer"] = self.controller.session_state.current_user
            new_meta["reviewed_at"] = now_ts
            replacement = type(kp)(
                image_id=kp.image_id,
                image_name=kp.image_name,
                t=kp.t,
                z=kp.z,
                y=kp.y,
                x=kp.x,
                label=kp.label,
                annotation_id=kp.annotation_id,
                image_key=kp.image_key,
                source=kp.source,
                meta=new_meta,
                modality_idx=kp.modality_idx,
            )
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                updated += 1
        if updated:
            self.controller.append_audit_event(
                "review_state_updated", state=state, count=updated
            )
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Updated review state for {updated} annotation(s).",
            timeout_ms=3000,
            source="standard.review_state",
        )
    def _assign_selected_annotations_dialog(self) -> None:
        """Set assignee for selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._status_info(
                "Select one or more annotations first.",
                timeout_ms=2500,
                source="standard.annotation_selection",
            )
            return
        assignee, ok = QtWidgets.QInputDialog.getText(
            self,
            "Assign Selected Annotations",
            "Assignee:",
            text=self.controller.session_state.current_user,
        )
        if not ok:
            return
        assignee = assignee.strip()
        updated = 0
        for kp in selected:
            new_meta = dict(kp.meta)
            new_meta["assignee"] = assignee
            replacement = type(kp)(
                image_id=kp.image_id,
                image_name=kp.image_name,
                t=kp.t,
                z=kp.z,
                y=kp.y,
                x=kp.x,
                label=kp.label,
                annotation_id=kp.annotation_id,
                image_key=kp.image_key,
                source=kp.source,
                meta=new_meta,
                modality_idx=kp.modality_idx,
            )
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                updated += 1
        if updated:
            self.controller.append_audit_event(
                "assignee_updated", assignee=assignee, count=updated
            )
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Assigned {updated} annotation(s) to '{assignee}'.",
            timeout_ms=3000,
            source="standard.assignee",
        )
    def _set_current_user_dialog(self) -> None:
        """Set current local user identity for review/audit actions."""
        current = self.controller.session_state.current_user
        user, ok = QtWidgets.QInputDialog.getText(self, "Set Current User", "User:", text=current)
        if not ok:
            return
        user = user.strip() or "local_user"
        self.controller.set_current_user_value(user)
        self.controller.append_audit_event("current_user_changed", user=user)
        self._status_info(
            f"Current user set to '{user}'.",
            timeout_ms=2500,
            source="standard.current_user",
        )
    def _set_review_queue_filter(self, mode: str) -> None:
        """Switch annotation table queue filter mode."""
        self._review_queue_filter = str(mode)
        action_map = {
            "all": getattr(self, "queue_all_act", None),
            "my_queue": getattr(self, "queue_my_act", None),
            "needs_review": getattr(self, "queue_needs_review_act", None),
            "blocked_qc": getattr(self, "queue_blocked_qc_act", None),
        }
        for key, action in action_map.items():
            if action is None:
                continue
            action.blockSignals(True)
            action.setChecked(key == self._review_queue_filter)
            action.blockSignals(False)
        self._refresh_table()
        self._refresh_review_queue_panel()
        self._request_ui_refresh("standard-actions")
        self._status_info(
            f"Review queue: {self._review_queue_filter}.",
            timeout_ms=2500,
            source="standard.review_queue",
        )
    def _show_profile_dialog(self) -> None:
        """Open a dialog showing line profiles (vertical, horizontal, diagonals) raw vs corrected."""
        if self.primary_image.array is None:
            return
        data = self._apply_crop(self._slice_data(self.primary_image))
        if data.ndim > 2:
            data = np.mean(data, axis=-1)
        h, w = data.shape[:2]
        cy, cx = h // 2, w // 2
        vertical = data[:, cx]
        horizontal = data[cy, :]
        diag1 = np.diag(data)
        diag2 = np.diag(np.fliplr(data))

        def _correct(arr: np.ndarray) -> np.ndarray:
            """Handle the correct helper flow."""
            if self.illum_corr_chk.isChecked():
                arr = arr - arr.min()
            if arr.max() > 0:
                arr = arr / arr.max()
            return arr

        fig, axes = plt.subplots(2, 2, figsize=(10, 6))
        axes = axes.ravel()
        for ax, arr, title in [
            (axes[0], vertical, "Vertical"),
            (axes[1], horizontal, "Horizontal"),
            (axes[2], diag1, "Diag TL-BR"),
            (axes[3], diag2, "Diag TR-BL"),
        ]:
            ax.plot(arr, label="raw")
            ax.plot(_correct(arr), label="corrected")
            ax.set_title(title)
            ax.legend()
            ax.set_xlabel("Pixel")
            ax.set_ylabel("Intensity")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Line profiles")
        layout = QtWidgets.QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.resize(900, 600)
        dlg.show()
        dlg.exec()
