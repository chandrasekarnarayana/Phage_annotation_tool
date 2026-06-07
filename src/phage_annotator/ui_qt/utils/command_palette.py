"""Extracted method group 12 for UiExtrasMixin."""

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



class CommandPaletteMixin:
    """Method group 12 extracted from UiExtrasMixin."""

    def _restore_sidebar_mode(self) -> None:
        """Restore sidebar panel and collapsed/expanded state from settings."""
        if not self.sidebar_stack or not self.sidebar_actions:
            return
        
        # Restore panel index
        idx = self._settings.value("sidebarMode", 0, type=int)
        idx = self.sidebar_manager.clamp_index(idx, len(self.sidebar_actions))
        
        # Restore collapsed state
        collapsed = self._settings.value("sidebarCollapsed", False, type=bool)
        
        if collapsed:
            self._collapse_sidebar()
            # Still set the current index so it's ready when expanded
            stack_idx = self.sidebar_panel_indices.get(idx, 0)
            if stack_idx >= 0:
                self.sidebar_stack.setCurrentIndex(stack_idx)
            if getattr(self, "sidebar_breadcrumb", None) is not None:
                label = self.sidebar_actions[idx].text()
                self.sidebar_breadcrumb.setText(self.sidebar_manager.breadcrumb_text(label))
        else:
            self._expand_sidebar()
            self._set_sidebar_mode(idx)
        
        # Restore right sidebar collapsed state
        right_collapsed = self._settings.value("rightSidebarCollapsed", False, type=bool)
        if right_collapsed:
            self._collapse_right_sidebar()
        else:
            self._expand_right_sidebar()
        
        # ALWAYS normalize right sidebar to show only Annotations at startup
        # This ensures consistent behavior regardless of previous session state
        for panel_id in (
            "review_queue",
            "advanced_settings",
            "advanced_analysis",
            "status_details",
            "qc_issues",
        ):
            self.set_panel_visible(panel_id, False, source="startup_normalize")
        if getattr(self, "dock_annotations", None) is not None:
            self.set_panel_visible("annotations", True, source="startup_normalize")
            try:
                self.dock_annotations.raise_()
            except Exception:
                pass
        self._apply_canvas_priority_layout()
    def _apply_canvas_priority_layout(self) -> None:
        """Resize docks so the canvas remains the primary focus."""
        docks: List[QtWidgets.QDockWidget] = []
        sizes: List[int] = []

        sidebar_visible = getattr(self, "dock_sidebar", None) is not None and self.dock_sidebar.isVisible()
        right_dock = None
        for attr in (
            "dock_annotations",
            "dock_review_queue",
            "dock_advanced_settings",
            "dock_advanced_analysis",
            "dock_qc_issues",
            "dock_status_details",
        ):
            candidate = getattr(self, attr, None)
            if candidate is not None and candidate.isVisible():
                right_dock = candidate
                break
        annotations_visible = right_dock is not None
        if annotations_visible and right_dock is not None:
            width = int(right_dock.width())
            if width > 80:
                self._right_sidebar_last_width = width
            if not bool(getattr(self, "_right_sidebar_collapsed", False)):
                try:
                    right_dock.setMinimumWidth(360)
                    right_dock.setMaximumWidth(16777215)
                except Exception:
                    pass

        for key in self.sidebar_manager.dock_order(sidebar_visible, annotations_visible):
            if key == "sidebar":
                docks.append(self.dock_sidebar)
            elif key == "annotations":
                docks.append(right_dock)

        sizes = self.sidebar_manager.dock_sizes(
            sidebar_visible=sidebar_visible,
            annotations_visible=annotations_visible,
            collapsed=getattr(self, "_sidebar_collapsed", False),
            annotations_collapsed=getattr(self, "_right_sidebar_collapsed", False),
        )

        if docks:
            preferred_right = int(
                getattr(self, "_right_sidebar_last_width", 0)
                or self._settings.value(
                    "rightSidebarDefaultWidth",
                    self.sidebar_manager.config.annotations_width,
                    type=int,
                )
            )
            if annotations_visible and sizes:
                # Use collapsed width if right sidebar is collapsed, else use preferred width
                if getattr(self, "_right_sidebar_collapsed", False):
                    sizes[-1] = self.sidebar_manager.config.annotations_collapsed_width
                else:
                    sizes[-1] = max(360, preferred_right)
            self.resizeDocks(docks, sizes, QtCore.Qt.Orientation.Horizontal)
    def _set_sidebar_expanded(self, expanded: bool) -> None:
        """Set sidebar expanded for the current workflow."""
        if self.sidebar_stack is None:
            return
        if expanded == self._sidebar_expanded:
            return
        self._sidebar_expanded = expanded
        if expanded:
            self.sidebar_stack.setVisible(True)
            if self.dock_sidebar is not None:
                self.dock_sidebar.setMaximumWidth(16777215)
                self.dock_sidebar.setMinimumWidth(
                    self._sidebar_bar_width + self._sidebar_stack_min_width
                )
                if self._sidebar_last_width:
                    self.dock_sidebar.resize(self._sidebar_last_width, self.dock_sidebar.height())
        else:
            if self.dock_sidebar is not None:
                self._sidebar_last_width = self.dock_sidebar.width()
                self.dock_sidebar.setMinimumWidth(self._sidebar_bar_width)
                self.dock_sidebar.setMaximumWidth(self._sidebar_bar_width)
                self.dock_sidebar.resize(self._sidebar_bar_width, self.dock_sidebar.height())
            self.sidebar_stack.setVisible(False)
    def _set_right_sidebar_expanded(self, expanded: bool) -> None:
        """Toggle right sidebar (annotations/inspect panels) between expanded and collapsed states."""
        if expanded == getattr(self, "_right_sidebar_expanded", True):
            return
        self._right_sidebar_expanded = expanded
        if not hasattr(self, "_right_sidebar_collapsed"):
            self._right_sidebar_collapsed = False
        # Collapsed state is opposite of expanded
        self._right_sidebar_collapsed = not expanded
        # Resize right dock to apply the new width
        self._apply_canvas_priority_layout()
    def _collect_command_actions(self) -> List[QtWidgets.QAction]:
        """Collect command actions for the current workflow."""
        actions: List[QtWidgets.QAction] = []
        seen = set()

        def _add_action(act: QtWidgets.QAction) -> None:
            """Add action for the current workflow."""
            if act in seen:
                return
            if not act.isVisible():
                return
            text = act.text().replace("&", "").strip()
            if not text:
                return
            seen.add(act)
            actions.append(act)

        def _walk_menu(menu: QtWidgets.QMenu) -> None:
            """Handle the walk menu helper flow."""
            for act in menu.actions():
                if act.isSeparator():
                    continue
                if not act.isVisible():
                    continue
                if act.menu() is not None:
                    _walk_menu(act.menu())
                else:
                    _add_action(act)

        for act in self.menuBar().actions():
            if act.menu() is not None:
                _walk_menu(act.menu())

        for act in self.sidebar_actions:
            _add_action(act)

        if self.command_palette_act is not None:
            _add_action(self.command_palette_act)
        if self.reset_view_act is not None:
            _add_action(self.reset_view_act)
        for act in dict(getattr(self, "panel_open_actions", {}) or {}).values():
            _add_action(act)

        return actions
    def _show_command_palette(self) -> None:
        """Show command palette for the current workflow."""
        self._show_command_palette_with_query("")
    def _show_panel_switcher(self) -> None:
        """Open command palette in panel-only mode."""
        self._show_command_palette_with_query("panel ")
