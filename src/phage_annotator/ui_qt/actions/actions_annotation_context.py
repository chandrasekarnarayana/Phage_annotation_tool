"""Extracted method group 1 for ActionsMixin."""

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



class ActionsAnnotationContextMixin:
    """Method group 1 extracted from ActionsMixin."""

    def _current_annotation_write_context(self) -> tuple[str, str]:
        """Return the current write context as (context_key, panel_key)."""
        context = (
            dict(self.controller.current_annotation_context() or {})
            if hasattr(self.controller, "current_annotation_context")
            else {}
        )
        return (
            str(context.get("context_key", "img:0|panel:frame|space:stack")),
            str(context.get("panel_key", getattr(self, "annotate_target", "frame"))),
        )
    def _mark_annotation_context_changed(self, reason: str) -> None:
        """Mark write context as changed and requiring explicit confirmation."""
        self._annotation_write_context_pending = True
        self._annotation_context_change_reason = str(reason or "context changed")
        self._annotation_write_context_pending_value = self._current_annotation_write_context()
        self._update_status()
    def _is_annotation_context_guard_pending(self) -> bool:
        """True when write actions should request confirmation before commit."""
        pending = bool(getattr(self, "_annotation_write_context_pending", False))
        confirmed = getattr(self, "_annotation_write_context_confirmed", None)
        current = self._current_annotation_write_context()
        if pending and isinstance(confirmed, tuple) and tuple(confirmed) == current:
            self._annotation_write_context_pending = False
            self._annotation_context_change_reason = ""
            self._annotation_write_context_pending_value = None
            pending = False
        if pending:
            return True
        return confirmed is not None and tuple(confirmed) != current
    def _ensure_annotation_write_context_confirmed(self, action_label: str) -> bool:
        """Prompt before write if annotation context changed since last confirmation."""
        current = self._current_annotation_write_context()
        confirmed = getattr(self, "_annotation_write_context_confirmed", None)
        needs_confirm = self._is_annotation_context_guard_pending()
        if not needs_confirm:
            self._annotation_write_context_confirmed = current
            return True

        reason = str(
            getattr(self, "_annotation_context_change_reason", "")
            or "annotation context changed"
        )
        prev_txt = (
            f"{confirmed[0]} / {confirmed[1]}"
            if isinstance(confirmed, tuple) and len(confirmed) == 2
            else "unknown"
        )
        cur_txt = f"{current[0]} / {current[1]}"
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Confirm Annotation Write Context")
        msg.setText(f"{action_label} will write annotations in a new context.")
        msg.setInformativeText(
            f"Previous confirmed context: {prev_txt}\n"
            f"Current context: {cur_txt}\n"
            f"Reason: {reason}\n\n"
            "Proceed with this write?"
        )
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel
        )
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        if msg.exec() != QtWidgets.QMessageBox.Yes:
            self._status_warning(
                "Write cancelled: context confirmation required.",
                timeout_ms=3000,
                source="standard.write_context",
            )
            return False
        self._annotation_write_context_confirmed = current
        self._annotation_write_context_pending = False
        self._annotation_context_change_reason = ""
        self._annotation_write_context_pending_value = None
        self._update_status()
        return True
    def _open_files(self) -> None:
        """Open files for the current workflow."""
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_files(self)
        if paths:
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[GUI] Open files from main import ({len(paths)} selected)",
                    category="GUI",
                )
            self.recorder.record("open_files", {"count": len(paths)})
            self._open_files_from_paths(paths)
    def _open_folder(self) -> None:
        """Open folder for the current workflow."""
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_folder(self)
        if paths:
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[GUI] Open folder from main import ({len(paths)} files discovered)",
                    category="GUI",
                )
            self.recorder.record("open_folder", {"count": len(paths)})
            # Load metadata for all files in the background with progress + cancel (P1.3)
            files = list(paths)

            def _worker(progress, cancel):
                """Handle the worker helper flow."""
                from phage_annotator.ui_qt.utils.image_io import read_metadata

                metas = []
                total = len(files)
                for idx, p in enumerate(files):
                    if cancel.is_cancelled():
                        return None
                    meta = read_metadata(p)
                    metas.append(meta)
                    progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
                return metas

            def _on_result(result):
                """Handle the on result helper flow."""
                if not result:
                    return
                new_images = result
                if hasattr(self, "_append_log"):
                    self._append_log(
                        f"[GUI] Folder load completed ({len(new_images)} image(s) added)",
                        category="GUI",
                    )
                # Add images and update UI on GUI thread
                self.controller.add_images(new_images)
                for meta in new_images:
                    self.roi_manager.rois_by_image[meta.id] = []
                # Build annotation index (lightweight) and update availability
                try:
                    self.controller.build_annotation_index(files[0].parent)
                    if hasattr(self, "_append_log"):
                        self._append_log(
                            f"[Annotations] Indexed annotation files in {files[0].parent}",
                            category="Annotations",
                        )
                except Exception:
                    logger.warning("Failed to build annotation index after opening folder", exc_info=True)
                self._refresh_annotation_availability()
                self._refresh_roi_manager()
                self._refresh_metadata_dock(self.primary_image.id)
                self._request_ui_refresh("standard-actions")
                self._maybe_autoload_annotations(self.primary_image.id)

            self.jobs.submit(
                _worker,
                name="Open folder",
                on_result=_on_result,
                timeout_sec=300.0,
                retries=2,
                retry_delay_sec=1.0,
                priority="interactive",
                replace_key="open-folder",
            )
    def _reset_confirmations(self) -> None:
        """Re-enable all confirmation dialogs."""
        self._settings.setValue("confirmApplyDisplayMapping", True)
        self._settings.setValue("confirmApplyThreshold", True)
        self._settings.setValue("confirmClearROI", True)
        self._settings.setValue("confirmDeleteAnnotations", True)
        self._settings.setValue("confirmOverwriteFile", True)
        QtWidgets.QMessageBox.information(
            self,
            "Confirmations Reset",
            "All confirmation prompts have been re-enabled.\n\nYou will now be asked before:\n• Applying display settings\n• Applying threshold\n• Clearing ROI\n• Deleting annotations\n• Overwriting files"
        )
    def _load_annotations_current(self) -> None:
        """Load annotations current for the current workflow."""
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            force_image_id=self.primary_image.id,
            context_panel_key=str(getattr(self, "annotate_target", "frame")),
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._request_ui_refresh("standard-actions", table=True)
        self._refresh_table()
    def _load_annotations_multi(self) -> None:
        """Load annotations multi for the current workflow."""
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            context_panel_key=str(getattr(self, "annotate_target", "frame")),
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._request_ui_refresh("standard-actions", table=True)
        self._refresh_table()
