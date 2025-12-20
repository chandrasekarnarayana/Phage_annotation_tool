"""UI helpers for sidebar, tool routing, layout, and command palette."""

from __future__ import annotations

from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter


class UiExtrasMixin:
    """Mixin for sidebar pages, tools, and layout/command palette actions."""

    def _build_sidebar_stack(self) -> QtWidgets.QWidget:
        """Create the stacked sidebar and activity bar for mode switching."""
        self.sidebar_stack = QtWidgets.QStackedWidget()
        self.sidebar_stack.addWidget(self.explore_panel)
        self.sidebar_stack.addWidget(self.annotate_panel)
        self.sidebar_stack.addWidget(self._build_analyze_panel())

        bar = QtWidgets.QToolBar("Activity Bar", self)
        bar.setOrientation(QtCore.Qt.Orientation.Vertical)
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        bar.setMovable(False)
        bar.setIconSize(QtCore.QSize(20, 20))

        self.sidebar_actions = []
        explore_act = QtWidgets.QAction(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon), "Explore", self)
        annotate_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView), "Annotate", self
        )
        analyze_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView), "Analyze", self
        )
        for idx, act in enumerate([explore_act, annotate_act, analyze_act]):
            act.setCheckable(True)
            act.triggered.connect(lambda checked, i=idx: self._set_sidebar_mode(i))
            self.sidebar_actions.append(act)
            bar.addAction(act)
        explore_act.setChecked(True)

        sidebar_container = QtWidgets.QWidget()
        sidebar_layout = QtWidgets.QHBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(bar)
        sidebar_layout.addWidget(self.sidebar_stack)
        self._restore_sidebar_mode()
        return sidebar_container

    def _build_annotate_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        label_group = QtWidgets.QGroupBox("Labels")
        label_layout = QtWidgets.QVBoxLayout(label_group)
        self.label_buttons = QtWidgets.QButtonGroup()
        for label in self.labels:
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
        for label in ["Frame", "Mean", "Composite", "Support"]:
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
        self._set_tool(Tool.ANNOTATE_POINT)

    def _init_tool_bar(self) -> None:
        toolbar = QtWidgets.QToolBar("Tools", self)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setMovable(True)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)

        group = QtWidgets.QActionGroup(self)
        group.setExclusive(True)
        icons = {
            Tool.PAN_ZOOM: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp),
            Tool.ANNOTATE_POINT: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton),
            Tool.ROI_BOX: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon),
            Tool.ROI_CIRCLE: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DriveNetIcon),
            Tool.ROI_EDIT: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogListView),
            Tool.PROFILE_LINE: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
            Tool.ERASER: self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton),
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

    def _set_tool(self, tool: Tool) -> None:
        if self.tool_router is not None:
            self.tool_router.set_tool(tool)
        self.controller.set_tool(tool.value)
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
        target_map = {
            "frame": self.ax_frame,
            "mean": self.ax_mean,
            "comp": self.ax_comp,
            "support": self.ax_support,
        }
        return target_map.get(self.annotate_target, self.ax_frame)

    def _get_image_axes(self) -> Set[object]:
        return {ax for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std] if ax is not None}

    def _set_roi_shape(self, shape: str) -> None:
        self.roi_shape = shape
        buttons = self.roi_shape_group.buttons()
        if buttons:
            buttons[0].setChecked(shape == "box")
            if len(buttons) > 1:
                buttons[1].setChecked(shape == "circle")

    def _set_sidebar_mode(self, idx: int) -> None:
        if self.sidebar_stack is None:
            return
        self.sidebar_stack.setCurrentIndex(idx)
        self._settings.setValue("sidebarMode", idx)

    def _restore_sidebar_mode(self) -> None:
        idx = self._settings.value("sidebarMode", 0, type=int)
        if self.sidebar_stack is None or not self.sidebar_actions:
            return
        idx = max(0, min(idx, self.sidebar_stack.count() - 1))
        self.sidebar_actions[idx].setChecked(True)
        self.sidebar_stack.setCurrentIndex(idx)

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
        actions = self._collect_command_actions()
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Command Palette")
        dlg.setWindowModality(QtCore.Qt.ApplicationModal)
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
        search.setFocus()
        dlg.exec()

    def _apply_default_layout(self) -> None:
        """Save the initial layout as the default reset state."""
        self._apply_panel_defaults()
        self._default_geometry = self.saveGeometry()
        self._default_state = self.saveState()

    def _restore_layout(self) -> None:
        """Restore the user's custom layout from QSettings if present."""
        geometry = self._settings.value("customGeometry", type=QtCore.QByteArray)
        state = self._settings.value("customState", type=QtCore.QByteArray)
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

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

    def apply_preset(self, name: str) -> None:
        """Apply a named layout preset without overwriting saved custom layout."""
        self._preset_active = True
        if name == "Default":
            if self._default_geometry is not None:
                self.restoreGeometry(self._default_geometry)
            if self._default_state is not None:
                self.restoreState(self._default_state)
            return

        if self.dock_sidebar is not None:
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dock_sidebar)
            self.dock_sidebar.setVisible(True)

        if name == "Minimal":
            for dock in [
                self.dock_annotations,
                self.dock_roi,
                self.dock_hist,
                self.dock_profile,
                self.dock_logs,
                self.dock_orthoview,
            ]:
                if dock is not None:
                    dock.setVisible(False)
            return

        if name == "Annotate":
            if self.dock_annotations is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_annotations)
                self.dock_annotations.setVisible(True)
            if self.dock_roi is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_roi)
                self.dock_roi.setVisible(True)
                if self.dock_annotations is not None:
                    self.tabifyDockWidget(self.dock_annotations, self.dock_roi)
            if self.dock_hist is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_hist)
                self.dock_hist.setVisible(True)
            if self.dock_profile is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_profile)
                self.dock_profile.setVisible(True)
                if self.dock_hist is not None:
                    self.tabifyDockWidget(self.dock_hist, self.dock_profile)
            if self.dock_logs is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_logs)
                self.dock_logs.setVisible(True)
            if self.dock_orthoview is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_orthoview)
                self.dock_orthoview.setVisible(True)
            return

        if name == "Analyze":
            if self.dock_annotations is not None:
                self.dock_annotations.setVisible(False)
            if self.dock_roi is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_roi)
                self.dock_roi.setVisible(True)
            if self.dock_hist is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_hist)
                self.dock_hist.setVisible(True)
            if self.dock_profile is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_profile)
                self.dock_profile.setVisible(True)
                if self.dock_hist is not None:
                    self.tabifyDockWidget(self.dock_hist, self.dock_profile)
            if self.dock_logs is not None:
                self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_logs)
                self.dock_logs.setVisible(True)
            if self.dock_orthoview is not None:
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_orthoview)
                self.dock_orthoview.setVisible(True)

    def closeEvent(self, event) -> None:
        """Persist layout before closing the main window."""
        self._save_layout()
        super().closeEvent(event)
