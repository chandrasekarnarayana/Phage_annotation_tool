"""Extracted method group 2 for ActionsMixin."""

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



class ActionsFileOpenMixin:
    """Method group 2 extracted from ActionsMixin."""

    def _load_annotations_all(self) -> None:
        """Load annotations all for the current workflow."""
        targets = []
        for img in self.images:
            if self.controller.annotation_entries_for_image(img.id):
                targets.append(img.id)
        if not targets:
            QtWidgets.QMessageBox.information(
                self, "No annotations", "No indexed annotations were found."
            )
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None

        def _worker(progress, cancel):
            """Handle the worker helper flow."""
            results = {}
            imports = []
            total = len(targets)
            for idx, image_id in enumerate(targets):
                if cancel.is_cancelled():
                    return None
                paths = [
                    entry.path for entry in self.controller.annotation_entries_for_image(image_id)
                ]
                points, import_entries = self.controller._parse_annotations_from_paths(
                    paths,
                    image_id=image_id,
                    pixel_size_nm=pixel_size_nm,
                    force_image_id=image_id,
                )
                results[image_id] = points
                imports.extend(import_entries)
                progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
            return (results, imports)

        def _on_result(result):
            """Handle the on result helper flow."""
            if not result:
                return
            results, imports = result
            self.controller._record_annotation_imports(imports)
            for image_id, points in results.items():
                if self.controller.annotations_are_loaded(image_id):
                    self.controller.merge_annotations(image_id, points)
                else:
                    self.controller.replace_annotations(image_id, points)
            meta = None
            for target_id, entry in imports:
                if target_id == self.primary_image.id:
                    meta = entry.get("meta")
                    if isinstance(meta, dict) and meta:
                        break
            if meta:
                self._handle_annotation_metadata(self.primary_image.id, meta)
            self._mark_dirty()
            emit_annotations_changed(self.controller, image_id=self.primary_image.id)
            self._request_ui_refresh("standard-actions", table=True)
            self._refresh_table()

        self.jobs.submit(
            _worker,
            name="Load all annotations",
            on_result=_on_result,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
            priority="interactive",
            replace_key="load-all-annotations",
        )
    def _reload_annotations_current(self) -> None:
        """Handle the reload annotations current helper flow."""
        image_id = self.primary_image.id
        if not self.controller.annotation_entries_for_image(image_id):
            self._load_annotations_current()
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=True, pixel_size_nm=pixel_size_nm)
    def _toggle_left_pane(self) -> None:
        """Toggle left pane for the current workflow."""
        if self.dock_sidebar is None:
            return
        self._set_panel_visibility("sidebar")
    def _toggle_settings_pane(self) -> None:
        """Toggle settings pane for the current workflow."""
        dock = getattr(self, "dock_advanced_settings", None)
        if dock is None:
            return
        visible = bool(dock.isVisible())
        if hasattr(self, "_toggle_right_sidebar_panel"):
            if visible:
                self._toggle_right_sidebar_panel("advanced_settings")
            else:
                self.open_panel("advanced_settings", reason="menu:advanced_settings")
                try:
                    dock.raise_()
                except Exception:
                    pass
        else:
            dock.setVisible(not visible)
    def _on_link_zoom_menu(self) -> None:
        """Handle the on link zoom menu helper flow."""
        self.link_zoom = self.link_zoom_act.isChecked()
        if not self.link_zoom:
            # reset last linked to avoid forcing 0-1 ranges
            self._last_zoom_linked = None
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
        if getattr(self, "view_sync", None) is not None:
            self._apply_view_sync_selection()
        self._request_ui_refresh("standard-actions")
    def _show_about(self) -> None:
        """Show about for the current workflow."""
        QtWidgets.QMessageBox.information(
            self,
            "About Phage Annotator",
            "Phage Annotator\nMatplotlib + Qt GUI for microscopy keypoint annotation.\nFive synchronized panels, ROI, autoplay, lazy loading.",
        )
    def _show_keyboard_shortcuts(self) -> None:
        """Show keyboard shortcuts reference dialog."""
        from phage_annotator.ui_qt.widgets.keyboard_shortcuts_dialog import (
            KeyboardShortcutsDialog,
        )
        dialog = KeyboardShortcutsDialog(self)
        dialog.exec()
    def _show_contextual_help(self) -> None:
        """Show concise context-aware help for faster discovery."""
        queue_count = 0
        if hasattr(self, "_visible_suggestions_uncertain_first"):
            try:
                queue_count = len(self._visible_suggestions_uncertain_first())
            except Exception:
                queue_count = 0
        mode = "Review" if getattr(self, "dock_review_queue", None) is not None and self.dock_review_queue.isVisible() else "Annotate"
        current_panel = "Unknown"
        for act in getattr(self, "sidebar_actions", []) or []:
            if act.isChecked():
                current_panel = str(act.text())
                break
        assist_state = assist_state_label(self._canonical_assist_state())
        QtWidgets.QMessageBox.information(
            self,
            "Contextual Help",
            (
                f"Mode: {mode} | Sidebar panel: {current_panel} | Assist: {assist_state}\n"
                "Quick actions:\n"
                f"- Review queue visible suggestions: {queue_count}\n"
                "- A/R: accept/reject current suggestion (when suggestions are visible)\n"
                "- N/P: next/previous uncertain suggestion\n"
                "- Use right-dock panels: Annotation Table, Review Queue, Suggestion Rationale.\n"
                "- Use Layouts button near playback for quick presets."
            ),
        )
    def _visible_suggestions(self) -> list[PointSuggestion]:
        """Return suggestions visible on active image and T/Z slice."""
        visible = self.controller.get_visible_suggestions(
            self.primary_image.id,
            t_index=int(self.t_slider.value()),
            z_index=int(self.z_slider.value()),
            min_score=float(getattr(self, "_suggestion_score_threshold", 0.0)),
        )
        return self._filter_suggestions_to_active_roi(visible)
    def _suggestions_for_current_tz(self) -> list[PointSuggestion]:
        """Return all suggestions for active image and current T/Z, including decided history rows."""
        visible = self.controller.get_slice_suggestions(
            int(self.primary_image.id),
            t_index=int(self.t_slider.value()),
            z_index=int(self.z_slider.value()),
        )
        return self._filter_suggestions_to_active_roi(visible)
    def _filter_suggestions_to_active_roi(
        self, suggestions: list[PointSuggestion]
    ) -> list[PointSuggestion]:
        """Handle the filter suggestions to active roi helper flow."""
        if str(getattr(self, "roi_shape", "none")) == "none":
            return list(suggestions or [])
        return [
            suggestion
            for suggestion in list(suggestions or [])
            if self._point_in_roi(float(getattr(suggestion, "x", 0.0)), float(getattr(suggestion, "y", 0.0)))
        ]
    def _candidate_suggestion_strategies(self) -> list[str]:
        """Return available suggestion strategies for the current context."""
        options = [
            "current_view",
            "raw",
            "corrected",
            "mean_projection",
            "max_projection",
            "evidence_consensus",
            "evidence_contradiction",
        ]
        image = getattr(self, "primary_image", None)
        if image is not None and int(getattr(image, "channel_count", 1)) >= 2:
            options.extend(
                [
                    "channel_a_only",
                    "channel_b_only",
                    "channel_a_peak_b_low",
                    "channel_b_peak_a_low",
                ]
            )
        return options
