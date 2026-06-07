"""Extracted method group 5 for UiExtrasMixin."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.services.action_logger import get_action_logger

from phage_annotator.ui_qt.models.lazy_loader import (
    LAZY_LOADER_FILE_FILTER,
    LAZY_LOADER_OPEN_FILES_TITLE,
    LAZY_LOADER_OPEN_FOLDER_TITLE,
    LAZY_TABLE_COLUMN_GROUP,
    LAZY_TABLE_COLUMN_NAME,
    LAZY_TABLE_COLUMN_ANNOTATION_FILE,
    LAZY_TABLE_COLUMN_ANNOTATION_MODE,
    LAZY_TABLE_COLUMN_POINTS,
    LAZY_TABLE_COLUMN_PROJECTION,
    LAZY_TABLE_COLUMN_SHOW,
    LAZY_TABLE_COLUMN_SOURCE,
    LAZY_TABLE_COLUMN_SYNC_CONTRAST,
    LAZY_TABLE_COLUMN_SYNC_TIME,
    LAZY_TABLE_COLUMN_SYNC_VIEW,
    LAZY_TABLE_COLUMN_TABLE,
    LazyTableRowSpec,
    normalize_lazy_sync_groups,
    iter_tiff_paths,
)
from phage_annotator.ui_qt.utils.ui_extra_annotations import (
    UiAnnotationViewsMixin,
    _LogicalVisibilityLabel,
)
from phage_annotator.ui_qt.utils.ui_extra_refresh import UiRefreshMixin
from phage_annotator.ui_qt.utils.ui_extra_tooltips import UiTooltipMixin
from phage_annotator.ui_qt.utils.iconography import right_sidebar_icon, tool_icon, workflow_sidebar_icon
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter

PRIMARY_RIGHT_SIDEBAR_PANELS = (
    "annotations",
    "review_queue",
    "advanced_settings",
    "advanced_analysis",
    "qc_issues",
)
SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS = (
    "status_details",
)
ALL_RIGHT_SIDEBAR_PANELS = PRIMARY_RIGHT_SIDEBAR_PANELS + SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS



class ExtrasAnnotatePanelMixin:
    """Method group 5 extracted from UiExtrasMixin."""

    def _on_show_annotations_master_changed(self, state: int) -> None:
        """Toggle annotation overlays globally and keep per-panel point flags in sync."""
        enabled = bool(int(state))
        checkboxes = dict(getattr(self, "_annotation_view_checkboxes", {}) or {})
        changed_keys: list[str] = []
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        for key, chk in checkboxes.items():
            if not chk.isVisible():
                continue
            if chk.isChecked() != enabled:
                chk.blockSignals(True)
                chk.setChecked(enabled)
                chk.blockSignals(False)
            if point_vis.get(str(key), True) != enabled:
                point_vis[str(key)] = enabled
                changed_keys.append(str(key))
        self._annotation_panel_visibility = point_vis
        current_target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        if not enabled:
            # Keep current target visible to avoid accidental hidden-write confusion.
            self._annotation_panel_visibility[current_target] = True
            target_chk = checkboxes.get(current_target)
            if target_chk is not None:
                target_chk.blockSignals(True)
                target_chk.setChecked(True)
                target_chk.blockSignals(False)
        if changed_keys:
            self._refresh_lazy_modality_table()
        self._request_ui_refresh("ui-extra", table=bool(changed_keys))
    def _cycle_label(self, delta: int) -> None:
        """Cycle active label selection without leaving canvas workflow."""
        group = getattr(self, "label_buttons", None)
        if group is None:
            return
        buttons = list(group.buttons())
        if not buttons:
            return
        current_idx = 0
        for i, btn in enumerate(buttons):
            if btn.isChecked():
                current_idx = i
                break
        next_idx = (current_idx + int(delta)) % len(buttons)
        target = buttons[next_idx]
        target.setChecked(True)
        self.current_label = str(target.text())
        self._status_info(f"Active label: {self.current_label}", source="ui_extra")
        self._update_status()
    def _toggle_focus_canvas_mode(self) -> None:
        """Canvas-dominant focus mode with true space reclaim."""
        right_ids = [
            "annotations",
            "review_queue",
            "advanced_settings",
            "advanced_analysis",
            "qc_issues",
            "status_details",
        ]
        bottom_ids = [
            "qc_issues",
            "results",
            "threshold",
            "particles",
            "hist",
            "profile",
            "logs",
            "roi",
            "roi_manager",
        ]
        active = bool(getattr(self, "_focus_canvas_mode_active", False))
        target_on = not active
        self._focus_canvas_mode_active = target_on
        if target_on:
            self._focus_canvas_prev_right = {
                key: bool(getattr(self, "panel_docks", {}).get(key) and self.panel_docks[key].isVisible())
                for key in right_ids
            }
            self._focus_canvas_prev_bottom = {
                key: bool(getattr(self, "panel_docks", {}).get(key) and self.panel_docks[key].isVisible())
                for key in bottom_ids
            }
            self._collapse_sidebar()
            for key in right_ids:
                self.set_panel_visible(key, False, source="focus_canvas_mode")
            for key in bottom_ids:
                self.set_panel_visible(key, False, source="focus_canvas_mode")
            self.set_panel_visible("review_queue", True, source="focus_canvas_mode")
            self._set_right_handle_compact(True)
            self._status_info("Focus Canvas mode enabled.", source="ui_extra.focus_canvas")
        else:
            self._set_right_handle_compact(False)
            self._expand_sidebar()
            for key, visible in dict(getattr(self, "_focus_canvas_prev_right", {}) or {}).items():
                self.set_panel_visible(key, bool(visible), source="focus_canvas_mode_restore")
            for key, visible in dict(getattr(self, "_focus_canvas_prev_bottom", {}) or {}).items():
                self.set_panel_visible(key, bool(visible), source="focus_canvas_mode_restore")
            self._status_info("Focus Canvas mode disabled.", source="ui_extra.focus_canvas")
        self._apply_canvas_priority_layout()
    def _set_right_handle_compact(self, compact: bool) -> None:
        """Shrink right dock to a thin handle-like strip when compact mode is active."""
        dock = getattr(self, "dock_review_queue", None) or getattr(self, "dock_annotations", None)
        if dock is None:
            return
        if compact:
            self._focus_prev_right_features = int(dock.features())
            dock.setFeatures(
                dock.features() | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
            )
            dock.setMinimumWidth(28)
            dock.setMaximumWidth(36)
            self.resizeDocks([dock], [32], QtCore.Qt.Orientation.Horizontal)
        else:
            prev = getattr(self, "_focus_prev_right_features", None)
            if prev is not None:
                try:
                    dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeatures(prev))
                except Exception:
                    pass
            dock.setMaximumWidth(16777215)
            dock.setMinimumWidth(180)
    def _build_analyze_panel(self) -> QtWidgets.QWidget:
        """Build analyze panel for the current workflow."""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        intro_lbl = QtWidgets.QLabel(
            "Measure current annotations, inspect ROI-derived signals, and open specialized analysis docks when you need deeper quantitative workflows."
        )
        intro_lbl.setWordWrap(True)
        intro_lbl.setStyleSheet("color: #546e7a;")
        layout.addWidget(intro_lbl)

        results_group = QtWidgets.QGroupBox("Results and measurement")
        results_layout = QtWidgets.QVBoxLayout(results_group)
        results_layout.setContentsMargins(8, 8, 8, 8)
        results_layout.setSpacing(6)
        measure_now_btn = QtWidgets.QPushButton("Measure current selection")
        measure_now_btn.clicked.connect(self._results_measure_current)
        measure_over_time_btn = QtWidgets.QPushButton("Measure over time")
        measure_over_time_btn.clicked.connect(self._results_measure_over_time)
        open_results_btn = QtWidgets.QPushButton("Open Results Table")
        open_results_btn.clicked.connect(
            lambda: self.open_panel("results", reason="analyze_sidebar")
        )
        results_layout.addWidget(measure_now_btn)
        results_layout.addWidget(measure_over_time_btn)
        results_layout.addWidget(open_results_btn)
        layout.addWidget(results_group)

        roi_group = QtWidgets.QGroupBox("ROI and line analysis")
        roi_layout = QtWidgets.QVBoxLayout(roi_group)
        roi_layout.setContentsMargins(8, 8, 8, 8)
        roi_layout.setSpacing(6)
        roi_help = QtWidgets.QLabel(
            "Use these tools when analysis depends on a region of interest or a sampled line across the image."
        )
        roi_help.setWordWrap(True)
        roi_help.setStyleSheet("color: #546e7a;")
        roi_layout.addWidget(roi_help)
        roi_reset = QtWidgets.QPushButton("Reset ROI")
        roi_show = QtWidgets.QPushButton("Open ROI Controls")
        roi_reset.clicked.connect(self._reset_roi)
        roi_show.clicked.connect(lambda: self.set_panel_visible("roi", True, source="analyze_panel"))
        line_btn = QtWidgets.QPushButton("Line Profiles")
        bleach_btn = QtWidgets.QPushButton("ROI Mean + Bleaching Fit")
        table_btn = QtWidgets.QPushButton("ROI Mean Table")
        line_btn.clicked.connect(self._show_profile_dialog)
        bleach_btn.clicked.connect(self._show_bleach_dialog)
        table_btn.clicked.connect(self._show_table_dialog)
        roi_layout.addWidget(roi_show)
        roi_layout.addWidget(roi_reset)
        roi_layout.addWidget(line_btn)
        roi_layout.addWidget(bleach_btn)
        roi_layout.addWidget(table_btn)
        layout.addWidget(roi_group)

        quant_group = QtWidgets.QGroupBox("Advanced quantitative tools")
        quant_layout = QtWidgets.QVBoxLayout(quant_group)
        quant_layout.setContentsMargins(8, 8, 8, 8)
        quant_layout.setSpacing(6)
        density_btn = QtWidgets.QPushButton("Open Density Analysis")
        density_btn.clicked.connect(lambda: self.open_panel("density", reason="analyze_sidebar"))
        orthoview_btn = QtWidgets.QPushButton("Open Ortho Views")
        orthoview_btn.clicked.connect(lambda: self.open_panel("orthoview", reason="analyze_sidebar"))
        smlm_btn = QtWidgets.QPushButton("Open SMLM Tools")
        smlm_btn.clicked.connect(lambda: self.open_panel("smlm", reason="analyze_sidebar"))
        quant_layout.addWidget(density_btn)
        quant_layout.addWidget(orthoview_btn)
        quant_layout.addWidget(smlm_btn)
        layout.addWidget(quant_group)

        export_group = QtWidgets.QGroupBox("Export measurements")
        export_layout = QtWidgets.QVBoxLayout(export_group)
        export_layout.setContentsMargins(8, 8, 8, 8)
        export_layout.setSpacing(6)
        export_csv = QtWidgets.QPushButton("Save CSV")
        export_json = QtWidgets.QPushButton("Save JSON")
        export_csv.clicked.connect(self._save_csv)
        export_json.clicked.connect(self._save_json)
        export_layout.addWidget(export_csv)
        export_layout.addWidget(export_json)
        layout.addWidget(export_group)

        layout.addStretch(1)
        return panel
