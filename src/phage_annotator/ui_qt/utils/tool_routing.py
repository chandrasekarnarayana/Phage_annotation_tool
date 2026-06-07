"""Extracted method group 6 for UiExtrasMixin."""

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



class ToolRoutingMixin:
    """Method group 6 extracted from UiExtrasMixin."""

    def _setup_tool_router(self) -> None:
        """Handle the setup tool router helper flow."""
        callbacks = ToolCallbacks(
            get_target_ax=self._get_target_axis,
            get_image_axes=self._get_image_axes,
            get_tz=lambda: (self.t_slider.value(), self.z_slider.value()),
            get_primary_image_id=lambda: self.primary_image.id,
            get_label=lambda: self.current_label,
            get_scope=lambda: self.annotation_scope,
            map_to_fullres=lambda ax, x, y: self._to_full_coords(ax, x, y),
            point_in_roi=self._point_in_roi,
            add_point=self._add_annotation,
            remove_near=self._remove_annotation_near,
            set_roi_rect=self._set_roi_rect,
            set_roi_shape=self._set_roi_shape,
            set_profile_line=self._set_profile_line,
            set_profile_mode=self._set_profile_mode,
            refresh=self._refresh_image,
            set_status=lambda text: self._status_info(str(text), source="tool.router"),
        )
        self.tool_router = ToolRouter(callbacks)
        # Restore last active tool from QSettings
        saved_tool_str = self._settings.value("activeTool", "ANNOTATE_POINT", type=str)
        try:
            saved_tool = Tool(saved_tool_str)
        except ValueError:
            saved_tool = Tool.ANNOTATE_POINT
        self._set_tool(saved_tool)
    def _init_tool_bar(self) -> None:
        """Initialize tool bar for the current workflow."""
        toolbar = QtWidgets.QToolBar("Tools", self)
        toolbar.setObjectName("tools_toolbar")
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setMovable(True)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        self.tools_toolbar = toolbar

        group = QtWidgets.QActionGroup(self)
        group.setExclusive(True)
        icons = {
            Tool.PAN_ZOOM: tool_icon(self.style(), "pan_zoom"),
            Tool.ANNOTATE_POINT: tool_icon(self.style(), "annotate_point"),
            Tool.ROI_BOX: tool_icon(self.style(), "roi_box"),
            Tool.ROI_CIRCLE: tool_icon(self.style(), "roi_circle"),
            Tool.ROI_EDIT: tool_icon(self.style(), "roi_edit"),
            Tool.PROFILE_LINE: tool_icon(self.style(), "profile_line"),
            Tool.ERASER: tool_icon(self.style(), "eraser"),
        }
        tool_specs = [
            (Tool.PAN_ZOOM, "Pan/Zoom"),
            (Tool.ANNOTATE_POINT, "Annotate"),
            (Tool.ROI_BOX, "ROI Box"),
            (Tool.ROI_CIRCLE, "ROI Circle"),
            (Tool.ROI_EDIT, "ROI Edit"),
            (Tool.PROFILE_LINE, "Profile"),
            (Tool.ERASER, "Eraser"),
        ]
        shortcuts = {
            Tool.PAN_ZOOM: ["1"],
            Tool.ANNOTATE_POINT: ["2"],
            Tool.ROI_BOX: ["3", "R"],
            Tool.ROI_CIRCLE: ["4", "O"],
            Tool.ROI_EDIT: ["E"],
            Tool.PROFILE_LINE: ["5"],
            Tool.ERASER: ["6"],
        }
        for tool, label in tool_specs:
            act = QtWidgets.QAction(icons[tool], label, self)
            act.setCheckable(True)
            act.setShortcuts(shortcuts.get(tool, []))
            act.triggered.connect(lambda checked, t=tool: self._set_tool(t))
            group.addAction(act)
            toolbar.addAction(act)
            self.tool_actions[tool] = act

        jump_to_frame = getattr(self, "jump_to_frame_act", None)
        jump_to_z = getattr(self, "jump_to_z_act", None)
        if jump_to_frame is not None and jump_to_z is not None:
            jump_to_frame.setIcon(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSeekForward)
            )
            jump_to_z.setIcon(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipForward)
            )
            jump_to_frame.setToolTip("Jump to frame (Ctrl+G)")
            jump_to_z.setToolTip("Jump to Z slice (Ctrl+Shift+G)")
            toolbar.addSeparator()
            toolbar.addAction(jump_to_frame)
            toolbar.addAction(jump_to_z)
    def _set_tool(self, tool: Tool) -> None:
        # Clear any lingering tooltips when switching tools
        """Set tool for the current workflow."""
        self._clear_all_tooltips()
        if self.tool_router is not None:
            self.tool_router.set_tool(tool)
        self.controller.set_tool(tool.value)
        self._settings.setValue("activeTool", tool.value)
        act = self.tool_actions.get(tool)
        if act is not None:
            act.setChecked(True)
        self._set_roi_interactor_tool(tool)
        self._sync_nav_mode(tool)
        if self.tool_label is not None:
            self.tool_label.setText(f"Tool: {self._tool_label(tool)}")
        if tool == Tool.ANNOTATE_POINT and hasattr(self, "_set_right_dock_mode"):
            self._set_right_dock_mode("annotate")
    def _set_right_dock_mode(self, mode: str) -> None:
        """Mode-aware right dock behavior: annotate/review/inspect."""
        target = str(mode or "").strip().lower()
        if target == "annotate":
            self._show_right_dock_mode("annotations")
            return
        if target == "review":
            extras: tuple[str, ...] = ()
            if getattr(self, "_visible_suggestions_uncertain_first", None) is not None:
                try:
                    if bool(getattr(self, "qc_state", None) and len(getattr(self.qc_state, "issues", []) or []) > 0):
                        extras = extras + ("qc_issues",)
                except Exception:
                    extras = ()
            self._show_right_dock_mode("review_queue", extras=extras)
            return
        if target == "inspect":
            self._show_right_dock_mode("annotations")
            return
    def _show_right_dock_mode(self, primary_panel: str, *, extras: tuple[str, ...] = ()) -> None:
        """Show one right-dock workflow state with an optional supporting context panel."""
        right_ids = self._all_right_sidebar_panels()
        wanted = {str(primary_panel)} | {str(panel_id) for panel_id in extras}
        self._set_right_handle_compact(False)
        if getattr(self, "_right_sidebar_collapsed", False):
            self._expand_right_sidebar()
        for panel_id in right_ids:
            self.set_panel_visible(panel_id, panel_id in wanted, source="mode_right_dock")
        primary_dock = getattr(self, f"dock_{primary_panel}", None)
        if primary_dock is not None:
            try:
                primary_dock.setMinimumWidth(360 if str(primary_panel) == "annotations" else 300)
            except Exception:
                pass
            primary_dock.raise_()
        if not getattr(self, "_right_sidebar_collapsed", False):
            self._apply_canvas_priority_layout()
    def _set_assist_mode(self, enabled: bool, *, source: str = "user") -> None:
        """Toggle assist-focused UI emphasis without hiding core panels."""
        enabled = bool(enabled)
        self._assist_mode_enabled = enabled
        self._settings.setValue("assistModeEnabled", enabled)
        btn = getattr(self, "status_assist_mode_btn", None)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(enabled)
            btn.setText("Assist Mode: On" if enabled else "Assist Mode: Off")
            btn.blockSignals(False)
        if enabled:
            self._show_right_dock_mode("review_queue", extras=("qc_issues",))
            self._status_info("Assist Mode enabled.", timeout_ms=2500, source="ui_extra.assist_mode")
            return
        # OFF: keep review queue available, but raise table and reduce inspect clutter.
        self._show_right_dock_mode("annotations")
        self._status_info("Assist Mode disabled.", timeout_ms=2500, source="ui_extra.assist_mode")
    def _sync_nav_mode(self, tool: Tool) -> None:
        """Synchronize nav mode for the current workflow."""
        if self.toolbar is None:
            return
        if tool == Tool.PAN_ZOOM:
            if getattr(self.toolbar, "mode", "") != "pan/zoom":
                self.toolbar.pan()
        else:
            if getattr(self.toolbar, "mode", ""):
                self.toolbar.pan()
    def _set_roi_interactor_tool(self, tool: Tool) -> None:
        """Set roi interactor tool for the current workflow."""
        if self.renderer is None or self.renderer.roi_interactor is None:
            return
        if tool == Tool.ROI_BOX:
            self.renderer.roi_interactor.set_tool("draw_rect")
        elif tool == Tool.ROI_CIRCLE:
            self.renderer.roi_interactor.set_tool("draw_circle")
        elif tool == Tool.ROI_EDIT:
            self.renderer.roi_interactor.set_tool("edit")
        else:
            self.renderer.roi_interactor.set_tool("idle")
    def _get_target_axis(self):
        """Return target axis for the current workflow."""
        axes = self.renderer.axes if getattr(self, "renderer", None) is not None else {}
        target_key = str(getattr(self, "annotate_target", "frame")).strip().lower()
        ax = axes.get(target_key)
        if ax is not None:
            return ax
        if "frame" in axes:
            return axes.get("frame")
        # Fallback to first available axis to keep annotation workflow operable.
        return next(iter(axes.values()), None)
    def _get_image_axes(self) -> Set[object]:
        """Return image axes for the current workflow."""
        if getattr(self, "renderer", None) is None:
            return set()
        return {ax for ax in self.renderer.axes.values() if ax is not None}
    def _set_roi_shape(self, shape: str) -> None:
        """Set roi shape for the current workflow."""
        if hasattr(self, "controller") and self.controller is not None:
            self.controller.set_roi(self.roi_rect, shape=shape)
        self.roi_shape = shape
        buttons = self.roi_shape_group.buttons()
        if buttons:
            buttons[0].setChecked(shape == "box")
            if len(buttons) > 1:
                buttons[1].setChecked(shape == "circle")
    def _set_sidebar_mode(self, idx: int) -> None:
        """Switch to the specified sidebar panel and update action states."""
        if not self.sidebar_stack or not self.sidebar_actions:
            return
        current_idx = self.sidebar_stack.currentIndex()

        # Map action index to stack index (skip Playback)
        stack_idx = self.sidebar_panel_indices.get(idx, -1)
        if stack_idx == -1:
            # Playback panel (no stack widget), just update checked state
            for i, act in enumerate(self.sidebar_actions):
                act.setChecked(i == idx)
            return
        
        # Switch to the panel
        self.sidebar_stack.setCurrentIndex(stack_idx)
        if current_idx != stack_idx:
            self._collapse_sidebar_context_docks_for_stack_index(stack_idx)
            self._apply_sidebar_mode_defaults_for_stack_index(stack_idx)
        self._settings.setValue("sidebarMode", idx)
