"""UI helpers for sidebar, tool routing, layout, and command palette."""

from __future__ import annotations

from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.sidebar_manager import SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter


class _LogicalVisibilityLabel(QtWidgets.QLabel):
    """QLabel that reports logical visibility even when parent containers are hidden."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logical_visible = True

    def setVisible(self, visible: bool) -> None:  # noqa: N802 - Qt API
        self._logical_visible = bool(visible)
        super().setVisible(bool(visible))

    def isVisible(self) -> bool:  # noqa: N802 - Qt API
        if not self._logical_visible:
            return False
        return not self.isHidden()


class UiExtrasMixin:
    """Mixin for sidebar pages, tools, and layout/command palette actions."""

    def _install_delayed_micro_help(self, widget: QtWidgets.QWidget, text: str) -> None:
        """Register long-hover micro-help bubble (quiet, delayed)."""
        if widget is None:
            return
        timers = getattr(self, "_micro_help_timers", None)
        if timers is None:
            timers = {}
            self._micro_help_timers = timers
        payload = str(text).strip()
        if not payload:
            return
        if widget in timers:
            timers[widget].stop()
            try:
                timers[widget].deleteLater()
            except Exception:
                pass
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(850)

        def _show_tip() -> None:
            if widget is None or not widget.isVisible():
                return
            center = widget.rect().center()
            pos = widget.mapToGlobal(center)
            QtWidgets.QToolTip.showText(pos, payload, widget)

        timer.timeout.connect(_show_tip)
        timers[widget] = timer
        widget.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt API
        """Drive delayed micro-help display on long-hover."""
        timers = getattr(self, "_micro_help_timers", None)
        if isinstance(timers, dict) and obj in timers:
            ev_type = event.type()
            if ev_type == QtCore.QEvent.Type.Enter:
                timers[obj].start()
            elif ev_type in (
                QtCore.QEvent.Type.Leave,
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.FocusOut,
                QtCore.QEvent.Type.Hide,
            ):
                timers[obj].stop()
                QtWidgets.QToolTip.hideText()
        return QtWidgets.QMainWindow.eventFilter(self, obj, event)

    def _available_annotation_views(self) -> dict[str, bool]:
        """Return currently available canvas views for annotation visibility controls."""
        primary = getattr(self, "primary_image", None)
        has_stack = False
        if primary is not None and hasattr(primary, "shape"):
            try:
                shape = tuple(int(v) for v in primary.shape)
                has_stack = len(shape) >= 2 and int(shape[1]) > 1
            except Exception:
                has_stack = False
        support_available = (
            len(getattr(self, "images", []) or []) > 1
            and int(getattr(self, "support_image_idx", 0)) != int(getattr(self, "current_image_idx", 0))
        )
        return {
            "frame": True,
            "mean": bool(has_stack),
            "support": bool(support_available),
            "std": bool(has_stack),
        }

    def _refresh_annotation_view_controls(self) -> None:
        """Sync dynamic visible-view checklist and target constraints."""
        availability = self._available_annotation_views()
        checkboxes = dict(getattr(self, "_annotation_view_checkboxes", {}) or {})
        panel_actions = dict(getattr(self, "panel_actions", {}) or {})
        for key, chk in checkboxes.items():
            available = bool(availability.get(str(key), False))
            chk.setVisible(available)
            if not available:
                continue
            action = panel_actions.get(str(key))
            if action is not None:
                chk.blockSignals(True)
                chk.setChecked(bool(action.isChecked()))
                chk.blockSignals(False)
        self._refresh_annotation_target_constraints()

    def _refresh_annotation_target_constraints(self) -> None:
        """Enable/disable target choices based on currently available views."""
        availability = self._available_annotation_views()
        targets = dict(getattr(self, "_target_buttons", {}) or {})
        unavailable = []
        for key in ("frame", "mean", "support"):
            btn = targets.get(key)
            if btn is None:
                continue
            available = bool(availability.get(key, False))
            btn.setEnabled(available)
            if available:
                btn.setToolTip("")
            else:
                unavailable.append(btn.text())
                btn.setToolTip("Unavailable for current modality/view context")
        hint = getattr(self, "target_unavailable_hint_lbl", None)
        if hint is not None:
            if unavailable:
                hint.setText("Other targets unavailable for this modality.")
                hint.setVisible(True)
            else:
                hint.setVisible(False)
        current_target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        if not bool(availability.get(current_target, False)):
            frame_btn = targets.get("frame")
            if frame_btn is not None:
                frame_btn.setChecked(True)
            self.annotate_target = "frame"

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
        self.sidebar_breadcrumb.setText(self.sidebar_manager.breadcrumb_text("Annotate"))
        self.sidebar_breadcrumb.setStyleSheet("font-weight: 600; padding: 6px 8px;")
        
        # Use the 10-panel registry if sidebar_pages are built
        pages = getattr(self, "sidebar_pages", None)
        if pages:
            # Add all panel widgets to the stack.
            for idx, (label, icon, widget) in enumerate(pages):
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
            default_action_idx = 0
            for page_idx, (label, icon, widget) in enumerate(pages):
                act = QtWidgets.QAction(self.style().standardIcon(icon), label, self)
                act.setObjectName(f"sidebar_action_{label.lower().replace('/', '_').replace(' ', '_')}")
                act.setCheckable(True)
                act.setToolTip(label)
                if label == "Annotate":
                    default_action_idx = page_idx
                
                # Connect with toggle behavior
                act.triggered.connect(lambda checked, i=page_idx: self._on_sidebar_action_triggered(i))
                self.sidebar_actions.append(act)
                bar.addAction(act)
                
                # Map to stack index.
                self.sidebar_panel_indices[page_idx] = stack_idx
                stack_idx += 1
            
            # Default to Annotate page for annotation-first workflow.
            if self.sidebar_actions:
                self.sidebar_actions[default_action_idx].setChecked(True)
                stack_default_idx = self.sidebar_panel_indices.get(default_action_idx, 0)
                if stack_default_idx >= 0:
                    self.sidebar_stack.setCurrentIndex(stack_default_idx)
                self.sidebar_breadcrumb.setText(
                    self.sidebar_manager.breadcrumb_text(
                        self.sidebar_actions[default_action_idx].text()
                    )
                )
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
        if stack_idx < 0:
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
        """Add a fixed right icon rail that toggles inspect-side docks."""
        if getattr(self, "dock_annotations", None) is None:
            return

        bar = QtWidgets.QToolBar("Right Sidebar", self)
        bar.setObjectName("right_sidebar_toolbar")
        bar.setOrientation(QtCore.Qt.Orientation.Vertical)
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        bar.setMovable(False)
        bar.setIconSize(QtCore.QSize(16, 16))
        bar.setFloatable(False)
        bar.setAllowedAreas(QtCore.Qt.ToolBarArea.RightToolBarArea)

        table_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "Annotation Table",
            self,
        )
        table_act.setObjectName("right_sidebar_table_toggle")
        table_act.setCheckable(True)
        table_act.setChecked(True)
        table_act.setToolTip("Annotation Table")
        table_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("annotations")
        )
        bar.addAction(table_act)

        queue_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowRight),
            "Review Queue",
            self,
        )
        queue_act.setObjectName("right_sidebar_queue_toggle")
        queue_act.setCheckable(True)
        queue_act.setChecked(False)
        queue_act.setToolTip("Review Queue")
        queue_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("review_queue")
        )
        bar.addAction(queue_act)

        explain_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation),
            "Why This Suggestion?",
            self,
        )
        explain_act.setObjectName("right_sidebar_why_toggle")
        explain_act.setCheckable(True)
        explain_act.setChecked(False)
        explain_act.setToolTip("Why This Suggestion?")
        explain_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("suggestion_explain")
        )
        bar.addAction(explain_act)

        layers_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView),
            "Modality Layers",
            self,
        )
        layers_act.setObjectName("right_sidebar_layers_toggle")
        layers_act.setCheckable(True)
        layers_act.setChecked(False)
        layers_act.setToolTip("Modality Layers")
        layers_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("modality_layers")
        )
        bar.addAction(layers_act)

        advanced_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarMenuButton),
            "Advanced Analysis",
            self,
        )
        advanced_act.setObjectName("right_sidebar_advanced_toggle")
        advanced_act.setCheckable(True)
        advanced_act.setChecked(False)
        advanced_act.setToolTip("Advanced Analysis")
        advanced_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("advanced_analysis")
        )
        bar.addAction(advanced_act)

        self.annotation_toolbar = bar
        self.annotation_toolbar_action = table_act
        self.right_sidebar_actions = {
            "annotations": table_act,
            "review_queue": queue_act,
            "suggestion_explain": explain_act,
            "modality_layers": layers_act,
            "advanced_analysis": advanced_act,
        }

        self.addToolBar(QtCore.Qt.RightToolBarArea, bar)

        for panel_id in (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
        ):
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is not None:
                dock.visibilityChanged.connect(self._sync_annotation_toolbar)
        self._sync_annotation_toolbar(True)

    def _toggle_annotation_dock(self, checked: bool) -> None:
        """Show or hide the annotation dock when the toolbar toggles."""
        if getattr(self, "dock_annotations", None) is None:
            return
        self.set_panel_visible("annotations", bool(checked), source="annotation_toolbar")
        if checked:
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_annotations)
            self.dock_annotations.raise_()

    def _sync_annotation_toolbar(self, visible: bool) -> None:
        """Keep right-toolbar toggles in sync with inspect dock visibility."""
        _ = visible  # Qt signal arg; sync uses current dock states.
        actions = dict(getattr(self, "right_sidebar_actions", {}) or {})
        for panel_id, action in actions.items():
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is None:
                continue
            checked = bool(dock.isVisible())
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

    def _toggle_right_sidebar_panel(self, panel_id: str) -> None:
        """VSCode-like right rail behavior: select one panel or collapse current."""
        panel_id = str(panel_id)
        inspect_ids = [
            "annotations",
            "review_queue",
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
        ]
        target_dock = getattr(self, f"dock_{panel_id}", None)
        if target_dock is None:
            return
        any_other_visible = False
        for pid in inspect_ids:
            if pid == panel_id:
                continue
            dock = getattr(self, f"dock_{pid}", None)
            if dock is not None and dock.isVisible():
                any_other_visible = True
                break
        is_only_visible = bool(target_dock.isVisible()) and not any_other_visible
        if is_only_visible:
            self.set_panel_visible(panel_id, False, source="right_sidebar")
            self._sync_annotation_toolbar(False)
            return
        for pid in inspect_ids:
            self.set_panel_visible(pid, pid == panel_id, source="right_sidebar")
        target_dock.raise_()
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

    def _build_annotate_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        vis_group = QtWidgets.QGroupBox("Visible views")
        vis_layout = QtWidgets.QVBoxLayout(vis_group)
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        row = QtWidgets.QVBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._annotation_view_checkboxes = {}
        view_specs = [
            ("frame", "Frame"),
            ("mean", "Mean Projection"),
            ("support", "Support"),
            ("std", "Std Projection"),
        ]
        for key, label in view_specs:
            chk = QtWidgets.QCheckBox(label)
            act = getattr(self, "panel_actions", {}).get(key)
            chk.setChecked(bool(act.isChecked()) if act is not None else True)
            chk.toggled.connect(lambda checked, k=key: self._on_panel_toggle(k, bool(checked)))
            row.addWidget(chk)
            self._annotation_view_checkboxes[key] = chk
        self.show_frame_chk = self._annotation_view_checkboxes.get("frame")
        self.show_mean_chk = self._annotation_view_checkboxes.get("mean")
        self.show_support_chk = self._annotation_view_checkboxes.get("support")
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
        scope_buttons = self.scope_group.buttons()
        if len(scope_buttons) > 1:
            self._install_delayed_micro_help(
                scope_buttons[1],
                "Annotations will be applied to all Z planes.\nUse with caution.",
            )
        layout.addWidget(scope_group)

        target_group = QtWidgets.QGroupBox("Target panel")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        self.target_group = QtWidgets.QButtonGroup()
        self._target_buttons = {}
        for key, label in [("frame", "Frame"), ("mean", "Mean Projection"), ("support", "Support")]:
            btn = QtWidgets.QRadioButton(label)
            if key == "mean":
                btn.setChecked(True)
            self.target_group.addButton(btn)
            target_layout.addWidget(btn)
            self._target_buttons[key] = btn
        self.target_unavailable_hint_lbl = _LogicalVisibilityLabel("")
        self.target_unavailable_hint_lbl.setWordWrap(True)
        self.target_unavailable_hint_lbl.setStyleSheet("color: #546e7a; font-style: italic;")
        self.target_unavailable_hint_lbl.setVisible(False)
        target_layout.addWidget(self.target_unavailable_hint_lbl)
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
        self._install_delayed_micro_help(
            self.profile_mode_chk,
            "Profile mode:\nClick two points to extract an intensity profile\nalong the line between them.",
        )
        tool_layout.addWidget(self.profile_mode_chk)
        
        layout.addWidget(tool_group)

        layout.addStretch(1)
        self._refresh_annotation_view_controls()
        return panel

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
        self._set_status(f"Active label: {self.current_label}")
        self._update_status()

    def _toggle_focus_canvas_mode(self) -> None:
        """Canvas-dominant focus mode with true space reclaim."""
        right_ids = [
            "annotations",
            "review_queue",
            "suggestion_explain",
            "advanced_analysis",
            "modality_layers",
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
            self._set_status("Focus Canvas mode enabled.")
        else:
            self._set_right_handle_compact(False)
            self._expand_sidebar()
            for key, visible in dict(getattr(self, "_focus_canvas_prev_right", {}) or {}).items():
                self.set_panel_visible(key, bool(visible), source="focus_canvas_mode_restore")
            for key, visible in dict(getattr(self, "_focus_canvas_prev_bottom", {}) or {}).items():
                self.set_panel_visible(key, bool(visible), source="focus_canvas_mode_restore")
            self._set_status("Focus Canvas mode disabled.")
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
        roi_show.clicked.connect(lambda: self.set_panel_visible("roi", True, source="analyze_panel"))
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
        if tool == Tool.ANNOTATE_POINT and hasattr(self, "_set_right_dock_mode"):
            self._set_right_dock_mode("annotate")

    def _set_right_dock_mode(self, mode: str) -> None:
        """Mode-aware right dock behavior: annotate/review/inspect."""
        target = str(mode or "").strip().lower()
        right_ids = ("annotations", "review_queue", "suggestion_explain")
        if target == "annotate":
            for panel_id in right_ids:
                self.set_panel_visible(panel_id, False, source="mode_right_dock")
            self.set_panel_visible("review_queue", True, source="mode_right_dock")
            self._set_right_handle_compact(True)
            return
        if target == "review":
            self._set_right_handle_compact(False)
            self.set_panel_visible("review_queue", True, source="mode_right_dock")
            dock = getattr(self, "dock_review_queue", None)
            if dock is not None:
                dock.raise_()
            return
        if target == "inspect":
            self._set_right_handle_compact(False)
            self.set_panel_visible("suggestion_explain", True, source="mode_right_dock")
            dock = getattr(self, "dock_suggestion_explain", None)
            if dock is not None:
                dock.raise_()

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
            self.set_panel_visible("review_queue", True, source=f"assist_mode:{source}")
            self.set_panel_visible("suggestion_explain", True, source=f"assist_mode:{source}")
            if getattr(self, "dock_review_queue", None) is not None:
                self.dock_review_queue.raise_()
            self.statusBar().showMessage("Assist Mode enabled.", 2500)
            return
        # OFF: keep review queue available, but raise table and reduce inspect clutter.
        self.set_panel_visible("review_queue", True, source=f"assist_mode:{source}")
        self.set_panel_visible("suggestion_explain", False, source=f"assist_mode:{source}")
        if getattr(self, "dock_annotations", None) is not None:
            self.set_panel_visible("annotations", True, source=f"assist_mode:{source}")
            self.dock_annotations.raise_()
        self.statusBar().showMessage("Assist Mode disabled.", 2500)

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
        self._settings.setValue("sidebarMode", idx)

        # Update breadcrumb label to match the selected panel
        if getattr(self, "sidebar_breadcrumb", None) is not None:
            label = self.sidebar_actions[idx].text()
            self.sidebar_breadcrumb.setText(self.sidebar_manager.breadcrumb_text(label))
        
        # Update action checked states
        for i, act in enumerate(self.sidebar_actions):
            act.setChecked(i == idx)

    def _focus_playback_controls(self) -> None:
        """Focus playback controls in the bottom bar from sidebar launcher page."""
        slider = getattr(self, "t_slider", None)
        if slider is not None:
            slider.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
            self.statusBar().showMessage("Playback controls are active in the bottom bar.", 3500)

    def _collapse_sidebar_context_docks_for_stack_index(self, stack_idx: int) -> None:
        """Collapse context docks from previous mode; keep only mode-relevant side panels."""
        mode_label = ""
        for action_idx, mapped_idx in dict(getattr(self, "sidebar_panel_indices", {}) or {}).items():
            if int(mapped_idx) == int(stack_idx):
                actions = getattr(self, "sidebar_actions", []) or []
                if 0 <= int(action_idx) < len(actions):
                    mode_label = str(actions[int(action_idx)].text()).strip().lower()
                break
        mode_to_keep = {
            "annotate": {
                "annotations",
                "review_queue",
                "suggestion_explain",
                "advanced_analysis",
                "modality_layers",
            },
            "analyze": {"roi", "roi_manager", "results", "orthoview", "metadata"},
            "display": {"hist", "profile"},
            "playback": set(),
            "preferences": {"advanced_analysis"},
            "explore": set(),
            "roi/crop": {"roi", "roi_manager"},
            "results": {"results", "qc_issues"},
            "project": set(),
            "export": set(),
        }
        keep = set(mode_to_keep.get(mode_label, set()))
        managed = {
            "annotations",
            "review_queue",
            "suggestion_explain",
            "advanced_analysis",
            "modality_layers",
            "roi",
            "roi_manager",
            "results",
            "orthoview",
            "metadata",
            "hist",
            "profile",
        }
        for panel_id in managed:
            if panel_id in keep:
                continue
            if hasattr(self, "is_panel_pinned") and self.is_panel_pinned(panel_id):
                continue
            if hasattr(self, "get_panel_opened_by") and self.get_panel_opened_by(panel_id) == "user":
                continue
            self.set_panel_visible(panel_id, False, source="sidebar_mode_switch")

    def _sidebar_action_index_for_label(self, label: str) -> int:
        """Return sidebar action index by label, or -1 if not found."""
        want = str(label).strip().lower()
        aliases = {
            "playback": "playback settings",
            "results": "results hub",
        }
        want = aliases.get(want, want)
        for i, act in enumerate(getattr(self, "sidebar_actions", []) or []):
            if str(act.text()).strip().lower() == want:
                return i
        return -1

    def open_preferences(self, section: str | None = None) -> None:
        """Open Preferences page and optionally focus a specific section."""
        if getattr(self, "dock_sidebar", None) is not None:
            self.set_panel_visible("sidebar", True, source="open_preferences")
        self._expand_sidebar()
        pref_idx = self._sidebar_action_index_for_label("Preferences")
        if pref_idx >= 0:
            self._set_sidebar_mode(pref_idx)
        if section not in {"training_controls", "panel_policy"}:
            return

        if getattr(self, "settings_advanced_container", None) is not None:
            self.settings_advanced_container.setVisible(True)
        if getattr(self, "advanced_group", None) is not None:
            self.advanced_group.setChecked(True)
        if section == "panel_policy" and hasattr(self, "_refresh_panel_policy_controls"):
            self._refresh_panel_policy_controls()

        scroll = self.sidebar_stack.currentWidget() if self.sidebar_stack is not None else None
        if isinstance(scroll, QtWidgets.QScrollArea):
            target = (
                getattr(self, "panel_policy_group", None)
                if section == "panel_policy"
                else self.settings_advanced_container
            )
            if target is not None:
                scroll.ensureWidgetVisible(target, 0, 24)

        focus_widget = (
            getattr(self, "suggestion_auto_retrain_chk", None)
            if section == "training_controls"
            else getattr(self, "panel_policy_reset_btn", None)
        )
        if focus_widget is not None:
            focus_widget.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

        # Brief highlight to confirm navigation target.
        if getattr(self, "advanced_group", None) is not None:
            group = self.advanced_group
            prior_style = group.styleSheet()
            group.setStyleSheet(
                prior_style
                + "\nQGroupBox { border: 2px solid #42a5f5; border-radius: 4px; }"
            )
            QtCore.QTimer.singleShot(1500, lambda: group.setStyleSheet(prior_style))

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
        right_dock = None
        for attr in (
            "dock_annotations",
            "dock_review_queue",
            "dock_suggestion_explain",
            "dock_advanced_analysis",
            "dock_modality_layers",
        ):
            candidate = getattr(self, attr, None)
            if candidate is not None and candidate.isVisible():
                right_dock = candidate
                break
        annotations_visible = right_dock is not None

        for key in self.sidebar_manager.dock_order(sidebar_visible, annotations_visible):
            if key == "sidebar":
                docks.append(self.dock_sidebar)
            elif key == "annotations":
                docks.append(right_dock)

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
            if not act.isVisible():
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
        # Backward-compatible aliases for renamed sidebar pages.
        if not isinstance(getattr(self, "_sidebar_alias_actions", None), dict):
            self._sidebar_alias_actions = {}
        for alias, target in (("Playback", "Playback Settings"), ("Results", "Results Hub")):
            idx = self._sidebar_action_index_for_label(target)
            if idx < 0:
                continue
            alias_act = self._sidebar_alias_actions.get(alias)
            if alias_act is None:
                alias_act = QtWidgets.QAction(alias, self)
                alias_act.setObjectName(f"sidebar_alias_{alias.lower()}")
                self._sidebar_alias_actions[alias] = alias_act
            try:
                alias_act.triggered.disconnect()
            except Exception:
                pass
            alias_act.triggered.connect(
                lambda _checked=False, i=idx: self._on_sidebar_action_triggered(i)
            )
            _add_action(alias_act)

        if self.command_palette_act is not None:
            _add_action(self.command_palette_act)
        if self.reset_view_act is not None:
            _add_action(self.reset_view_act)
        for act in dict(getattr(self, "panel_open_actions", {}) or {}).values():
            _add_action(act)

        return actions

    def _show_command_palette(self) -> None:
        self._show_command_palette_with_query("")

    def _show_panel_switcher(self) -> None:
        """Open command palette in panel-only mode."""
        self._show_command_palette_with_query("panel ")

    def _show_command_palette_with_query(self, initial_query: str = "") -> None:
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
        rationale_lbl = QtWidgets.QLabel("")
        rationale_lbl.setStyleSheet("color: #666666;")
        layout.addWidget(search)
        layout.addWidget(listw)
        layout.addWidget(rationale_lbl)

        action_map: List[Tuple[str, QtWidgets.QAction, str]] = []
        for act in actions:
            label = act.text().replace("&", "").strip()
            object_name = str(act.objectName() or "")
            search_blob = label.lower()
            if object_name.startswith("open_panel_"):
                panel_id = object_name.replace("open_panel_", "", 1)
                panel_specs = dict(getattr(self, "panel_specs_by_id", {}) or {})
                spec = panel_specs.get(panel_id)
                if spec is not None:
                    label = f"{label} [{str(spec.bucket).title()}]"
                    aliases = tuple(getattr(spec, "search_aliases", ()) or ())
                    if aliases:
                        search_blob = f"{search_blob} " + " ".join(str(a).lower() for a in aliases)
            action_map.append((label, act, search_blob))

        if not hasattr(self, "_command_usage_count"):
            self._command_usage_count = {}
        if not hasattr(self, "_command_last_used_ts"):
            self._command_last_used_ts = {}

        def _current_palette_mode() -> str:
            if getattr(self, "dock_review_queue", None) is not None and self.dock_review_queue.isVisible():
                return "review"
            return "annotate"

        mode_keywords = {
            "review": ("review", "queue", "qc", "issue", "approve", "assign", "reject"),
            "annotate": ("annotate", "point", "label", "roi", "slice", "frame", "accept"),
        }

        import time

        def _score(label: str, act: QtWidgets.QAction, filter_text: str) -> float:
            key = str(act.objectName() or label)
            usage = float(self._command_usage_count.get(key, 0))
            last_ts = float(self._command_last_used_ts.get(key, 0.0))
            age_sec = max(0.0, float(time.time()) - last_ts) if last_ts > 0 else 1e9
            recency_bonus = max(0.0, 1000.0 - min(1000.0, age_sec))
            score = usage * 3.0 + recency_bonus
            mode = _current_palette_mode()
            low = label.lower()
            if any(k in low for k in mode_keywords.get(mode, ())):
                score += 10.0
            if filter_text:
                if low.startswith(filter_text):
                    score += 30.0
                elif filter_text in low:
                    score += 10.0
            return score

        def _populate(filter_text: str = "") -> None:
            listw.clear()
            panel_only = False
            filter_expr = filter_text
            if filter_text.startswith("panel "):
                panel_only = True
                filter_expr = filter_text[len("panel "):].strip()
            ranked = sorted(
                action_map,
                key=lambda row: _score(row[0], row[1], filter_text),
                reverse=True,
            )
            for label, act, search_blob in ranked:
                object_name = str(act.objectName() or "")
                if panel_only and not object_name.startswith("open_panel_"):
                    continue
                if filter_expr and filter_expr not in search_blob:
                    continue
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, act)
                if not act.isEnabled():
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
                listw.addItem(item)
            if listw.count():
                listw.setCurrentRow(0)
            mode = _current_palette_mode()
            if panel_only:
                rationale_lbl.setText("Panel switcher mode: searching panel commands only.")
            else:
                rationale_lbl.setText(
                    f"Ranking: frequency + recency + mode boost ({mode}). "
                    "Review mode boosts review/QC commands."
                )

        def _activate() -> None:
            item = listw.currentItem()
            if item is None:
                return
            act = item.data(QtCore.Qt.UserRole)
            dlg.accept()
            if act is not None:
                key = str(act.objectName() or act.text().replace("&", "").strip())
                self._command_usage_count[key] = int(self._command_usage_count.get(key, 0) + 1)
                self._command_last_used_ts[key] = float(time.time())
                act.trigger()

        _populate(initial_query.strip().lower())
        search.textChanged.connect(lambda text: _populate(text.strip().lower()))
        search.returnPressed.connect(_activate)
        listw.itemActivated.connect(lambda _: _activate())
        dlg.finished.connect(lambda _code: setattr(self, "_command_palette_dialog", None))
        if initial_query:
            search.setText(initial_query)
            search.selectAll()
        search.setFocus()
        dlg.open()

    def _toggle_review_context_pack(self) -> None:
        """One-click toggle for Table + Queue + Why review context pack."""
        keys = ("annotations", "review_queue", "suggestion_explain", "modality_layers")
        visible_now = [
            bool(getattr(self, "panel_docks", {}).get(k).isVisible())
            for k in keys
            if getattr(self, "panel_docks", {}).get(k) is not None
        ]
        pack_on = not all(visible_now)
        if pack_on:
            for key in keys:
                self.set_panel_visible(key, True, source="review_context_pack")
            if getattr(self, "dock_review_queue", None) is not None:
                self.dock_review_queue.raise_()
            self._set_status("Review Context Pack enabled.")
        else:
            self.set_panel_visible("annotations", True, source="review_context_pack")
            self.set_panel_visible("review_queue", False, source="review_context_pack")
            self.set_panel_visible("suggestion_explain", False, source="review_context_pack")
            self.set_panel_visible("modality_layers", False, source="review_context_pack")
            self._set_status("Review Context Pack collapsed to table.")

    def _apply_default_layout(self) -> None:
        """Save the initial layout as the default reset state."""
        self.apply_preset("Default")
        self._default_geometry = self.saveGeometry()
        self._default_state = self.saveState()
        self._preset_active = False
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
            self.set_panel_visible("sidebar", True, source="layout_restore")
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

    def _capture_layout_snapshot(self) -> None:
        """Capture one-step layout undo state before major layout changes."""
        self._layout_prev_geometry = self.saveGeometry()
        self._layout_prev_state = self.saveState()
        act = getattr(self, "undo_layout_change_act", None)
        if act is not None:
            act.setEnabled(True)

    def _undo_layout_change(self) -> None:
        """Restore the previous saved layout snapshot once."""
        geometry = getattr(self, "_layout_prev_geometry", None)
        state = getattr(self, "_layout_prev_state", None)
        if geometry is None or state is None:
            return
        self.restoreGeometry(geometry)
        self.restoreState(state)
        self._apply_canvas_priority_layout()
        self._layout_prev_geometry = None
        self._layout_prev_state = None
        act = getattr(self, "undo_layout_change_act", None)
        if act is not None:
            act.setEnabled(False)
        self.statusBar().showMessage("Layout restored.", 3000)

    def _reset_layout(self) -> None:
        """Reset dock placement to PanelSpec defaults without removing docks."""
        self._capture_layout_snapshot()
        self._apply_panel_defaults()
        self._preset_active = False
        self._apply_canvas_priority_layout()
        self.statusBar().showMessage("Layout changed. Use Layout > Layouts > Undo Layout Change.", 8000)

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
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is not None:
                self.addDockWidget(area, dock)

        # Canonical geometry targets for key presets.
        _dock_to_area("sidebar", QtCore.Qt.LeftDockWidgetArea)
        if name in {"Default", "Annotate", "Analyze", "Assist Expert"}:
            _dock_to_area("annotations", QtCore.Qt.RightDockWidgetArea)
            _dock_to_area("review_queue", QtCore.Qt.RightDockWidgetArea)
        if name in {"Analyze", "Assist Expert"}:
            _dock_to_area("qc_issues", QtCore.Qt.BottomDockWidgetArea)
        if name == "Analyze":
            _dock_to_area("results", QtCore.Qt.BottomDockWidgetArea)
            _dock_to_area("threshold", QtCore.Qt.BottomDockWidgetArea)
            if self.dock_results is not None and self.dock_threshold is not None:
                self.tabifyDockWidget(self.dock_results, self.dock_threshold)
            _dock_to_area("orthoview", QtCore.Qt.RightDockWidgetArea)
        if name == "Assist Expert":
            _dock_to_area("suggestion_explain", QtCore.Qt.RightDockWidgetArea)
            _dock_to_area("modality_layers", QtCore.Qt.RightDockWidgetArea)

        preset_visibility: dict[str, dict[str, bool]] = {
            "Default": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": False,
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
                "modality_layers": False,
                "orthoview": False,
            },
            "Minimal": {
                "sidebar": True,
                "annotations": False,
                "review_queue": False,
                "suggestion_explain": False,
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
                "modality_layers": False,
                "orthoview": False,
            },
            "Annotate": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": False,
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
                "modality_layers": False,
                "orthoview": False,
            },
            "Analyze": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": False,
                "advanced_analysis": False,
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
                "modality_layers": False,
            },
            "Assist Expert": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": True,
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
                "modality_layers": True,
                "orthoview": False,
            },
        }

        if name == "Default":
            self._set_sidebar_mode(0)
            self._collapse_sidebar()
        elif name == "Minimal":
            self._collapse_sidebar()
        elif name == "Annotate":
            self._set_sidebar_mode(1)
            self._expand_sidebar()
        elif name == "Analyze":
            self._set_sidebar_mode(5)
            self._expand_sidebar()
        elif name == "Assist Expert":
            self._set_sidebar_mode(1)
            self._collapse_sidebar()
        else:
            return

        preset = preset_visibility.get(name)
        if preset is not None:
            self.apply_panel_visibility_preset(preset, source=f"preset:{name.lower().replace(' ', '_')}")
        if name == "Default":
            for key in ("annotations", "suggestion_explain", "advanced_analysis", "modality_layers"):
                self.set_panel_visible(key, False, source="preset:default_canvas_home")
            self.set_panel_visible("review_queue", True, source="preset:default_canvas_home")
            self._set_right_handle_compact(True)
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
        self.statusBar().showMessage(
            "Layout changed. Use Layout > Layouts > Undo Layout Change.",
            8000,
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
        for fig_name in ("hist_fig", "profile_fig"):
            fig = getattr(self, fig_name, None)
            if fig is not None:
                fig.clear()
        QtWidgets.QMainWindow.closeEvent(self, event)
