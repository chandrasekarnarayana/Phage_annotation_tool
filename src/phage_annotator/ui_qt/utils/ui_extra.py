"""UI helpers for sidebar, tool routing, layout, and command palette."""

from __future__ import annotations

from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager
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
                try:
                    QtWidgets.QToolTip.hideText()
                except Exception:
                    pass
        return QtWidgets.QMainWindow.eventFilter(self, obj, event)

    def _clear_all_tooltips(self) -> None:
        """Clear any lingering tooltips from the screen."""
        try:
            QtWidgets.QToolTip.hideText()
        except Exception:
            pass
        # Also stop any pending micro-help timers
        timers = getattr(self, "_micro_help_timers", None)
        if isinstance(timers, dict):
            for timer in timers.values():
                try:
                    timer.stop()
                except Exception:
                    pass

    def _available_annotation_views(self) -> dict[str, bool]:
        """Return currently available canvas views for annotation visibility controls."""
        table = getattr(self, "lazy_modality_table", None)
        availability: dict[str, bool] = {}
        if table is not None and table.rowCount() > 0:
            for row in range(table.rowCount()):
                name_item = table.item(row, 3)
                if name_item is None:
                    continue
                role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
                panel_key = ""
                if isinstance(role_data, str):
                    role_text = str(role_data)
                    if role_text.startswith("builtin:"):
                        panel_key = role_text.split(":", 1)[1]
                    elif role_text.startswith("modality_"):
                        panel_key = role_text
                else:
                    try:
                        panel_key = self._panel_key_for_modality_idx(int(role_data))
                    except Exception:
                        panel_key = ""
                if not panel_key:
                    continue
                visible_chk = table.cellWidget(row, 1)
                is_selected_visible = bool(
                    isinstance(visible_chk, QtWidgets.QCheckBox) and visible_chk.isChecked()
                )
                availability[str(panel_key)] = is_selected_visible
            if availability:
                return availability
        panel_visibility = dict(getattr(self, "_panel_visibility", {}) or {})
        availability = {}
        for key, visible in panel_visibility.items():
            k = str(key)
            if k.startswith("modality_"):
                availability[k] = bool(visible)
        return availability

    def _set_lazy_row_visible_state(self, panel_key: str, checked: bool) -> None:
        """Mirror panel visibility changes back into lazy modality table checkboxes."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        panel_key = str(panel_key)
        for row in range(table.rowCount()):
            name_item = table.item(row, 3)
            if name_item is None:
                continue
            role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
            row_key = ""
            if isinstance(role_data, str):
                role_text = str(role_data)
                if role_text.startswith("builtin:"):
                    row_key = role_text.split(":", 1)[1]
                elif role_text.startswith("modality_"):
                    row_key = role_text
            else:
                try:
                    row_key = self._panel_key_for_modality_idx(int(role_data))
                except Exception:
                    row_key = ""
            if row_key != panel_key:
                continue
            chk = table.cellWidget(row, 1)
            if isinstance(chk, QtWidgets.QCheckBox) and chk.isChecked() != bool(checked):
                chk.blockSignals(True)
                chk.setChecked(bool(checked))
                chk.blockSignals(False)
            break

    def _set_lazy_row_points_state(self, panel_key: str, checked: bool) -> None:
        """Mirror annotation point visibility changes into lazy-table Pts checkboxes."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        panel_key = str(panel_key)
        for row in range(table.rowCount()):
            name_item = table.item(row, 3)
            if name_item is None:
                continue
            role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
            row_key = ""
            if isinstance(role_data, str):
                role_text = str(role_data)
                if role_text.startswith("builtin:"):
                    row_key = role_text.split(":", 1)[1]
                elif role_text.startswith("modality_"):
                    row_key = role_text
            else:
                try:
                    row_key = self._panel_key_for_modality_idx(int(role_data))
                except Exception:
                    row_key = ""
            if row_key != panel_key:
                continue
            chk = table.cellWidget(row, 2)
            if isinstance(chk, QtWidgets.QCheckBox) and chk.isChecked() != bool(checked):
                chk.blockSignals(True)
                chk.setChecked(bool(checked))
                chk.blockSignals(False)
            break

    def _lazy_annotation_rows(self) -> list[tuple[str, str]]:
        """Return (panel_key, display_name) rows from lazy table in exact visible order."""
        table = getattr(self, "lazy_modality_table", None)
        rows: list[tuple[str, str]] = []
        if table is None:
            return rows
        for row in range(table.rowCount()):
            name_item = table.item(row, 3)
            if name_item is None:
                continue
            role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
            panel_key = ""
            if isinstance(role_data, str):
                role_text = str(role_data)
                if role_text.startswith("builtin:"):
                    panel_key = role_text.split(":", 1)[1]
                elif role_text.startswith("modality_"):
                    panel_key = role_text
            else:
                try:
                    panel_key = self._panel_key_for_modality_idx(int(role_data))
                except Exception:
                    panel_key = ""
            if not panel_key:
                continue
            display_name = str(name_item.text()).strip() or str(panel_key)
            rows.append((str(panel_key), display_name))
        return rows

    def _refresh_annotation_view_controls(self) -> None:
        """Sync dynamic visible-view checklist and target constraints."""
        availability = self._available_annotation_views()
        layout = getattr(self, "_annotation_view_rows_layout", None)
        if layout is None:
            return
        # Rebuild from lazy rows so order/naming is exactly mirrored.
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        checkboxes: dict[str, QtWidgets.QCheckBox] = {}
        ordered_rows = self._lazy_annotation_rows()
        if not ordered_rows:
            labels = self._annotation_view_labels()
            ordered_rows = [(k, labels.get(k, k)) for k in availability.keys()]
        for key, label in ordered_rows:
            if not bool(availability.get(str(key), False)):
                continue
            chk = QtWidgets.QCheckBox(str(label))
            chk.toggled.connect(
                lambda checked, k=str(key): self._on_annotation_panel_toggle(k, bool(checked))
            )
            layout.addWidget(chk)
            checkboxes[str(key)] = chk
        self._annotation_view_checkboxes = checkboxes
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        for key, chk in checkboxes.items():
            available = bool(availability.get(str(key), False))
            chk.setVisible(bool(available))
            chk.blockSignals(True)
            chk.setChecked(bool(point_vis.get(str(key), True)))
            chk.blockSignals(False)
        self.show_frame_chk = None
        self.show_mean_chk = None
        self.show_support_chk = None
        self._refresh_annotation_target_constraints()

    def _annotation_view_labels(self) -> dict[str, str]:
        """Return dynamic labels for annotation views."""
        labels = {}
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        for key, modality in panel_map.items():
            if str(key).startswith("modality_"):
                labels[str(key)] = str(getattr(modality, "display_name", key))
        for key, name in self._lazy_annotation_rows():
            labels.setdefault(str(key), str(name))
        return labels

    def _default_panel_key(self) -> str:
        """Return preferred annotation/render target panel key."""
        rows = self._lazy_annotation_rows()
        if rows:
            return str(rows[0][0])
        for key, visible in dict(getattr(self, "_panel_visibility", {}) or {}).items():
            if str(key).startswith("modality_") and bool(visible):
                return str(key)
        return "modality_0"

    def _image_index_from_id(self, image_id: int) -> int:
        """Resolve loaded image id to list index; fallback to current index."""
        target = int(image_id)
        images = list(getattr(self, "images", []) or [])
        for idx, img in enumerate(images):
            try:
                if int(getattr(img, "id", -1)) == target:
                    return idx
            except Exception:
                continue
        return int(getattr(self, "current_image_idx", 0))

    def _refresh_annotation_target_constraints(self) -> None:
        """Enable target choices based on currently available visible views."""
        availability = self._available_annotation_views()
        combo = getattr(self, "annotate_target_combo", None)
        labels = self._annotation_view_labels()
        if combo is None:
            return
        current_target = str(getattr(self, "annotate_target", self._default_panel_key())).strip().lower()
        combo.blockSignals(True)
        combo.clear()
        for key, label in self._lazy_annotation_rows():
            if not bool(availability.get(str(key), False)):
                continue
            combo.addItem(labels.get(str(key), str(label)), str(key))
        combo.blockSignals(False)
        if combo.count() <= 0:
            hint = getattr(self, "target_unavailable_hint_lbl", None)
            if hint is not None:
                hint.setText("No visible target view. Enable at least one view in Lazy Loading.")
                hint.setVisible(True)
            self.annotate_target = ""
            return
        idx = combo.findData(current_target)
        if idx < 0:
            idx = 0
            self.annotate_target = str(combo.itemData(0))
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        badge = getattr(self, "target_state_badge_lbl", None)
        if badge is not None:
            badge.setText(f"Write target: {combo.currentText()}")
        hint = getattr(self, "target_unavailable_hint_lbl", None)
        if hint is not None:
            hint.setVisible(False)

    def _on_annotation_panel_toggle(self, panel_key: str, checked: bool) -> None:
        """Toggle whether annotations are rendered on a specific visible panel."""
        key = str(panel_key or "").strip()
        if not key:
            return
        current_target = str(getattr(self, "annotate_target", self._default_panel_key())).strip().lower()
        if key == current_target and not bool(checked):
            chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(key)
            if chk is not None:
                chk.blockSignals(True)
                chk.setChecked(True)
                chk.blockSignals(False)
            self._set_status("Target view must show points while annotating.")
            return
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        point_vis[key] = bool(checked)
        self._annotation_panel_visibility = point_vis
        if hasattr(self, "_set_lazy_row_points_state"):
            self._set_lazy_row_points_state(key, bool(checked))
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        if hasattr(self, "_set_lazy_apply_button_state"):
            self._set_lazy_apply_button_state()
        self._refresh_image()

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
        
        # Right sidebar expand/collapse state
        self._right_sidebar_expanded = True
        self._right_sidebar_collapsed = False
        self._right_sidebar_last_width = None
        
        left_default = int(self._settings.value("leftSidebarDefaultWidth", 300, type=int))
        right_default = int(self._settings.value("rightSidebarDefaultWidth", 420, type=int))
        self.sidebar_manager = SidebarManager(
            SidebarLayoutConfig(
                expanded_width=max(220, left_default),
                annotations_width=max(220, right_default),
            )
        )
        
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
        bar.setIconSize(QtCore.QSize(20, 20))
        bar.setFixedWidth(getattr(self, "_sidebar_bar_width", 38))
        bar.setStyleSheet(
            "QToolBar#right_sidebar_toolbar {"
            " spacing: 3px; padding-top: 4px; border-left: 1px solid #d0d0d0; background: #f9fafb; }"
            "QToolBar#right_sidebar_toolbar QToolButton {"
            " margin: 1px; padding: 4px; min-width: 30px; min-height: 30px; border-radius: 4px; }"
        )
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

        status_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation),
            "Status Details",
            self,
        )
        status_act.setObjectName("right_sidebar_status_toggle")
        status_act.setCheckable(True)
        status_act.setChecked(False)
        status_act.setToolTip("Status Details")
        status_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("status_details")
        )
        bar.addAction(status_act)

        relink_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon),
            "Project Relink",
            self,
        )
        relink_act.setObjectName("right_sidebar_relink_toggle")
        relink_act.setCheckable(True)
        relink_act.setChecked(False)
        relink_act.setToolTip("Project Relink")
        relink_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("project_relink")
        )
        bar.addAction(relink_act)

        # Add separator and collapse/expand toggle
        bar.addSeparator()
        collapse_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowLeft),
            "Collapse/Expand Sidebar",
            self,
        )
        collapse_act.setObjectName("right_sidebar_collapse_toggle")
        collapse_act.setToolTip("Collapse (←) or Expand (→) right sidebar")
        collapse_act.triggered.connect(self._toggle_right_sidebar_collapse)
        bar.addAction(collapse_act)
        self.right_sidebar_collapse_action = collapse_act

        self.annotation_toolbar = bar
        self.annotation_toolbar_action = table_act
        self.right_sidebar_actions = {
            "annotations": table_act,
            "review_queue": queue_act,
            "suggestion_explain": explain_act,
            "modality_layers": layers_act,
            "advanced_analysis": advanced_act,
            "status_details": status_act,
            "project_relink": relink_act,
        }

        self.addToolBar(QtCore.Qt.RightToolBarArea, bar)

        for panel_id in (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
            "status_details",
            "project_relink",
        ):
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is not None:
                dock.visibilityChanged.connect(self._sync_annotation_toolbar)
                dock.visibilityChanged.connect(lambda _v: self._capture_right_sidebar_width())
        self._ensure_right_sidebar_panels_not_tabified()
        self._sync_annotation_toolbar(True)

    def _capture_right_sidebar_width(self) -> None:
        """Persist right-sidebar open width for consistent reopen behavior."""
        for panel_id in (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
            "status_details",
            "project_relink",
        ):
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is None or not dock.isVisible():
                continue
            width = int(dock.width())
            if width > 80:
                self._right_sidebar_last_width = width
                if getattr(self, "_settings", None) is not None:
                    self._settings.setValue("rightSidebarDefaultWidth", width)
            break

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

    def _ensure_right_sidebar_panels_not_tabified(self) -> None:
        """Keep right inspect panels as standalone docks (never tab peers)."""
        panel_ids = (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
            "status_details",
            "project_relink",
        )
        for panel_id in panel_ids:
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is None:
                continue
            peers = list(self.tabifiedDockWidgets(dock) or [])
            if not peers:
                continue
            try:
                self.removeDockWidget(dock)
                self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
            except Exception:
                continue

    def _toggle_right_sidebar_panel(self, panel_id: str) -> None:
        """VSCode-like right rail behavior: select one panel or collapse current."""
        panel_id = str(panel_id)
        inspect_ids = [
            "annotations",
            "review_queue",
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
            "status_details",
            "project_relink",
        ]
        target_dock = getattr(self, f"dock_{panel_id}", None)
        if target_dock is None:
            return
        # Ensure right sidebar expands to normal width before activating a panel.
        if getattr(self, "_right_sidebar_collapsed", False):
            self._expand_right_sidebar()
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
            "suggestion_explain",
            "modality_layers",
            "advanced_analysis",
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
                    "suggestion_explain",
                    "modality_layers",
                    "advanced_analysis",
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

    def _build_annotate_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("annotate_sidebar_panel")
        panel.setStyleSheet(
            "#annotate_sidebar_panel QGroupBox {"
            " margin-top: 10px; border: 1px solid #e4e7eb; border-radius: 5px; padding-top: 4px; }"
            "#annotate_sidebar_panel QGroupBox::title {"
            " subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #263238; font-weight: 600; }"
            "#annotate_sidebar_panel QComboBox, #annotate_sidebar_panel QLineEdit { min-height: 24px; }"
            "#annotate_sidebar_panel QCheckBox, #annotate_sidebar_panel QRadioButton { min-height: 22px; }"
        )
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        vis_group = QtWidgets.QGroupBox("Visible views")
        vis_layout = QtWidgets.QVBoxLayout(vis_group)
        vis_layout.setContentsMargins(8, 8, 8, 8)
        vis_layout.setSpacing(6)
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        row = QtWidgets.QVBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._annotation_view_rows_layout = row
        self._annotation_view_checkboxes = {}
        view_specs = [
            ("modality_0", "Modality 1"),
            ("modality_1", "Modality 2"),
        ]
        for key, label in view_specs:
            chk = QtWidgets.QCheckBox(label)
            act = getattr(self, "panel_actions", {}).get(key)
            chk.setChecked(bool(act.isChecked()) if act is not None else True)
            chk.toggled.connect(lambda checked, k=key: self._on_panel_toggle(k, bool(checked)))
            row.addWidget(chk)
            self._annotation_view_checkboxes[key] = chk
        self.show_frame_chk = None
        self.show_mean_chk = None
        self.show_support_chk = None
        vis_layout.addWidget(self.show_ann_master_chk)
        vis_layout.addLayout(row)
        layout.addWidget(vis_group)
        label_group = QtWidgets.QGroupBox("Labels")
        label_layout = QtWidgets.QVBoxLayout(label_group)
        label_layout.setContentsMargins(8, 8, 8, 8)
        label_layout.setSpacing(6)
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
        scope_layout.setContentsMargins(8, 8, 8, 8)
        scope_layout.setSpacing(6)
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

        target_group = QtWidgets.QGroupBox("Annotation target")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        target_layout.setContentsMargins(8, 8, 8, 8)
        target_layout.setSpacing(6)
        self.annotate_target_combo = QtWidgets.QComboBox(target_group)
        self.annotate_target_combo.setToolTip(
            "Choose the visible canvas view/modality where new points will be written."
        )
        target_layout.addWidget(self.annotate_target_combo)
        self.target_state_badge_lbl = QtWidgets.QLabel("Write target: -")
        self.target_state_badge_lbl.setStyleSheet(
            "background:#e8f0fe; color:#1d4e89; padding:3px 6px; border-radius:4px; font-weight:600;"
        )
        target_layout.addWidget(self.target_state_badge_lbl)
        self.target_unavailable_hint_lbl = _LogicalVisibilityLabel("")
        self.target_unavailable_hint_lbl.setWordWrap(True)
        self.target_unavailable_hint_lbl.setStyleSheet("color: #546e7a; font-style: italic;")
        self.target_unavailable_hint_lbl.setVisible(False)
        target_layout.addWidget(self.target_unavailable_hint_lbl)
        layout.addWidget(target_group)

        tool_group = QtWidgets.QGroupBox("Tools")
        tool_layout = QtWidgets.QVBoxLayout(tool_group)
        tool_layout.setContentsMargins(8, 8, 8, 8)
        tool_layout.setSpacing(6)
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
        current_target = str(
            getattr(self, "annotate_target", self._default_panel_key())
        ).strip().lower()
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
        self._refresh_image()

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
            "status_details",
            "project_relink",
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
        # Clear any lingering tooltips when switching tools
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
        right_ids = (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "status_details",
            "project_relink",
        )
        if target == "annotate":
            # Annotation-first default: keep table visible and focused.
            self._set_right_handle_compact(False)
            self.set_panel_visible("annotations", True, source="mode_right_dock")
            for panel_id in right_ids:
                if panel_id != "annotations":
                    self.set_panel_visible(panel_id, False, source="mode_right_dock")
            dock = getattr(self, "dock_annotations", None)
            if dock is not None:
                dock.setMinimumWidth(360)
                dock.raise_()
            if getattr(self, "_right_sidebar_collapsed", False):
                self._expand_right_sidebar()
            else:
                self._apply_canvas_priority_layout()
            return
        if target == "review":
            self._set_right_handle_compact(False)
            self.set_panel_visible("review_queue", True, source="mode_right_dock")
            for panel_id in right_ids:
                if panel_id != "review_queue":
                    self.set_panel_visible(panel_id, False, source="mode_right_dock")
            dock = getattr(self, "dock_review_queue", None)
            if dock is not None:
                dock.raise_()
            return
        if target == "inspect":
            self._set_right_handle_compact(False)
            self.set_panel_visible("suggestion_explain", True, source="mode_right_dock")
            for panel_id in right_ids:
                if panel_id != "suggestion_explain":
                    self.set_panel_visible(panel_id, False, source="mode_right_dock")
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
        target_key = str(getattr(self, "annotate_target", self._default_panel_key())).strip().lower()
        ax = axes.get(target_key)
        if ax is not None:
            return ax
        # Fallback to first available axis to keep annotation workflow operable.
        return next(iter(axes.values()), None)

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

    def _refresh_lazy_modality_table(self) -> None:
        """Populate lazy-loading modality/view table."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        self._migrate_builtin_views_to_modalities(manager)
        self._ensure_lazy_sync_group_keys()
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        hidden_base = set(getattr(self, "_lazy_hidden_base_panel_keys", set()) or set())
        for panel_key in ("modality_0", "modality_1"):
            if panel_key in hidden_base:
                self._panel_visibility[str(panel_key)] = False
        self._lazy_builtin_views = builtin
        projection_labels = {
            "raw": "Source Frame",
            "mean": "Mean",
            "median": "Median",
            "std": "Std",
            "min": "Min",
            "max": "Max",
        }
        table.blockSignals(True)
        table.setRowCount(0)
        saw_support = False
        all_modalities = list(manager.get_all_modalities())
        panel_order = dict(getattr(self, "_lazy_panel_order", {}) or {})
        next_order = max([int(v) for v in panel_order.values() if str(v).isdigit()] or [0]) + 1
        modality_rows = []
        for modality in all_modalities:
            panel_key = self._panel_key_for_modality_idx(int(modality.idx))
            if panel_key in hidden_base and int(modality.idx) <= 1:
                continue
            order_no = panel_order.get(panel_key)
            if not str(order_no).isdigit():
                order_no = next_order
                next_order += 1
                panel_order[panel_key] = int(order_no)
            modality_rows.append((int(order_no), int(modality.idx), panel_key, modality))
        self._lazy_panel_order = panel_order
        for order_no, _idx, panel_key, modality in sorted(modality_rows, key=lambda x: (int(x[0]), int(x[1]))):
            row = table.rowCount()
            table.insertRow(row)
            if panel_key == "modality_1":
                saw_support = True
            order_item = QtWidgets.QTableWidgetItem(str(int(order_no)))
            order_item.setData(QtCore.Qt.ItemDataRole.UserRole, int(modality.idx))
            table.setItem(row, 0, order_item)
            visible_chk = QtWidgets.QCheckBox(table)
            visible_chk.setChecked(bool(self._panel_visibility.get(panel_key, True)))
            visible_chk.toggled.connect(
                lambda checked, k=panel_key: self._on_panel_toggle(str(k), bool(checked))
            )
            table.setCellWidget(row, 1, visible_chk)
            pts_chk = QtWidgets.QCheckBox(table)
            pts_chk.setChecked(
                bool(dict(getattr(self, "_annotation_panel_visibility", {}) or {}).get(panel_key, True))
            )
            pts_chk.toggled.connect(
                lambda checked, k=panel_key: self._on_annotation_panel_toggle(str(k), bool(checked))
            )
            table.setCellWidget(row, 2, pts_chk)

            name_item = QtWidgets.QTableWidgetItem(str(modality.display_name))
            name_item.setData(QtCore.Qt.ItemDataRole.UserRole, int(modality.idx))
            table.setItem(row, 3, name_item)

            source_combo = QtWidgets.QComboBox(table)
            for img in getattr(self, "images", []) or []:
                source_combo.addItem(str(getattr(img, "name", f"Image {img.id}")), int(img.id))
            src_idx = max(0, source_combo.findData(int(modality.image_id)))
            source_combo.setCurrentIndex(src_idx)
            source_combo.currentIndexChanged.connect(
                lambda _i, mid=int(modality.idx), combo=source_combo: self._on_lazy_modality_source_changed(
                    mid, int(combo.currentData())
                )
            )
            table.setCellWidget(row, 4, source_combo)

            view_combo = QtWidgets.QComboBox(table)
            for projection in ("raw", "mean", "median", "std", "min", "max"):
                view_combo.addItem(str(projection_labels.get(projection, projection.title())), projection)
            proj_idx = max(0, view_combo.findData(str(modality.projection_type.value)))
            view_combo.setCurrentIndex(proj_idx)
            view_combo.currentIndexChanged.connect(
                lambda _i, mid=int(modality.idx), combo=view_combo: self._on_lazy_modality_projection_changed(
                    mid, str(combo.currentData())
                )
            )
            table.setCellWidget(row, 5, view_combo)
            group_item = QtWidgets.QTableWidgetItem(
                str(dict(getattr(self, "_lazy_modality_groups", {}) or {}).get(int(modality.idx), ""))
            )
            group_item.setData(QtCore.Qt.ItemDataRole.UserRole, int(modality.idx))
            table.setItem(row, 6, group_item)
            table.setCellWidget(row, 7, self._sync_mode_toolbutton(table, int(modality.idx), "contrast"))
            table.setCellWidget(row, 8, self._sync_mode_toolbutton(table, int(modality.idx), "zoom"))
            table.setCellWidget(row, 9, self._sync_mode_toolbutton(table, int(modality.idx), "playback"))

        # Remove stale dynamic panel visibility keys no longer represented by modalities.
        valid_dynamic_keys = {
            self._panel_key_for_modality_idx(int(modality.idx))
            for modality in manager.get_all_modalities()
        }
        for key in list(dict(getattr(self, "_panel_visibility", {}) or {}).keys()):
            k = str(key)
            if k.startswith("modality_") and k not in valid_dynamic_keys:
                self._panel_visibility.pop(k, None)

        table.blockSignals(False)
        table.resizeColumnsToContents()
        table.setColumnWidth(0, 40)
        table.setColumnWidth(1, 48)
        table.setColumnWidth(2, 36)
        if table.columnCount() >= 10:
            table.setColumnWidth(7, 28)
            table.setColumnWidth(8, 28)
            table.setColumnWidth(9, 28)
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()

    def _panel_key_for_modality_idx(self, modality_idx: int) -> str:
        """Map modality index to panel key used by renderer/sync list."""
        return f"modality_{int(modality_idx)}"

    def _panel_key_from_role_data(self, role_data) -> str:
        """Resolve lazy-table role payload (int or builtin:*) to panel key."""
        if isinstance(role_data, str):
            role_text = str(role_data).strip()
            if role_text.startswith("builtin:"):
                return role_text.split(":", 1)[1]
            if role_text.startswith("modality_"):
                return role_text
            return ""
        try:
            return self._panel_key_for_modality_idx(int(role_data))
        except Exception:
            return ""

    def _reorder_lazy_panel_by_no(self, panel_key: str, requested_no: int) -> None:
        """Move one panel key to requested 1-based position and renumber all rows."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        ordered_keys: list[str] = []
        for row in range(table.rowCount()):
            name_item = table.item(row, 3)
            if name_item is None:
                continue
            key = self._panel_key_from_role_data(name_item.data(QtCore.Qt.ItemDataRole.UserRole))
            if key:
                ordered_keys.append(str(key))
        if not ordered_keys or str(panel_key) not in ordered_keys:
            return
        keys = [k for k in ordered_keys if k != str(panel_key)]
        pos = max(1, int(requested_no))
        insert_at = min(len(keys), max(0, pos - 1))
        keys.insert(insert_at, str(panel_key))
        self._lazy_panel_order = {k: i + 1 for i, k in enumerate(keys)}

    def _migrate_builtin_views_to_modalities(self, manager) -> None:
        """One-time migration: convert builtin mean/std configs into regular modalities."""
        if bool(getattr(self, "_lazy_builtin_migrated", False)):
            return
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        migrated_any = False
        try:
            from phage_annotator.session.modality import ProjectionType
        except Exception:
            return
        existing = list(getattr(manager, "get_all_modalities", lambda: [])() or [])
        existing_keys = {
            (int(getattr(mod, "image_id", -1)), str(getattr(getattr(mod, "projection_type", None), "value", "raw")))
            for mod in existing
        }
        for key in ("mean", "std"):
            cfg = dict(builtin.get(key, {}) or {})
            if not cfg:
                continue
            image_id = int(cfg.get("image_id", getattr(getattr(self, "primary_image", None), "id", 0)))
            projection_key = str(cfg.get("projection", key)).strip().lower()
            try:
                projection = ProjectionType(projection_key)
            except Exception:
                projection = ProjectionType.MEAN if key == "mean" else ProjectionType.STD
            dedupe = (image_id, str(getattr(projection, "value", projection_key)))
            if dedupe in existing_keys:
                builtin.pop(key, None)
                continue
            name = str(cfg.get("name", "")).strip() or (
                "Mean Projection (Modality 1)" if key == "mean" else "Std Projection (Modality 1)"
            )
            try:
                modality = manager.add_modality(
                    image_id=image_id,
                    custom_name=name,
                    projection_type=projection,
                )
                self._panel_visibility[self._panel_key_for_modality_idx(int(modality.idx))] = True
                existing_keys.add(dedupe)
                migrated_any = True
                builtin.pop(key, None)
            except Exception:
                continue
        if migrated_any:
            self._lazy_builtin_views = builtin
        self._lazy_builtin_migrated = True

    def _next_numeric_sync_key(self, groups: dict) -> str:
        """Return next available positive integer sync key as string."""
        used = set()
        for value in (groups or {}).values():
            text = str(value or "").strip()
            if text.isdigit():
                used.add(int(text))
        key = 1
        while key in used:
            key += 1
        return str(key)

    def _sync_modes_for_role(self, role_key) -> dict[str, bool]:
        """Return sync mode flags for a modality/view role key."""
        modes = dict(getattr(self, "_lazy_sync_modes", {}) or {})
        current = dict(modes.get(role_key, {}) or {})
        normalized = {
            "contrast": bool(current.get("contrast", True)),
            "zoom": bool(current.get("zoom", True)),
            "playback": bool(current.get("playback", True)),
        }
        modes[role_key] = normalized
        self._lazy_sync_modes = modes
        return normalized

    def _set_sync_mode_for_role(self, role_key, mode_key: str, enabled: bool) -> None:
        """Update one sync mode flag for all rows in the same sync group."""
        key = str(mode_key).strip().lower()
        if key not in {"contrast", "zoom", "playback"}:
            return
        groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
        group_key = str(groups.get(role_key, "")).strip()
        target_roles = {role_key}
        if group_key.isdigit():
            target_roles = {rk for rk, gk in groups.items() if str(gk).strip() == group_key}
        modes = dict(getattr(self, "_lazy_sync_modes", {}) or {})
        for target_role in target_roles:
            row_modes = dict(modes.get(target_role, {}) or {})
            # Playback cannot be enabled for projection-only views (single-frame).
            if key == "playback" and bool(enabled) and self._is_single_frame_projection_role(target_role):
                row_modes[key] = False
            else:
                row_modes[key] = bool(enabled)
            modes[target_role] = {
                "contrast": bool(row_modes.get("contrast", True)),
                "zoom": bool(row_modes.get("zoom", True)),
                "playback": bool(row_modes.get("playback", True)),
            }
        self._lazy_sync_modes = modes
        self._sync_mode_widgets_for_roles(target_roles, key)
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()

    def _ensure_lazy_sync_modes(self) -> None:
        """Ensure each lazy row has explicit sync mode flags."""
        modes = dict(getattr(self, "_lazy_sync_modes", {}) or {})
        groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
        if getattr(self, "controller", None) is not None:
            from phage_annotator.session.migration import ensure_modality_system

            manager = ensure_modality_system(self.controller.session_state)
            for modality in manager.get_all_modalities():
                role_key = int(modality.idx)
                current = dict(modes.get(role_key, {}) or {})
                modes[role_key] = {
                    "contrast": bool(current.get("contrast", True)),
                    "zoom": bool(current.get("zoom", True)),
                    "playback": bool(current.get("playback", True)),
                }
        for builtin_key in ("builtin:support", "builtin:mean", "builtin:std"):
            if builtin_key not in groups:
                continue
            current = dict(modes.get(builtin_key, {}) or {})
            modes[builtin_key] = {
                "contrast": bool(current.get("contrast", True)),
                "zoom": bool(current.get("zoom", True)),
                "playback": bool(current.get("playback", True)),
            }
        # Force playback off for single-frame projection roles.
        for role_key, flags in list(modes.items()):
            row_modes = dict(flags or {})
            if self._is_single_frame_projection_role(role_key):
                row_modes["playback"] = False
            modes[role_key] = {
                "contrast": bool(row_modes.get("contrast", True)),
                "zoom": bool(row_modes.get("zoom", True)),
                "playback": bool(row_modes.get("playback", True)),
            }
        self._lazy_sync_modes = modes

    def _is_single_frame_projection_role(self, role_key) -> bool:
        """Return True when role represents projection-only (non-RAW) row."""
        try:
            role = role_key
            if isinstance(role, str) and role.startswith("builtin:"):
                panel_key = role.split(":", 1)[1]
                cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get(panel_key, {}) or {})
                projection_key = str(cfg.get("projection", panel_key)).strip().lower()
                return projection_key in {"mean", "median", "std", "min", "max"}
            if getattr(self, "controller", None) is None:
                return False
            from phage_annotator.session.migration import ensure_modality_system

            manager = ensure_modality_system(self.controller.session_state)
            modality = manager.get_modality(int(role))
            if modality is None:
                return False
            projection_key = str(getattr(getattr(modality, "projection_type", None), "value", "raw")).strip().lower()
            return projection_key in {"mean", "median", "std", "min", "max"}
        except Exception:
            return False

    def _sync_mode_toolbutton(self, table, role_key, mode_key: str):
        """Create lazy-table sync checkbox widget."""
        mk = str(mode_key).strip().lower()
        tooltip = {
            "contrast": "Sync contrast for this row's Sync Group",
            "zoom": "Sync zoom/pan for this row's Sync Group",
            "playback": "Sync playback for this row's Sync Group",
        }.get(mk, "Sync mode")
        chk = QtWidgets.QCheckBox(table)
        chk.setText("")
        chk.setToolTip(tooltip)
        chk.setProperty("syncMode", mk)
        chk.setProperty("roleKey", role_key)
        if mk == "playback" and self._is_single_frame_projection_role(role_key):
            chk.setChecked(False)
            chk.setEnabled(False)
            chk.setToolTip("Playback disabled for projection-only views (single-frame).")
        else:
            chk.setChecked(bool(self._sync_modes_for_role(role_key).get(mk, True)))
        chk.toggled.connect(
            lambda checked, rk=role_key, mode=mk: self._set_sync_mode_for_role(
                rk, mode, bool(checked)
            )
        )
        return chk

    def _role_key_for_lazy_row(self, row: int):
        """Return role key (int or builtin:*) for a lazy-table row."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return None
        item = table.item(row, 3)
        if item is None:
            return None
        role_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(role_data, str):
            role_text = str(role_data)
            if role_text.startswith("builtin:"):
                return role_text
            if role_text.startswith("modality_"):
                try:
                    return int(role_text.split("_", 1)[1])
                except Exception:
                    return None
            return role_text
        try:
            return int(role_data)
        except Exception:
            return None

    def _sync_mode_widgets_for_roles(self, role_keys: set, mode_key: str) -> None:
        """Apply mode-check state to all visible lazy-table rows for given role keys."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        mk = str(mode_key).strip().lower()
        if mk not in {"contrast", "zoom", "playback"}:
            return
        col = {"contrast": 7, "zoom": 8, "playback": 9}[mk]
        role_set = set(role_keys or set())
        for row in range(table.rowCount()):
            rk = self._role_key_for_lazy_row(row)
            if rk not in role_set:
                continue
            widget = table.cellWidget(row, col)
            if widget is None:
                continue
            target_checked = bool(self._sync_modes_for_role(rk).get(mk, True))
            force_disable = mk == "playback" and self._is_single_frame_projection_role(rk)
            widget.blockSignals(True)
            try:
                if hasattr(widget, "setChecked"):
                    widget.setChecked(False if force_disable else target_checked)
                if hasattr(widget, "setEnabled"):
                    widget.setEnabled(not force_disable)
            finally:
                widget.blockSignals(False)

    def _ensure_lazy_sync_group_keys(self) -> None:
        """Ensure every lazy modality/view row has a numeric sync key."""
        groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
        if getattr(self, "controller", None) is None:
            self._lazy_modality_groups = groups
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        for modality in manager.get_all_modalities():
            mid = int(modality.idx)
            key = str(groups.get(mid, "")).strip()
            if not key.isdigit():
                groups[mid] = "1"
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        for builtin_key in ("support", "mean", "std"):
            if builtin_key != "support" and builtin_key not in builtin:
                continue
            role_key = f"builtin:{builtin_key}"
            key = str(groups.get(role_key, "")).strip()
            if not key.isdigit():
                groups[role_key] = "1"
        self._lazy_modality_groups = groups
        self._ensure_lazy_sync_modes()

    def _add_lazy_modality_view(self, projection_key: str) -> None:
        """Add a new modality/view row and reflect it immediately on canvas."""
        if getattr(self, "controller", None) is None:
            return
        table = getattr(self, "lazy_modality_table", None)
        if table is not None:
            table.clearFocus()
        from phage_annotator.session.migration import ensure_modality_system
        from phage_annotator.session.modality import ProjectionType

        proj_key = str(projection_key or "raw").strip().lower()

        manager = ensure_modality_system(self.controller.session_state)
        proj = {
            "raw": ProjectionType.RAW,
            "mean": ProjectionType.MEAN,
            "median": ProjectionType.MEDIAN,
            "std": ProjectionType.STD,
            "min": ProjectionType.MIN,
            "max": ProjectionType.MAX,
        }.get(proj_key, ProjectionType.RAW)
        try:
            modality = manager.add_modality(
                image_id=int(getattr(getattr(self, "primary_image", None), "id", 0)),
                projection_type=proj,
            )
        except Exception as exc:
            self._set_status(f"Could not add modality/view: {exc}")
            return
        self._panel_visibility[f"modality_{int(modality.idx)}"] = True
        panel_key = self._panel_key_for_modality_idx(int(modality.idx))
        order_map = dict(getattr(self, "_lazy_panel_order", {}) or {})
        next_no = max([int(v) for v in order_map.values() if str(v).isdigit()] or [0]) + 1
        order_map[str(panel_key)] = int(next_no)
        self._lazy_panel_order = order_map
        groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
        groups[int(modality.idx)] = "1"
        self._lazy_modality_groups = groups
        self._ensure_lazy_sync_group_keys()
        self._refresh_lazy_modality_table()
        table = getattr(self, "lazy_modality_table", None)
        if table is not None:
            for row in range(table.rowCount()):
                name_item = table.item(row, 3)
                if name_item is None:
                    continue
                role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
                try:
                    role_idx = int(role_data)
                except Exception:
                    continue
                if role_idx == int(modality.idx):
                    table.selectRow(row)
                    break
        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        if hasattr(self, "_refresh_modality_layers_panel"):
            self._refresh_modality_layers_panel()
        self._refresh_annotation_view_controls()
        self._refresh_image()

    def _remove_selected_lazy_modality_view(self) -> None:
        """Remove selected runtime modality view."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or getattr(self, "controller", None) is None:
            return
        row = int(table.currentRow())
        if row < 0:
            return
        item = table.item(row, 3)
        if item is None:
            return
        role_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        if isinstance(role_data, str):
            role_text = str(role_data)
            if role_text.startswith("builtin:"):
                key = role_text.split(":", 1)[1]
                if key in {"mean", "std"}:
                    builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
                    builtin.pop(key, None)
                    self._lazy_builtin_views = builtin
                modes = dict(getattr(self, "_lazy_sync_modes", {}) or {})
                modes.pop(f"builtin:{key}", None)
                self._lazy_sync_modes = modes
                order_map = dict(getattr(self, "_lazy_panel_order", {}) or {})
                order_map.pop(str(key), None)
                self._lazy_panel_order = order_map
                self._on_panel_toggle(str(key), False)
                self._refresh_lazy_modality_table()
                self._refresh_annotation_view_controls()
                self._set_status(f"Removed view: {key}")
            return

        modality_idx = int(role_data)
        panel_key = self._panel_key_for_modality_idx(modality_idx)
        if modality_idx <= 1:
            # Base modalities cannot be deleted from manager, but can be hidden.
            hidden_base = set(getattr(self, "_lazy_hidden_base_panel_keys", set()) or set())
            hidden_base.add(str(panel_key))
            self._lazy_hidden_base_panel_keys = hidden_base
            order_map = dict(getattr(self, "_lazy_panel_order", {}) or {})
            order_map.pop(str(panel_key), None)
            self._lazy_panel_order = order_map
            self._on_panel_toggle(str(panel_key), False)
            self._refresh_lazy_modality_table()
            self._refresh_annotation_view_controls()
            self._set_status(f"Removed view: {panel_key}")
            return
        if manager.remove_modality(modality_idx):
            self._panel_visibility.pop(f"modality_{modality_idx}", None)
            order_map = dict(getattr(self, "_lazy_panel_order", {}) or {})
            order_map.pop(f"modality_{modality_idx}", None)
            self._lazy_panel_order = order_map
            modes = dict(getattr(self, "_lazy_sync_modes", {}) or {})
            modes.pop(int(modality_idx), None)
            self._lazy_sync_modes = modes
            self._refresh_lazy_modality_table()
            self._refresh_annotation_view_controls()
            self._refresh_image()

    def _on_lazy_modality_item_changed(self, item) -> None:
        """Handle lazy-table inline rename and propagate to canvas titles."""
        if item is None or getattr(self, "controller", None) is None:
            return
        col = int(item.column())
        if col not in (0, 3, 6):
            return
        from phage_annotator.session.migration import ensure_modality_system

        role_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        role_text = str(role_data)
        panel_key = ""
        if role_text.startswith("builtin:"):
            panel_key = role_text.split(":", 1)[1]
        else:
            try:
                panel_key = self._panel_key_for_modality_idx(int(role_data))
            except Exception:
                panel_key = ""
        if col == 0:
            if not panel_key:
                return
            new_order = str(item.text()).strip()
            if not new_order.isdigit():
                item.setText(str(dict(getattr(self, "_lazy_panel_order", {}) or {}).get(panel_key, 1)))
                return
            self._reorder_lazy_panel_by_no(str(panel_key), int(new_order))
            self._refresh_lazy_modality_table()
            self._refresh_annotation_view_controls()
            self._refresh_image()
            return
        if role_text.startswith("builtin:"):
            if col == 6:
                groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
                new_key = str(item.text()).strip()
                if not new_key.isdigit():
                    new_key = "1"
                groups[f"builtin:{panel_key}"] = new_key
                self._lazy_modality_groups = groups
                item.setText(new_key)
                self._apply_lazy_group_sync_selection(new_key)
                self._set_status("Sync group updated.")
                return
            new_name = str(item.text()).strip() or panel_key.title()
            if panel_key == "support":
                # Support title is backed by modality idx=1 in manager.
                manager = ensure_modality_system(self.controller.session_state)
                support_modality = manager.get_modality(1)
                if support_modality is not None:
                    support_modality.display_name = new_name
                else:
                    builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
                    cfg = dict(builtin.get("support", {}) or {})
                    cfg["name"] = new_name
                    cfg["image_id"] = int(getattr(getattr(self, "support_image", None), "id", -1))
                    builtin["support"] = cfg
                    self._lazy_builtin_views = builtin
            else:
                builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
                cfg = dict(builtin.get(panel_key, {}) or {})
                cfg["name"] = new_name
                builtin[panel_key] = cfg
                self._lazy_builtin_views = builtin
            self._refresh_annotation_view_controls()
            self._refresh_image()
            return

        modality_idx = int(role_data)
        if col == 6:
            groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
            new_key = str(item.text()).strip()
            if not new_key.isdigit():
                new_key = "1"
            groups[int(modality_idx)] = new_key
            self._lazy_modality_groups = groups
            item.setText(new_key)
            self._apply_lazy_group_sync_selection(new_key)
            self._set_status("Sync group updated.")
            return
        new_name = str(item.text()).strip()
        if not new_name:
            return
        manager = ensure_modality_system(self.controller.session_state)
        try:
            manager.rename_modality(modality_idx, new_name)
        except Exception as exc:
            self._set_status(f"Rename rejected: {exc}")
            return
        self._refresh_annotation_view_controls()
        self._refresh_image()

    def _apply_lazy_group_sync_selection(self, group_key: str) -> None:
        """Set manual sync target to a shared lazy-table group key."""
        group = str(group_key or "").strip()
        combo = getattr(self, "sync_key_combo", None)
        if not group or combo is None:
            return
        idx = combo.findData(group)
        if idx < 0:
            return
        mode_combo = getattr(self, "sync_target_mode_combo", None)
        if mode_combo is not None:
            mode_combo.blockSignals(True)
            mode_combo.setCurrentIndex(max(0, mode_combo.findData("manual")))
            mode_combo.blockSignals(False)
        if getattr(self, "sync_follow_active_chk", None) is not None:
            self.sync_follow_active_chk.setChecked(False)
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()

    def _lazy_auto_update_enabled(self) -> bool:
        """Return whether lazy-table source/view edits apply immediately."""
        chk = getattr(self, "lazy_auto_update_chk", None)
        if chk is None:
            return True
        try:
            return bool(chk.isChecked())
        except Exception:
            return True

    def _set_lazy_apply_button_state(self) -> None:
        """Update apply button enabled state based on pending edits."""
        btn = getattr(self, "lazy_apply_btn", None)
        if btn is None:
            return
        pending = dict(getattr(self, "_lazy_pending_updates", {}) or {})
        btn.setEnabled(bool(pending))

    def _sync_builtin_projections_with_primary_source(
        self,
        old_primary_id: int,
        new_primary_id: int,
    ) -> None:
        """Keep mean/std builtins following Modality 1 unless user explicitly diverged."""
        old_id = int(old_primary_id)
        new_id = int(new_primary_id)
        if old_id == new_id:
            return
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        changed = False
        for key in ("mean", "std"):
            cfg = dict(builtin.get(key, {}) or {})
            current = cfg.get("image_id", old_id)
            try:
                current_id = int(current)
            except Exception:
                current_id = old_id
            # Follow primary when still on old/default source.
            if current_id == old_id:
                cfg["image_id"] = new_id
                builtin[key] = cfg
                changed = True
        if changed:
            self._lazy_builtin_views = builtin

    def _on_lazy_auto_update_toggled(self, checked: bool) -> None:
        """Persist auto-update preference for lazy-table edits."""
        enabled = bool(checked)
        if getattr(self, "_settings", None) is not None:
            self._settings.setValue("lazyModalityAutoUpdate", enabled)
        if enabled:
            self._apply_lazy_pending_updates()
        else:
            self._set_status("Lazy table edits staged. Click Update Canvas to apply.")
            self._set_lazy_apply_button_state()

    def _queue_lazy_pending_update(self, key: tuple, callback, description: str) -> None:
        """Queue one lazy-table change for manual apply mode."""
        pending = dict(getattr(self, "_lazy_pending_updates", {}) or {})
        pending[tuple(key)] = (callback, str(description))
        self._lazy_pending_updates = pending
        self._set_lazy_apply_button_state()
        self._set_status(f"Pending updates: {len(pending)}")

    def _apply_lazy_pending_updates(self) -> None:
        """Apply queued lazy-table changes when auto-update is disabled."""
        pending = dict(getattr(self, "_lazy_pending_updates", {}) or {})
        if not pending:
            self._set_lazy_apply_button_state()
            return
        self._lazy_pending_updates = {}
        self._set_lazy_apply_button_state()
        applied = 0
        for callback, _desc in pending.values():
            try:
                callback()
                applied += 1
            except Exception:
                continue
        if applied > 0:
            self._set_status(f"Applied {applied} lazy-table update(s).")
        else:
            self._set_status("No lazy-table updates applied.")

    def _on_lazy_modality_source_changed(
        self,
        modality_idx: int,
        image_id: int,
        *,
        force_apply: bool = False,
    ) -> None:
        if getattr(self, "controller", None) is None:
            return
        if (not force_apply) and (not self._lazy_auto_update_enabled()):
            key = ("modality_source", int(modality_idx))
            self._queue_lazy_pending_update(
                key,
                lambda mid=int(modality_idx), img=int(image_id): self._on_lazy_modality_source_changed(
                    mid, img, force_apply=True
                ),
                f"modality {int(modality_idx)} source",
            )
            return
        # Base rows are coupled to main primary/support context.
        if int(modality_idx) == 0:
            old_primary_id = int(getattr(getattr(self, "primary_image", None), "id", -1))
            image_idx = self._image_index_from_id(int(image_id))
            self._set_primary_combo(
                int(image_idx),
                refresh_lazy_table=False,
                schedule_prefetch=False,
            )
            new_primary_id = int(getattr(getattr(self, "primary_image", None), "id", -1))
            self._sync_builtin_projections_with_primary_source(old_primary_id, new_primary_id)
            if hasattr(self, "proj_cache"):
                try:
                    self.proj_cache.invalidate_image(old_primary_id)
                    self.proj_cache.invalidate_image(new_primary_id)
                except Exception:
                    pass
            if hasattr(self, "_refresh_lazy_modality_table"):
                self._refresh_lazy_modality_table()
            return
        if int(modality_idx) == 1:
            image_idx = self._image_index_from_id(int(image_id))
            self._set_support_combo(int(image_idx), refresh_lazy_table=False)
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            support_cfg = dict(builtin.get("support", {}) or {})
            support_cfg["image_id"] = int(image_id)
            builtin["support"] = support_cfg
            self._lazy_builtin_views = builtin
            if hasattr(self, "_refresh_lazy_modality_table"):
                self._refresh_lazy_modality_table()
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        modality = manager.get_modality(int(modality_idx))
        if modality is None:
            return
        old_image_id = int(getattr(modality, "image_id", -1))
        modality.image_id = int(image_id)
        if hasattr(self, "proj_cache"):
            try:
                self.proj_cache.invalidate_image(old_image_id)
                self.proj_cache.invalidate_image(int(image_id))
            except Exception:
                pass
        self._refresh_image()

    def _on_lazy_modality_projection_changed(
        self,
        modality_idx: int,
        projection_key: str,
        *,
        force_apply: bool = False,
    ) -> None:
        if getattr(self, "controller", None) is None:
            return
        if (not force_apply) and (not self._lazy_auto_update_enabled()):
            key = ("modality_projection", int(modality_idx))
            self._queue_lazy_pending_update(
                key,
                lambda mid=int(modality_idx), proj=str(projection_key): self._on_lazy_modality_projection_changed(
                    mid, proj, force_apply=True
                ),
                f"modality {int(modality_idx)} projection",
            )
            return
        from phage_annotator.session.migration import ensure_modality_system
        from phage_annotator.session.modality import ProjectionType

        manager = ensure_modality_system(self.controller.session_state)
        modality = manager.get_modality(int(modality_idx))
        if modality is None:
            return
        try:
            modality.projection_type = ProjectionType(str(projection_key).strip().lower())
        except Exception:
            modality.projection_type = ProjectionType.RAW
        # Projection rows are single-frame, so playback sync must be forced off.
        self._ensure_lazy_sync_modes()
        self._sync_mode_widgets_for_roles({int(modality_idx)}, "playback")
        self._refresh_image()

    def _on_lazy_builtin_source_changed(
        self,
        panel_key: str,
        image_id: int,
        *,
        force_apply: bool = False,
    ) -> None:
        """Update source image for built-in mean/std panel rows."""
        if (not force_apply) and (not self._lazy_auto_update_enabled()):
            key = ("builtin_source", str(panel_key))
            self._queue_lazy_pending_update(
                key,
                lambda pk=str(panel_key), img=int(image_id): self._on_lazy_builtin_source_changed(
                    pk, img, force_apply=True
                ),
                f"{str(panel_key)} source",
            )
            return
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(str(panel_key), {}) or {})
        old_image_id = int(cfg.get("image_id", getattr(getattr(self, "primary_image", None), "id", -1)))
        cfg["image_id"] = int(image_id)
        builtin[str(panel_key)] = cfg
        self._lazy_builtin_views = builtin
        if hasattr(self, "proj_cache"):
            try:
                self.proj_cache.invalidate_image(old_image_id)
                self.proj_cache.invalidate_image(int(image_id))
            except Exception:
                pass
        self._refresh_image()

    def _on_lazy_builtin_projection_changed(
        self,
        panel_key: str,
        projection_key: str,
        *,
        force_apply: bool = False,
    ) -> None:
        """Update projection type for built-in mean/std panel rows."""
        if (not force_apply) and (not self._lazy_auto_update_enabled()):
            key = ("builtin_projection", str(panel_key))
            self._queue_lazy_pending_update(
                key,
                lambda pk=str(panel_key), proj=str(projection_key): self._on_lazy_builtin_projection_changed(
                    pk, proj, force_apply=True
                ),
                f"{str(panel_key)} projection",
            )
            return
        if str(panel_key) == "support":
            return
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(str(panel_key), {}) or {})
        cfg["projection"] = str(projection_key).strip().lower()
        builtin[str(panel_key)] = cfg
        self._lazy_builtin_views = builtin
        role_key = f"builtin:{str(panel_key)}"
        self._ensure_lazy_sync_modes()
        self._sync_mode_widgets_for_roles({role_key}, "playback")
        self._refresh_image()

    def _on_lazy_builtin_support_source_changed(
        self,
        image_id: int,
        *,
        force_apply: bool = False,
    ) -> None:
        """Update support panel source image from lazy table."""
        if (not force_apply) and (not self._lazy_auto_update_enabled()):
            key = ("builtin_support_source", "support")
            self._queue_lazy_pending_update(
                key,
                lambda img=int(image_id): self._on_lazy_builtin_support_source_changed(
                    img, force_apply=True
                ),
                "support source",
            )
            return
        try:
            image_idx = self._image_index_from_id(int(image_id))
            self._set_support_combo(int(image_idx), refresh_lazy_table=False)
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            support_cfg = dict(builtin.get("support", {}) or {})
            support_cfg["image_id"] = int(image_id)
            builtin["support"] = support_cfg
            self._lazy_builtin_views = builtin
        except Exception:
            self.support_image_idx = self._image_index_from_id(int(image_id))
            self._refresh_image()

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
                "status_details",
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
            "status_details",
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
            def _restore_group_style() -> None:
                try:
                    group.setStyleSheet(prior_style)
                except RuntimeError:
                    # Widget may be deleted during teardown before timer fires.
                    return

            QtCore.QTimer.singleShot(1500, _restore_group_style)

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
            # Keep right side usable by default: if nothing is visible, show Annotation Table.
            any_right_visible = any(
                bool(getattr(self, attr, None) is not None and getattr(self, attr).isVisible())
                for attr in (
                    "dock_annotations",
                    "dock_review_queue",
                    "dock_suggestion_explain",
                    "dock_modality_layers",
                    "dock_advanced_analysis",
                    "dock_status_details",
                )
            )
            if not any_right_visible and getattr(self, "dock_annotations", None) is not None:
                self.set_panel_visible("annotations", True, source="restore_defaults")
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
            "dock_suggestion_explain",
            "dock_advanced_analysis",
            "dock_modality_layers",
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
            self.set_panel_visible("status_details", False, source="review_context_pack")
            if getattr(self, "dock_review_queue", None) is not None:
                self.dock_review_queue.raise_()
            self._set_status("Review Context Pack enabled.")
        else:
            self.set_panel_visible("annotations", True, source="review_context_pack")
            self.set_panel_visible("review_queue", False, source="review_context_pack")
            self.set_panel_visible("suggestion_explain", False, source="review_context_pack")
            self.set_panel_visible("modality_layers", False, source="review_context_pack")
            self.set_panel_visible("status_details", False, source="review_context_pack")
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
        # DISABLED: Layout restoration disabled to prevent floating dock windows
        # geometry = self._settings.value("customGeometry", type=QtCore.QByteArray)
        # state = self._settings.value("customState", type=QtCore.QByteArray)
        # if geometry:
        #     self.restoreGeometry(geometry)
        # if state:
        #     self.restoreState(state)
        
        # Ensure no docks are floating
        for dock_attr in dir(self):
            if dock_attr.startswith("dock_") and hasattr(self, dock_attr):
                dock = getattr(self, dock_attr)
                if isinstance(dock, QtWidgets.QDockWidget) and dock is not None:
                    try:
                        dock.setFloating(False)
                    except Exception:
                        pass
        
        if self.dock_sidebar is not None and not self.dock_sidebar.isVisible():
            self.set_panel_visible("sidebar", True, source="layout_restore")
        # Keep status details dock opt-in only; do not auto-restore it.
        if hasattr(self, "set_panel_visible"):
            self.set_panel_visible("status_details", False, source="layout_restore")
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
                "status_details": False,
                "advanced_analysis": False,
                "roi": False,
                "roi_manager": False,
                "results": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "performance": False,
                "density": False,
                "threshold": False,
                "particles": False,
                "qc_issues": False,
                "modality_layers": False,
                "orthoview": False,
            },
            "Minimal": {
                "sidebar": True,
                "annotations": False,
                "review_queue": False,
                "suggestion_explain": False,
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
                "performance": False,
                "density": False,
                "qc_issues": False,
                "modality_layers": False,
                "orthoview": False,
            },
            "Annotate": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": False,
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
                "performance": False,
                "density": False,
                "qc_issues": False,
                "modality_layers": False,
                "orthoview": False,
            },
            "Analyze": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": False,
                "status_details": False,
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
                "performance": False,
                "density": False,
                "qc_issues": False,
                "modality_layers": False,
            },
            "Assist Expert": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": True,
                "status_details": False,
                "advanced_analysis": False,
                "qc_issues": False,
                "roi": False,
                "roi_manager": False,
                "results": False,
                "threshold": False,
                "particles": False,
                "hist": False,
                "profile": False,
                "logs": False,
                "performance": False,
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
        # Keep all docks embedded; presets should not spawn floating windows.
        for dock in (getattr(self, "panel_docks", {}) or {}).values():
            if dock is None:
                continue
            try:
                dock.setFloating(False)
            except Exception:
                continue
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

    def _on_canvas_grid_rows_changed(self, value: int) -> None:
        """Set preferred canvas grid rows (0 = automatic)."""
        self._canvas_layout_rows = max(0, int(value))
        if getattr(self, "_settings", None) is not None:
            self._settings.setValue("canvasLayoutRows", int(self._canvas_layout_rows))
        self._rebuild_figure_layout()
        self._refresh_image()

    def _on_canvas_grid_cols_changed(self, value: int) -> None:
        """Set preferred canvas grid columns (0 = automatic)."""
        self._canvas_layout_cols = max(0, int(value))
        if getattr(self, "_settings", None) is not None:
            self._settings.setValue("canvasLayoutCols", int(self._canvas_layout_cols))
        self._rebuild_figure_layout()
        self._refresh_image()

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
        for fig_name in ("hist_fig", "profile_fig"):
            fig = getattr(self, fig_name, None)
            if fig is not None:
                fig.clear()
        QtWidgets.QMainWindow.closeEvent(self, event)
