"""UI helpers for sidebar, tool routing, layout, and command palette."""

from __future__ import annotations

from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.sidebar_manager import SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter


class UiExtrasMixin:
    """Mixin for sidebar pages, tools, and layout/command palette actions."""

    def _build_sidebar_stack(self) -> QtWidgets.QWidget:
        """Create the 10-panel stacked sidebar with activity bar and toggle behavior.
        
        Toggle behavior:
        - Clicking a different icon switches panel and expands sidebar if collapsed
        - Clicking the same icon collapses sidebar to slim bar (or expands if already collapsed)
        """
        # Initialize state tracking
        self._sidebar_expanded = True
        self._sidebar_last_width = None
        self._sidebar_stack_min_width = 260
        self._sidebar_bar_width = 36
        self._sidebar_collapsed = False
        self.sidebar_manager = SidebarManager()
        
        # Create the stacked widget for panels
        self.sidebar_stack = QtWidgets.QStackedWidget()
        self.sidebar_stack.setObjectName("sidebar_stack")

        # Breadcrumb label for the current sidebar section
        self.sidebar_breadcrumb = QtWidgets.QLabel()
        self.sidebar_breadcrumb.setObjectName("sidebar_breadcrumb")
        self.sidebar_breadcrumb.setText(self.sidebar_manager.breadcrumb_text("Explore"))
        self.sidebar_breadcrumb.setStyleSheet("font-weight: 600; padding: 6px 8px;")
        
        # Use the 10-panel registry if sidebar_pages are built
        pages = getattr(self, "sidebar_pages", None)
        if pages:
            # Add all panel widgets to the stack (skip Playback since it's bottom bar only)
            for idx, (label, icon, widget) in enumerate(pages):
                if label != "Playback":  # Playback is bottom bar only
                    self.sidebar_stack.addWidget(widget)
                    widget.setObjectName(f"sidebar_panel_{idx}")
        else:
            # Fallback to 3-panel (should not reach here with proper setup)
            self.sidebar_stack.addWidget(self.explore_panel)
            self.sidebar_stack.addWidget(self.annotate_panel)
            self.sidebar_stack.addWidget(self._build_analyze_panel())

        # Create the activity bar (vertical toolbar)
        bar = QtWidgets.QToolBar("Activity Bar", self)
        bar.setObjectName("activity_bar")
        bar.setOrientation(QtCore.Qt.Orientation.Vertical)
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        bar.setMovable(False)
        bar.setIconSize(QtCore.QSize(20, 20))
        bar.setFixedWidth(self._sidebar_bar_width)
        self.sidebar_bar = bar

        # Create actions for each panel
        self.sidebar_actions = []
        self.sidebar_panel_indices = {}  # Map action index to stack index
        
        if pages:
            stack_idx = 0
            for page_idx, (label, icon, widget) in enumerate(pages):
                act = QtWidgets.QAction(self.style().standardIcon(icon), label, self)
                act.setObjectName(f"sidebar_action_{label.lower().replace('/', '_').replace(' ', '_')}")
                act.setCheckable(True)
                act.setToolTip(label)
                
                # Connect with toggle behavior
                act.triggered.connect(lambda checked, i=page_idx: self._on_sidebar_action_triggered(i))
                self.sidebar_actions.append(act)
                bar.addAction(act)
                
                # Map to stack index (skip Playback)
                if label != "Playback":
                    self.sidebar_panel_indices[page_idx] = stack_idx
                    stack_idx += 1
                else:
                    self.sidebar_panel_indices[page_idx] = -1  # Not in stack
            
            # Check first action by default
            if self.sidebar_actions:
                self.sidebar_actions[0].setChecked(True)
        else:
            # Fallback actions
            explore_act = QtWidgets.QAction(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon),
                "Explore",
                self,
            )
            annotate_act = QtWidgets.QAction(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView),
                "Annotate",
                self,
            )
            analyze_act = QtWidgets.QAction(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
                "Analyze",
                self,
            )
            for idx, act in enumerate([explore_act, annotate_act, analyze_act]):
                act.setCheckable(True)
                act.triggered.connect(lambda checked, i=idx: self._on_sidebar_action_triggered(i))
                self.sidebar_actions.append(act)
                bar.addAction(act)
                self.sidebar_panel_indices[idx] = idx
            explore_act.setChecked(True)

        # Create container with bar + stack
        sidebar_container = QtWidgets.QWidget()
        sidebar_container.setObjectName("sidebar_container")
        sidebar_layout = QtWidgets.QHBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(bar)

        self.sidebar_stack.setMinimumWidth(self._sidebar_stack_min_width)
        self.sidebar_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        stack_container = QtWidgets.QWidget()
        stack_layout = QtWidgets.QVBoxLayout(stack_container)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(0)
        stack_layout.addWidget(self.sidebar_breadcrumb)
        stack_layout.addWidget(self.sidebar_stack, stretch=1)

        sidebar_layout.addWidget(stack_container)
        
        self._restore_sidebar_mode()
        return sidebar_container
    
    def _on_sidebar_action_triggered(self, action_idx: int) -> None:
        """Handle sidebar action trigger with toggle behavior.
        
        Toggle logic:
        - If clicking the currently active action: collapse/expand sidebar
        - If clicking a different action: switch to that panel (and expand if collapsed)
        """
        if not self.sidebar_actions or action_idx >= len(self.sidebar_actions):
            return
        
        # Get the stack index for this action
        stack_idx = self.sidebar_panel_indices.get(action_idx, -1)
        if stack_idx == -1:  # Playback panel (no stack widget)
            # Just check the action, don't change stack
            for i, act in enumerate(self.sidebar_actions):
                act.setChecked(i == action_idx)
            return
        
        # Check if this is the currently active panel
        current_stack_idx = self.sidebar_stack.currentIndex()
        is_current_panel = (stack_idx == current_stack_idx)
        is_visible = self.sidebar_stack.isVisible()
        
        if is_current_panel and is_visible:
            # Clicking same panel: collapse sidebar
            self._collapse_sidebar()
        else:
            # Clicking different panel or sidebar is collapsed: switch and expand
            if not is_visible:
                self._expand_sidebar()
            self._set_sidebar_mode(action_idx)

    def _setup_annotation_toolbar(self) -> None:
        """Add a right toolbar toggle for the annotation dock."""
        if getattr(self, "dock_annotations", None) is None:
            return

        bar = QtWidgets.QToolBar("Annotation Controls", self)
        bar.setObjectName("annotation_toolbar")
        bar.setOrientation(QtCore.Qt.Orientation.Vertical)
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        bar.setMovable(False)
        bar.setIconSize(QtCore.QSize(16, 16))

        act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "Annotations",
            self,
        )
        act.setObjectName("annotation_toolbar_toggle")
        act.setCheckable(True)
        act.setChecked(True)
        act.setToolTip("Show/hide annotation table")
        act.triggered.connect(self._toggle_annotation_dock)
        bar.addAction(act)
        suggest_act = getattr(self, "suggest_points_act", None)
        if suggest_act is not None:
            bar.addAction(suggest_act)
        suggest_image_act = getattr(self, "suggest_points_image_act", None)
        if suggest_image_act is not None:
            bar.addAction(suggest_image_act)
        accept_roi_act = getattr(self, "accept_suggestions_in_roi_act", None)
        if accept_roi_act is not None:
            bar.addAction(accept_roi_act)

        self.annotation_toolbar = bar
        self.annotation_toolbar_action = act

        self.addToolBar(QtCore.Qt.RightToolBarArea, bar)

        self.dock_annotations.visibilityChanged.connect(self._sync_annotation_toolbar)

    def _toggle_annotation_dock(self, checked: bool) -> None:
        """Show or hide the annotation dock when the toolbar toggles."""
        if getattr(self, "dock_annotations", None) is None:
            return
        self.dock_annotations.setVisible(checked)
        if checked:
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_annotations)
            self.dock_annotations.raise_()

    def _sync_annotation_toolbar(self, visible: bool) -> None:
        """Keep the toolbar toggle in sync with the annotation dock visibility."""
        action = getattr(self, "annotation_toolbar_action", None)
        if action is not None:
            action.blockSignals(True)
            action.setChecked(visible)
            action.blockSignals(False)
    
    def _collapse_sidebar(self) -> None:
        """Collapse sidebar to slim activity bar only."""
        if self.sidebar_stack and self.sidebar_stack.isVisible():
            self.sidebar_stack.setVisible(False)
            if getattr(self, "sidebar_breadcrumb", None) is not None:
                self.sidebar_breadcrumb.setVisible(False)
            self._sidebar_collapsed = True
            self._settings.setValue("sidebarCollapsed", True)
            self._apply_canvas_priority_layout()
    
    def _expand_sidebar(self) -> None:
        """Expand sidebar to show active panel."""
        if self.sidebar_stack and not self.sidebar_stack.isVisible():
            self.sidebar_stack.setVisible(True)
            if getattr(self, "sidebar_breadcrumb", None) is not None:
                self.sidebar_breadcrumb.setVisible(True)
            self._sidebar_collapsed = False
            self._settings.setValue("sidebarCollapsed", False)
            self._apply_canvas_priority_layout()

    def _build_annotate_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        vis_group = QtWidgets.QGroupBox("Annotation visibility")
        vis_layout = QtWidgets.QVBoxLayout(vis_group)
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        row = QtWidgets.QHBoxLayout()
        self.show_frame_chk = QtWidgets.QCheckBox("Frame")
        self.show_mean_chk = QtWidgets.QCheckBox("Mean")
        self.show_support_chk = QtWidgets.QCheckBox("Support")
        self.show_frame_chk.setChecked(True)
        self.show_mean_chk.setChecked(True)
        self.show_support_chk.setChecked(False)
        row.addWidget(self.show_frame_chk)
        row.addWidget(self.show_mean_chk)
        row.addWidget(self.show_support_chk)
        vis_layout.addWidget(self.show_ann_master_chk)
        vis_layout.addLayout(row)
        layout.addWidget(vis_group)
        label_group = QtWidgets.QGroupBox("Labels")
        label_layout = QtWidgets.QVBoxLayout(label_group)
        self.label_buttons = QtWidgets.QButtonGroup()
        # P3.5: Guard against empty label lists
        labels_to_display = self.labels if self.labels else ["Point", "Region"]
        for label in labels_to_display:
            btn = QtWidgets.QRadioButton(label)
            if label == self.current_label:
                btn.setChecked(True)
            self.label_buttons.addButton(btn)
            label_layout.addWidget(btn)
        layout.addWidget(label_group)

        scope_group = QtWidgets.QGroupBox("Annotation scope")
        scope_layout = QtWidgets.QVBoxLayout(scope_group)
        self.scope_group = QtWidgets.QButtonGroup()
        for label in ["Current slice", "All slices"]:
            btn = QtWidgets.QRadioButton(label)
            if label == "All slices":
                btn.setChecked(True)
            self.scope_group.addButton(btn)
            scope_layout.addWidget(btn)
        layout.addWidget(scope_group)

        target_group = QtWidgets.QGroupBox("Target panel")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        self.target_group = QtWidgets.QButtonGroup()
        for label in ["Frame", "Mean", "Support"]:
            btn = QtWidgets.QRadioButton(label)
            if label == "Mean":
                btn.setChecked(True)
            self.target_group.addButton(btn)
            target_layout.addWidget(btn)
        layout.addWidget(target_group)

        tool_group = QtWidgets.QGroupBox("Tools")
        tool_layout = QtWidgets.QVBoxLayout(tool_group)
        self.tool_label = QtWidgets.QLabel("Tool: Annotate")
        tool_layout.addWidget(self.tool_label)
        
        # ARCHITECTURAL FIX: Add profile_mode_chk to prevent AttributeError in _set_profile_mode()
        # This checkbox enables click-two-points line profile mode
        # Phase 2D: This should be part of ToolState dataclass
        self.profile_mode_chk = QtWidgets.QCheckBox("Profile mode (click two points)")
        self.profile_mode_chk.setChecked(False)
        tool_layout.addWidget(self.profile_mode_chk)
        
        layout.addWidget(tool_group)

        layout.addStretch(1)
        return panel

    def _build_analyze_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        toolbox = QtWidgets.QToolBox()
        toolbox.setContentsMargins(0, 0, 0, 0)

        roi_group = QtWidgets.QWidget()
        roi_layout = QtWidgets.QVBoxLayout(roi_group)
        roi_layout.setContentsMargins(6, 6, 6, 6)
        roi_layout.setSpacing(6)
        roi_reset = QtWidgets.QPushButton("Reset ROI")
        roi_show = QtWidgets.QPushButton("Show ROI Controls")
        roi_reset.clicked.connect(self._reset_roi)
        roi_show.clicked.connect(lambda: self.dock_roi.setVisible(True) if self.dock_roi else None)
        roi_layout.addWidget(roi_reset)
        roi_layout.addWidget(roi_show)

        analysis_group = QtWidgets.QWidget()
        analysis_layout = QtWidgets.QVBoxLayout(analysis_group)
        analysis_layout.setContentsMargins(6, 6, 6, 6)
        analysis_layout.setSpacing(6)
        line_btn = QtWidgets.QPushButton("Line Profiles")
        bleach_btn = QtWidgets.QPushButton("ROI Mean + Bleaching Fit")
        table_btn = QtWidgets.QPushButton("ROI Mean Table")
        line_btn.clicked.connect(self._show_profile_dialog)
        bleach_btn.clicked.connect(self._show_bleach_dialog)
        table_btn.clicked.connect(self._show_table_dialog)
        analysis_layout.addWidget(line_btn)
        analysis_layout.addWidget(bleach_btn)
        analysis_layout.addWidget(table_btn)

        export_group = QtWidgets.QWidget()
        export_layout = QtWidgets.QVBoxLayout(export_group)
        export_layout.setContentsMargins(6, 6, 6, 6)
        export_layout.setSpacing(6)
        export_csv = QtWidgets.QPushButton("Save CSV")
        export_json = QtWidgets.QPushButton("Save JSON")
        export_csv.clicked.connect(self._save_csv)
        export_json.clicked.connect(self._save_json)
        export_layout.addWidget(export_csv)
        export_layout.addWidget(export_json)

        experimental_group = QtWidgets.QWidget()
        experimental_layout = QtWidgets.QVBoxLayout(experimental_group)
        experimental_layout.setContentsMargins(6, 6, 6, 6)
        experimental_layout.setSpacing(6)
        experimental_layout.addWidget(QtWidgets.QLabel("No experimental tools yet."))
        experimental_layout.addStretch(1)

        toolbox.addItem(roi_group, "ROI")
        toolbox.addItem(analysis_group, "Bleaching / Profiles")
        toolbox.addItem(export_group, "Export")
        toolbox.addItem(experimental_group, "Experimental")

        layout.addWidget(toolbox)
        layout.addStretch(1)
        return panel

    def _setup_tool_router(self) -> None:
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
            set_status=self._set_status,
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
        toolbar = QtWidgets.QToolBar("Tools", self)
        toolbar.setObjectName("tools_toolbar")
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setMovable(True)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        self.tools_toolbar = toolbar

        group = QtWidgets.QActionGroup(self)
        group.setExclusive(True)
        icons = {
            Tool.PAN_ZOOM: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp),
            Tool.ANNOTATE_POINT: self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton
            ),
            Tool.ROI_BOX: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon),
            Tool.ROI_CIRCLE: self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DriveNetIcon
            ),
            Tool.ROI_EDIT: self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogListView
            ),
            Tool.PROFILE_LINE: self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView
            ),
            Tool.ERASER: self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton
            ),
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

    def _sync_nav_mode(self, tool: Tool) -> None:
        if self.toolbar is None:
            return
        if tool == Tool.PAN_ZOOM:
            if getattr(self.toolbar, "mode", "") != "pan/zoom":
                self.toolbar.pan()
        else:
            if getattr(self.toolbar, "mode", ""):
                self.toolbar.pan()

    def _set_roi_interactor_tool(self, tool: Tool) -> None:
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
        axes = self.renderer.axes if getattr(self, "renderer", None) is not None else {}
        target_map = {
            "frame": axes.get("frame"),
            "mean": axes.get("mean"),
            "support": axes.get("support"),
        }
        return target_map.get(self.annotate_target, axes.get("frame"))

    def _get_image_axes(self) -> Set[object]:
        if getattr(self, "renderer", None) is None:
            return set()
        return {ax for ax in self.renderer.axes.values() if ax is not None}

    def _set_roi_shape(self, shape: str) -> None:
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
        
        # Map action index to stack index (skip Playback)
        stack_idx = self.sidebar_panel_indices.get(idx, -1)
        if stack_idx == -1:
            # Playback panel (no stack widget), just update checked state
            for i, act in enumerate(self.sidebar_actions):
                act.setChecked(i == idx)
            return
        
        # Switch to the panel
        self.sidebar_stack.setCurrentIndex(stack_idx)
        self._settings.setValue("sidebarMode", idx)

        # Update breadcrumb label to match the selected panel
        if getattr(self, "sidebar_breadcrumb", None) is not None:
            label = self.sidebar_actions[idx].text()
            self.sidebar_breadcrumb.setText(self.sidebar_manager.breadcrumb_text(label))
        
        # Update action checked states
        for i, act in enumerate(self.sidebar_actions):
            act.setChecked(i == idx)

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

    def _apply_canvas_priority_layout(self) -> None:
        """Resize docks so the canvas remains the primary focus."""
        docks: List[QtWidgets.QDockWidget] = []
        sizes: List[int] = []

        sidebar_visible = getattr(self, "dock_sidebar", None) is not None and self.dock_sidebar.isVisible()
        annotations_visible = (
            getattr(self, "dock_annotations", None) is not None and self.dock_annotations.isVisible()
        )

        for key in self.sidebar_manager.dock_order(sidebar_visible, annotations_visible):
            if key == "sidebar":
                docks.append(self.dock_sidebar)
            elif key == "annotations":
                docks.append(self.dock_annotations)

        sizes = self.sidebar_manager.dock_sizes(
            sidebar_visible=sidebar_visible,
            annotations_visible=annotations_visible,
            collapsed=getattr(self, "_sidebar_collapsed", False),
        )

        if docks:
            self.resizeDocks(docks, sizes, QtCore.Qt.Orientation.Horizontal)

    def _set_sidebar_expanded(self, expanded: bool) -> None:
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

    def _collect_command_actions(self) -> List[QtWidgets.QAction]:
        actions: List[QtWidgets.QAction] = []
        seen = set()

        def _add_action(act: QtWidgets.QAction) -> None:
            if act in seen:
                return
            text = act.text().replace("&", "").strip()
            if not text:
                return
            seen.add(act)
            actions.append(act)

        def _walk_menu(menu: QtWidgets.QMenu) -> None:
            for act in menu.actions():
                if act.isSeparator():
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

        return actions

    def _show_command_palette(self) -> None:
        existing = getattr(self, "_command_palette_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        actions = self._collect_command_actions()
        dlg = QtWidgets.QDialog(self)
        self._command_palette_dialog = dlg
        dlg.setWindowTitle("Command Palette")
        dlg.setWindowModality(QtCore.Qt.NonModal)
        dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dlg.resize(520, 320)
        layout = QtWidgets.QVBoxLayout(dlg)
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Type a command...")
        listw = QtWidgets.QListWidget()
        layout.addWidget(search)
        layout.addWidget(listw)

        action_map: List[Tuple[str, QtWidgets.QAction]] = []
        for act in actions:
            label = act.text().replace("&", "").strip()
            action_map.append((label, act))

        def _populate(filter_text: str = "") -> None:
            listw.clear()
            for label, act in action_map:
                if filter_text and filter_text not in label.lower():
                    continue
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, act)
                if not act.isEnabled():
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
                listw.addItem(item)
            if listw.count():
                listw.setCurrentRow(0)

        def _activate() -> None:
            item = listw.currentItem()
            if item is None:
                return
            act = item.data(QtCore.Qt.UserRole)
            dlg.accept()
            if act is not None:
                act.trigger()

        _populate()
        search.textChanged.connect(lambda text: _populate(text.strip().lower()))
        search.returnPressed.connect(_activate)
        listw.itemActivated.connect(lambda _: _activate())
        dlg.finished.connect(lambda _code: setattr(self, "_command_palette_dialog", None))
        search.setFocus()
        dlg.open()

    def _apply_default_layout(self) -> None:
        """Save the initial layout as the default reset state."""
        self._apply_panel_defaults()
        self._default_geometry = self.saveGeometry()
        self._default_state = self.saveState()
        self._apply_canvas_priority_layout()

    def _restore_layout(self) -> None:
        """Restore the user's custom layout from QSettings if present."""
        geometry = self._settings.value("customGeometry", type=QtCore.QByteArray)
        state = self._settings.value("customState", type=QtCore.QByteArray)
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        if self.dock_sidebar is not None and not self.dock_sidebar.isVisible():
            self.dock_sidebar.setVisible(True)
        self._apply_canvas_priority_layout()

    def _save_layout(self) -> None:
        """Persist the current layout unless a preset is active."""
        if self._preset_active:
            return
        self._settings.setValue("customGeometry", self.saveGeometry())
        self._settings.setValue("customState", self.saveState())

    def _save_layout_default(self) -> None:
        """Save the current layout as the new default custom layout."""
        self._preset_active = False
        self._settings.setValue("customGeometry", self.saveGeometry())
        self._settings.setValue("customState", self.saveState())

    def _reset_layout(self) -> None:
        """Reset dock placement to PanelSpec defaults without removing docks."""
        self._apply_panel_defaults()
        self._preset_active = False
        self._apply_canvas_priority_layout()

    def apply_preset(self, name: str) -> None:
        """Apply a named layout preset without overwriting saved custom layout."""
        self._preset_active = True

        if name == "Default":
            # Default: sidebar on EXPLORE (index 0), annotation table visible on the right
            self._set_sidebar_mode(0)
            self._expand_sidebar()
            if self.dock_annotations is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_annotations)
                self.dock_annotations.setVisible(True)
            for dock in [
                self.dock_roi,
                self.dock_roi_manager,
                self.dock_results,
                self.dock_hist,
                self.dock_profile,
                self.dock_logs,
                self.dock_threshold,
                self.dock_particles,
            ]:
                if dock is not None:
                    dock.setVisible(False)
            self._apply_canvas_priority_layout()
            return

        if name == "Default_Legacy":
            if self._default_geometry is not None:
                self.restoreGeometry(self._default_geometry)
            if self._default_state is not None:
                self.restoreState(self._default_state)
            return

        if self.dock_sidebar is not None:
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dock_sidebar)
            self.dock_sidebar.setVisible(True)

        if name == "Minimal":
            # Minimal: sidebar collapsed, annotation table hidden
            self._collapse_sidebar()
            if self.dock_annotations is not None:
                self.dock_annotations.setVisible(False)
            for dock in [
                self.dock_roi,
                self.dock_roi_manager,
                self.dock_results,
                self.dock_threshold,
                self.dock_particles,
                self.dock_hist,
                self.dock_profile,
                self.dock_logs,
            ]:
                if dock is not None:
                    dock.setVisible(False)
            self._apply_canvas_priority_layout()
            return

        if name == "Annotate":
            # Annotate: sidebar on ANNOTATE (index 1), annotation table visible
            self._set_sidebar_mode(1)
            self._expand_sidebar()
            if self.dock_annotations is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_annotations)
                self.dock_annotations.setVisible(True)
            for dock in [
                self.dock_roi,
                self.dock_roi_manager,
                self.dock_results,
                self.dock_threshold,
                self.dock_particles,
                self.dock_hist,
                self.dock_profile,
                self.dock_logs,
            ]:
                if dock is not None:
                    dock.setVisible(False)
            return

        if name == "Analyze":
            # Analyze: sidebar on ANALYZE (index 5), results + threshold bottom, annotation table visible
            self._set_sidebar_mode(5)
            self._expand_sidebar()
            if self.dock_annotations is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_annotations)
                self.dock_annotations.setVisible(True)
            if self.dock_results is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_results)
                self.dock_results.setVisible(True)
            if self.dock_threshold is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_threshold)
                self.dock_threshold.setVisible(True)
                if self.dock_results is not None:
                    self.tabifyDockWidget(self.dock_results, self.dock_threshold)
            for dock in [
                self.dock_roi,
                self.dock_roi_manager,
                self.dock_particles,
                self.dock_hist,
                self.dock_profile,
                self.dock_logs,
            ]:
                if dock is not None:
                    dock.setVisible(False)
            if self.dock_orthoview is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_orthoview)
                self.dock_orthoview.setVisible(True)
            return

    def closeEvent(self, event) -> None:
        """Persist layout before closing the main window."""
        self._save_layout()
        for fig_name in ("hist_fig", "profile_fig"):
            fig = getattr(self, fig_name, None)
            if fig is not None:
                fig.clear()
        QtWidgets.QMainWindow.closeEvent(self, event)
