"""Extracted method group 14 for UiExtrasMixin."""

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



class LayoutPresetMixin:
    """Method group 14 extracted from UiExtrasMixin."""

    def _reset_layout(self) -> None:
        """Reset dock placement to PanelSpec defaults without removing docks."""
        self._capture_layout_snapshot()
        self._apply_panel_defaults()
        self._preset_active = False
        self._apply_canvas_priority_layout()
        self._status_info(
            "Layout changed. Use Layout > Layouts > Undo Layout Change.",
            timeout_ms=8000,
            source="ui_extra.layout",
        )
    def apply_preset(self, name: str) -> None:
        """Apply a named layout preset without overwriting saved custom layout."""
        self._capture_layout_snapshot()
        self._preset_active = True
        self._active_layout_preset = str(name)

        if name == "Default_Legacy":
            if self._default_geometry is not None:
                self.restoreGeometry(self._default_geometry)
            if self._default_state is not None:
                self.restoreState(self._default_state)
            return

        def _dock_to_area(panel_id: str, area: QtCore.Qt.DockWidgetArea) -> None:
            """Handle the dock to area helper flow."""
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is not None:
                self.addDockWidget(area, dock)

        # Canonical geometry targets for key presets.
        _dock_to_area("sidebar", QtCore.Qt.LeftDockWidgetArea)
        if name in {"Default", "Annotate", "Analyze", "Assist Expert"}:
            _dock_to_area("annotations", QtCore.Qt.RightDockWidgetArea)
            _dock_to_area("review_queue", QtCore.Qt.RightDockWidgetArea)
        if name in {"Analyze", "Assist Expert"}:
            _dock_to_area("qc_issues", QtCore.Qt.RightDockWidgetArea)
        if name == "Analyze":
            _dock_to_area("results", QtCore.Qt.BottomDockWidgetArea)
            _dock_to_area("threshold", QtCore.Qt.BottomDockWidgetArea)
            if self.dock_results is not None and self.dock_threshold is not None:
                self.tabifyDockWidget(self.dock_results, self.dock_threshold)
            _dock_to_area("orthoview", QtCore.Qt.RightDockWidgetArea)
        if name == "Analyze":
            _dock_to_area("advanced_analysis", QtCore.Qt.RightDockWidgetArea)

        preset_visibility: dict[str, dict[str, bool]] = {
            "Default": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "status_details": False,
                "advanced_analysis": False,
                "roi": False,
                "roi_manager": False,
                "results": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "threshold": False,
                "particles": False,
                "qc_issues": True,
                "orthoview": False,
            },
            "Minimal": {
                "sidebar": True,
                "annotations": False,
                "review_queue": False,
                "status_details": False,
                "advanced_analysis": False,
                "roi": False,
                "roi_manager": False,
                "results": False,
                "threshold": False,
                "particles": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "qc_issues": True,
                "orthoview": False,
            },
            "Annotate": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "status_details": False,
                "advanced_analysis": False,
                "roi": False,
                "roi_manager": False,
                "results": False,
                "threshold": False,
                "particles": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "qc_issues": True,
                "orthoview": False,
            },
            "Analyze": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "status_details": False,
                "advanced_analysis": True,
                "results": True,
                "threshold": True,
                "orthoview": True,
                "roi": False,
                "roi_manager": False,
                "particles": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "qc_issues": True,
            },
            "Assist Expert": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "status_details": False,
                "advanced_analysis": False,
                "qc_issues": True,
                "roi": False,
                "roi_manager": False,
                "results": False,
                "threshold": False,
                "particles": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "metadata": False,
                "density": False,
                "orthoview": False,
            },
        }

        preset_sidebar = {
            "Default": ("Lazy Loading", False),
            "Minimal": (None, False),
            "Annotate": ("Annotation", True),
            "Analyze": ("Contrast", True),
            "Assist Expert": ("Annotation", True),
        }
        if name not in preset_sidebar:
            return
        sidebar_label, expand = preset_sidebar[name]
        if sidebar_label is not None:
            sidebar_idx = self._sidebar_action_index_for_label(sidebar_label)
            if sidebar_idx >= 0:
                self._set_sidebar_mode(sidebar_idx)
        if expand:
            self._expand_sidebar()
        else:
            self._collapse_sidebar()

        preset = preset_visibility.get(name)
        if preset is not None:
            self.apply_panel_visibility_preset(preset, source=f"preset:{name.lower().replace(' ', '_')}")
        if name == "Default":
            for key in ("annotations", "advanced_analysis"):
                self.set_panel_visible(key, False, source="preset:default_canvas_home")
            self.set_panel_visible("review_queue", True, source="preset:default_canvas_home")
            self._set_right_handle_compact(False)
            self._set_bottom_docks_compact(True)
        else:
            self._set_right_handle_compact(False)
            self._set_bottom_docks_compact(False)
        if name == "Assist Expert" and self.dock_annotations is not None:
            self.dock_annotations.resize(
                self.dock_annotations.width(),
                max(220, self.dock_annotations.height()),
            )
        if name == "Assist Expert" and self.dock_review_queue is not None:
            self.dock_review_queue.raise_()
        if name == "Default" and self.dock_annotations is not None:
            self.dock_annotations.raise_()
        self._status_info(
            "Layout changed. Use Layout > Layouts > Undo Layout Change.",
            timeout_ms=8000,
            source="ui_extra.layout",
        )
        self._apply_canvas_priority_layout()
        return
    def _set_bottom_docks_compact(self, compact: bool) -> None:
        """Keep bottom-dock footprint minimal in canvas-first modes."""
        panel_docks = dict(getattr(self, "panel_docks", {}) or {})
        bottom_visible = []
        for dock in panel_docks.values():
            if dock is None or not dock.isVisible():
                continue
            try:
                if self.dockWidgetArea(dock) == QtCore.Qt.DockWidgetArea.BottomDockWidgetArea:
                    bottom_visible.append(dock)
            except Exception:
                continue
        if not bottom_visible:
            return
        if compact:
            per = max(44, int(max(1, self.height()) * 0.10))
        else:
            per = max(120, int(max(1, self.height()) * 0.20))
        self.resizeDocks(bottom_visible, [per for _ in bottom_visible], QtCore.Qt.Orientation.Vertical)
    def closeEvent(self, event) -> None:
        """Persist layout before closing the main window."""
        self._save_layout()
        lock = getattr(self, "_instance_lock", None)
        if lock is not None:
            try:
                if lock.isLocked():
                    lock.unlock()
            except Exception:
                pass
        for fig_name in ("hist_fig", "contrast_hist_fig", "profile_fig"):
            fig = getattr(self, fig_name, None)
            if fig is not None:
                fig.clear()
        QtWidgets.QMainWindow.closeEvent(self, event)
