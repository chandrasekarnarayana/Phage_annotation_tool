"""Extracted method group 3 for UiExtrasMixin."""

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



class ExtrasSidebarToggleMixin:
    """Method group 3 extracted from UiExtrasMixin."""

    def _toggle_right_sidebar_panel(self, panel_id: str) -> None:
        """VSCode-like right rail behavior: select one panel or collapse current."""
        panel_id = str(panel_id)
        inspect_ids = list(self._primary_right_sidebar_panels())
        target_dock = getattr(self, f"dock_{panel_id}", None)
        if target_dock is None:
            return
        
        # Check if this panel is the only one visible
        any_other_visible = False
        for pid in inspect_ids:
            if pid == panel_id:
                continue
            dock = getattr(self, f"dock_{pid}", None)
            if dock is not None and dock.isVisible():
                any_other_visible = True
                break
        is_only_visible = bool(target_dock.isVisible()) and not any_other_visible
        
        # If clicking the active panel, collapse the entire sidebar
        if is_only_visible:
            for pid in inspect_ids:
                self.set_panel_visible(pid, False, source="right_sidebar")
            self._collapse_right_sidebar()
            self._right_sidebar_intentionally_closed = True  # Mark as intentionally closed
            self._sync_annotation_toolbar(False)
            return
        
        # Ensure right sidebar expands to normal width before activating a panel
        if getattr(self, "_right_sidebar_collapsed", False):
            self._expand_right_sidebar()
        
        # Clear the intentionally closed flag when opening a panel
        self._right_sidebar_intentionally_closed = False
        
        # Hide all other panels, show only the selected one
        for pid in inspect_ids:
            self.set_panel_visible(pid, pid == panel_id, source="right_sidebar")
            dock = getattr(self, f"dock_{pid}", None)
            if dock is not None:
                try:
                    self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
                except Exception:
                    pass
        target_dock.raise_()
        # Enforce a practical open width (avoid ultra-thin right pane).
        preferred_right = int(
            getattr(self, "_right_sidebar_last_width", 0)
            or self._settings.value("rightSidebarDefaultWidth", 420, type=int)
        )
        preferred_right = max(420, preferred_right)
        target_dock.setMinimumWidth(360)
        left = getattr(self, "dock_sidebar", None)
        try:
            if left is not None and left.isVisible():
                left_w = max(220, int(left.width()))
                self.resizeDocks([left, target_dock], [left_w, preferred_right], QtCore.Qt.Orientation.Horizontal)
            else:
                self.resizeDocks([target_dock], [preferred_right], QtCore.Qt.Orientation.Horizontal)
        except Exception:
            pass
        self._capture_right_sidebar_width()
        self._ensure_right_sidebar_panels_not_tabified()
        self._sync_annotation_toolbar(True)
    def _collapse_sidebar(self) -> None:
        """Collapse sidebar to slim activity bar only."""
        if self.sidebar_stack and self.sidebar_stack.isVisible():
            self.sidebar_stack.setVisible(False)
            if getattr(self, "sidebar_breadcrumb", None) is not None:
                self.sidebar_breadcrumb.setVisible(False)
            self._sidebar_collapsed = True
            self._settings.setValue("sidebarCollapsed", True)
            self._set_sidebar_expanded(False)
            self._apply_canvas_priority_layout()
    def _expand_sidebar(self) -> None:
        """Expand sidebar to show active panel."""
        if self.sidebar_stack and not self.sidebar_stack.isVisible():
            self.sidebar_stack.setVisible(True)
            if getattr(self, "sidebar_breadcrumb", None) is not None:
                self.sidebar_breadcrumb.setVisible(True)
            self._sidebar_collapsed = False
            self._settings.setValue("sidebarCollapsed", False)
            self._set_sidebar_expanded(True)
            self._apply_canvas_priority_layout()
    def _collapse_right_sidebar(self) -> None:
        """Collapse right sidebar to icon-only state (48px)."""
        self._right_sidebar_collapsed = True
        self._right_sidebar_expanded = False
        self._settings.setValue("rightSidebarCollapsed", True)
        self._apply_canvas_priority_layout()
    def _expand_right_sidebar(self) -> None:
        """Expand right sidebar to full width."""
        self._right_sidebar_collapsed = False
        self._right_sidebar_expanded = True
        self._settings.setValue("rightSidebarCollapsed", False)
        preferred_right = int(
            getattr(self, "_right_sidebar_last_width", 0)
            or self._settings.value("rightSidebarDefaultWidth", 420, type=int)
        )
        preferred_right = max(420, preferred_right)
        for panel_id in (
            "annotations",
            "review_queue",
            "advanced_settings",
            "advanced_analysis",
            "qc_issues",
            "status_details",
        ):
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is not None:
                dock.setMinimumWidth(360)
        active_right = next(
            (
                getattr(self, f"dock_{pid}", None)
                for pid in (
                    "annotations",
                    "review_queue",
                    "advanced_settings",
                    "advanced_analysis",
                    "qc_issues",
                    "status_details",
                )
                if getattr(self, f"dock_{pid}", None) is not None
                and getattr(self, f"dock_{pid}").isVisible()
            ),
            None,
        )
        if active_right is not None:
            left = getattr(self, "dock_sidebar", None)
            try:
                if left is not None and left.isVisible():
                    left_w = max(220, int(left.width()))
                    self.resizeDocks([left, active_right], [left_w, preferred_right], QtCore.Qt.Orientation.Horizontal)
                else:
                    self.resizeDocks([active_right], [preferred_right], QtCore.Qt.Orientation.Horizontal)
            except Exception:
                pass
        self._ensure_right_sidebar_panels_not_tabified()
        self._apply_canvas_priority_layout()
    def _toggle_right_sidebar_collapse(self) -> None:
        """Toggle right sidebar between collapsed and expanded states."""
        if getattr(self, "_right_sidebar_collapsed", False):
            self._expand_right_sidebar()
        else:
            self._collapse_right_sidebar()
