"""UI helpers for sidebar, tool routing, layout, and command palette."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

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
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter


class UiExtrasMixin(UiRefreshMixin, UiTooltipMixin, UiAnnotationViewsMixin):
    """Mixin for sidebar pages, tools, and layout/command palette actions."""

    def _build_sidebar_stack(self) -> QtWidgets.QWidget:
        """Create the workflow sidebar with activity bar and toggle behavior.
        
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
        self._right_sidebar_intentionally_closed = False  # Track if user explicitly closed sidebar
        
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
        
        # Use the workflow-page registry if sidebar_pages are built
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
                "Prepare",
                self,
            )
            annotate_act = QtWidgets.QAction(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView),
                "Annotate",
                self,
            )
            analyze_act = QtWidgets.QAction(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
                "Advanced",
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
        table_act.setToolTip("Annotation Table: inspect, sort, and edit the current annotation list.")
        table_act.setStatusTip("Open the annotation table for the active annotation context.")
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
        queue_act.setToolTip("Review Queue: work through uncertain or review-targeted suggestions.")
        queue_act.setStatusTip("Open the review queue for assist and reviewer workflows.")
        queue_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("review_queue")
        )
        bar.addAction(queue_act)

        explain_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation),
            "Suggestion Rationale",
            self,
        )
        explain_act.setObjectName("right_sidebar_why_toggle")
        explain_act.setCheckable(True)
        explain_act.setChecked(False)
        explain_act.setToolTip("Suggestion Rationale: inspect why the focused suggestion was proposed.")
        explain_act.setStatusTip("Open rationale and evidence for the focused suggestion.")
        explain_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("suggestion_explain")
        )
        bar.addAction(explain_act)

        qc_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning),
            "QC Issues",
            self,
        )
        qc_act.setObjectName("right_sidebar_qc_toggle")
        qc_act.setCheckable(True)
        qc_act.setChecked(False)
        qc_act.setToolTip("QC Issues: inspect validation warnings, conflicts, and review-blocking issues.")
        qc_act.setStatusTip("Open QC issues for the current review and validation context.")
        qc_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("qc_issues")
        )
        bar.addAction(qc_act)

        layers_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView),
            "Modality Layers",
            self,
        )
        layers_act.setObjectName("right_sidebar_layers_toggle")
        layers_act.setCheckable(True)
        layers_act.setChecked(False)
        layers_act.setToolTip("Modality Layers: compare or tune view-layer presets across modalities.")
        layers_act.setStatusTip("Open layer controls for modality and evidence overlays.")
        layers_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("modality_layers")
        )
        bar.addAction(layers_act)

        advanced_act = QtWidgets.QAction(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarMenuButton),
            "Analysis",
            self,
        )
        advanced_act.setObjectName("right_sidebar_advanced_toggle")
        advanced_act.setCheckable(True)
        advanced_act.setChecked(False)
        advanced_act.setToolTip("Analysis: open advanced analysis tools without leaving the main canvas.")
        advanced_act.setStatusTip("Open advanced analysis tools and measurement helpers.")
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
        status_act.setToolTip("Status Details: expanded operational summary of sync, write context, jobs, and diagnostics.")
        status_act.setStatusTip("Open detailed run and workflow status.")
        status_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("status_details")
        )
        bar.addAction(status_act)

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
            "qc_issues": qc_act,
            "modality_layers": layers_act,
            "advanced_analysis": advanced_act,
            "status_details": status_act,
        }

        self.addToolBar(QtCore.Qt.RightToolBarArea, bar)

        for panel_id in (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "qc_issues",
            "modality_layers",
            "advanced_analysis",
            "status_details",
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
            "qc_issues",
            "modality_layers",
            "advanced_analysis",
            "status_details",
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
        # Don't auto-open annotations panel if sidebar is collapsed or all panels closed
        # This allows full collapse of the right sidebar
        if not any(
            bool(getattr(self, f"dock_{panel_id}", None) and getattr(self, f"dock_{panel_id}").isVisible())
            for panel_id in (
                "annotations",
                "review_queue",
                "suggestion_explain",
                "qc_issues",
                "modality_layers",
                "advanced_analysis",
                "status_details",
            )
        ):
            # Only auto-open if sidebar is NOT explicitly collapsed
            if (getattr(self, "dock_annotations", None) is not None 
                and not getattr(self, "_right_sidebar_collapsed", False)
                and not getattr(self, "_right_sidebar_intentionally_closed", False)):
                self.set_panel_visible("annotations", True, source="right_sidebar:auto_default")

    def _ensure_right_sidebar_panels_not_tabified(self) -> None:
        """Keep right inspect panels as standalone docks (never tab peers)."""
        panel_ids = (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "qc_issues",
            "modality_layers",
            "advanced_analysis",
            "status_details",
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
            "qc_issues",
            "modality_layers",
            "advanced_analysis",
            "status_details",
        ]
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
            "suggestion_explain",
            "qc_issues",
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
                    "qc_issues",
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
        intro_lbl = QtWidgets.QLabel(
            "Choose where points will be written, which label they use, and whether you are annotating the current slice or the full stack."
        )
        intro_lbl.setWordWrap(True)
        intro_lbl.setStyleSheet("color: #546e7a;")
        layout.addWidget(intro_lbl)

        quick_group = QtWidgets.QGroupBox("Quick panels")
        quick_layout = QtWidgets.QGridLayout(quick_group)
        quick_layout.setContentsMargins(8, 8, 8, 8)
        quick_layout.setHorizontalSpacing(6)
        quick_layout.setVerticalSpacing(6)
        open_annotations_btn = QtWidgets.QPushButton("Annotation Table")
        open_annotations_btn.setToolTip("Open the annotation table to inspect or edit the current annotation set.")
        open_annotations_btn.clicked.connect(
            lambda: self.open_panel("annotations", reason="annotate_sidebar")
        )
        open_review_btn = QtWidgets.QPushButton("Review Queue")
        open_review_btn.setToolTip("Open the review queue for uncertain or review-targeted points.")
        open_review_btn.clicked.connect(
            lambda: self.open_panel("review_queue", reason="annotate_sidebar")
        )
        quick_layout.addWidget(open_annotations_btn, 0, 0)
        quick_layout.addWidget(open_review_btn, 0, 1)
        layout.addWidget(quick_group)

        target_group = QtWidgets.QGroupBox("1. Write target")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        target_layout.setContentsMargins(8, 8, 8, 8)
        target_layout.setSpacing(6)
        target_help_lbl = QtWidgets.QLabel(
            "New points are written into the selected modality/context. Read-only targets are excluded automatically."
        )
        target_help_lbl.setWordWrap(True)
        target_help_lbl.setStyleSheet("color: #546e7a;")
        target_layout.addWidget(target_help_lbl)
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

        label_group = QtWidgets.QGroupBox("2. Label")
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

        scope_group = QtWidgets.QGroupBox("3. Scope")
        scope_layout = QtWidgets.QVBoxLayout(scope_group)
        scope_layout.setContentsMargins(8, 8, 8, 8)
        scope_layout.setSpacing(6)
        self.scope_group = QtWidgets.QButtonGroup()
        for label in ["Current slice", "All slices"]:
            btn = QtWidgets.QRadioButton(label)
            scope_value = str(getattr(self, "annotation_scope", "current"))
            if (scope_value == "all" and label == "All slices") or (
                scope_value != "all" and label == "Current slice"
            ):
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

        tool_group = QtWidgets.QGroupBox("4. Tools")
        tool_layout = QtWidgets.QVBoxLayout(tool_group)
        tool_layout.setContentsMargins(8, 8, 8, 8)
        tool_layout.setSpacing(6)
        self.tool_label = QtWidgets.QLabel("Tool: Annotate")
        tool_layout.addWidget(self.tool_label)
        tool_help_lbl = QtWidgets.QLabel(
            "Use the top toolbar or number shortcuts to switch between pan, annotate, ROI, profile, and eraser tools."
        )
        tool_help_lbl.setWordWrap(True)
        tool_help_lbl.setStyleSheet("color: #546e7a;")
        tool_layout.addWidget(tool_help_lbl)
        
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

        vis_group = QtWidgets.QGroupBox("5. Annotation overlays")
        vis_layout = QtWidgets.QVBoxLayout(vis_group)
        vis_layout.setContentsMargins(8, 8, 8, 8)
        vis_layout.setSpacing(6)
        vis_help_lbl = QtWidgets.QLabel(
            "Control where annotations remain visible. The active write target stays visible to avoid hidden-write mistakes."
        )
        vis_help_lbl.setWordWrap(True)
        vis_help_lbl.setStyleSheet("color: #546e7a;")
        vis_layout.addWidget(vis_help_lbl)
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        row = QtWidgets.QVBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._annotation_view_rows_layout = row
        self._annotation_view_checkboxes = {}
        view_specs = [
            ("frame", "Frame"),
            ("mean", "Mean Projection"),
            ("support", "Modality 2"),
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
            "suggestion_explain",
            "qc_issues",
            "advanced_analysis",
            "modality_layers",
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
        if target == "annotate":
            self._show_right_dock_mode("annotations")
            return
        if target == "review":
            extras: tuple[str, ...] = ("qc_issues",)
            if getattr(self, "_visible_suggestions_uncertain_first", None) is not None:
                try:
                    if bool(self._visible_suggestions_uncertain_first()):
                        extras = extras + ("suggestion_explain",)
                except Exception:
                    extras = ("qc_issues",)
            self._show_right_dock_mode("review_queue", extras=extras)
            return
        if target == "inspect":
            self._show_right_dock_mode("suggestion_explain", extras=("review_queue", "status_details"))
            return

    def _show_right_dock_mode(self, primary_panel: str, *, extras: tuple[str, ...] = ()) -> None:
        """Show one right-dock workflow state with an optional supporting context panel."""
        right_ids = (
            "annotations",
            "review_queue",
            "suggestion_explain",
            "qc_issues",
            "status_details",
        )
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
            self._show_right_dock_mode("review_queue", extras=("suggestion_explain", "qc_issues"))
            self._status_info("Assist Mode enabled.", timeout_ms=2500, source="ui_extra.assist_mode")
            return
        # OFF: keep review queue available, but raise table and reduce inspect clutter.
        self._show_right_dock_mode("annotations", extras=("review_queue",))
        self._status_info("Assist Mode disabled.", timeout_ms=2500, source="ui_extra.assist_mode")

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
        target_key = str(getattr(self, "annotate_target", "frame")).strip().lower()
        ax = axes.get(target_key)
        if ax is not None:
            return ax
        if "frame" in axes:
            return axes.get("frame")
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
            self._apply_sidebar_mode_defaults_for_stack_index(stack_idx)
        self._settings.setValue("sidebarMode", idx)

    def _refresh_lazy_modality_table(self) -> None:
        """Populate lazy-loading modality/view table."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        self._ensure_lazy_loader_base_modalities()
        row_specs = self._lazy_table_row_specs(manager)
        normalized_groups = normalize_lazy_sync_groups(
            row_specs,
            self._lazy_sync_groups_state(),
        )
        for role_key, group_key in normalized_groups.items():
            self._set_lazy_sync_group_for_role(role_key, group_key)
        row_specs = self._lazy_table_row_specs(manager)
        table.blockSignals(True)
        table.setRowCount(0)
        for row_spec in row_specs:
            self._insert_lazy_table_row(table, row_spec)

        # Remove stale dynamic panel visibility keys no longer represented by modalities.
        valid_dynamic_keys = {
            self._panel_key_for_modality_idx(int(modality.idx))
            for modality in manager.get_all_modalities()
            if int(modality.idx) >= 2
        }
        for key in list(dict(getattr(self, "_panel_visibility", {}) or {}).keys()):
            k = str(key)
            if k.startswith("modality_") and k not in valid_dynamic_keys:
                self._panel_visibility.pop(k, None)

        table.blockSignals(False)
        table.resizeColumnsToContents()
        table.setColumnWidth(LAZY_TABLE_COLUMN_SHOW, 44)
        table.setColumnWidth(LAZY_TABLE_COLUMN_POINTS, 44)
        table.setColumnWidth(LAZY_TABLE_COLUMN_NAME, 180)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SOURCE, 150)
        table.setColumnWidth(LAZY_TABLE_COLUMN_PROJECTION, 110)
        table.setColumnWidth(LAZY_TABLE_COLUMN_ANNOTATION_MODE, 120)
        table.setColumnWidth(LAZY_TABLE_COLUMN_ANNOTATION_FILE, 84)
        table.setColumnWidth(LAZY_TABLE_COLUMN_GROUP, 70)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SYNC_CONTRAST, 86)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SYNC_VIEW, 88)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SYNC_TIME, 84)
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        # Update sync key selector dropdown to show all available group keys
        if hasattr(self, "_update_sync_key_selector"):
            try:
                self._update_sync_key_selector()
            except Exception:
                pass

    def _panel_key_for_modality_idx(self, modality_idx: int) -> str:
        """Map modality index to panel key used by renderer/sync list."""
        idx = int(modality_idx)
        if idx == 0:
            return "frame"
        if idx == 1:
            return "support"
        return f"modality_{idx}"

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

    def _normalized_lazy_sync_group_key(self, group_key: object, groups: dict | None = None) -> str:
        """Return a valid numeric sync-group key."""
        text = str(group_key or "").strip()
        if text.isdigit():
            return text
        return self._next_numeric_sync_key(dict(groups or self._lazy_sync_groups_state() or {}))

    def _lazy_sync_groups_state(self) -> dict:
        """Return controller-owned lazy sync groups."""
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "get_lazy_sync_groups"):
            return dict(controller.get_lazy_sync_groups() or {})
        return {}

    def _lazy_sync_modes_state(self) -> dict:
        """Return controller-owned lazy sync modes."""
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "get_lazy_sync_modes"):
            return dict(controller.get_lazy_sync_modes() or {})
        return {}

    def _lazy_sync_group_for_role(self, role_key) -> str:
        """Return the current normalized sync group for one lazy-table role."""
        groups = self._lazy_sync_groups_state()
        return self._normalized_lazy_sync_group_key(groups.get(role_key, ""), groups)

    def _set_lazy_sync_group_for_role(self, role_key, group_key: object) -> str:
        """Set lazy sync-group membership through one centralized mutation path."""
        groups = self._lazy_sync_groups_state()
        normalized = self._normalized_lazy_sync_group_key(group_key, groups)
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "set_lazy_sync_group"):
            normalized = str(controller.set_lazy_sync_group(role_key, normalized))
            groups = self._lazy_sync_groups_state()
        else:
            return normalized
        self._ensure_lazy_sync_modes()
        self._apply_lazy_group_sync_selection(normalized)
        if hasattr(self, "_update_sync_key_selector"):
            try:
                self._update_sync_key_selector()
            except Exception:
                pass
        if hasattr(self, "_update_sync_keys_hint"):
            try:
                self._update_sync_keys_hint()
            except Exception:
                pass
        return normalized

    def _sync_modes_for_role(self, role_key) -> dict[str, bool]:
        """Return sync mode flags for a modality/view role key."""
        modes = self._lazy_sync_modes_state()
        current = dict(modes.get(role_key, {}) or {})
        normalized = {
            "contrast": bool(current.get("contrast", True)),
            "zoom": bool(current.get("zoom", True)),
            "playback": bool(current.get("playback", True)),
        }
        return normalized

    def _set_sync_mode_for_role(self, role_key, mode_key: str, enabled: bool) -> None:
        """Update one sync mode flag for all rows in the same sync group."""
        key = str(mode_key).strip().lower()
        if key not in {"contrast", "zoom", "playback"}:
            return
        groups = self._lazy_sync_groups_state()
        group_key = str(groups.get(role_key, "")).strip()
        target_roles = {role_key}
        if group_key.isdigit():
            target_roles = {rk for rk, gk in groups.items() if str(gk).strip() == group_key}
        modes = self._lazy_sync_modes_state()
        controller = getattr(self, "controller", None)
        for target_role in target_roles:
            row_modes = dict(modes.get(target_role, {}) or {})
            row_modes[key] = bool(enabled)
            normalized = {
                "contrast": bool(row_modes.get("contrast", True)),
                "zoom": bool(row_modes.get("zoom", True)),
                "playback": bool(row_modes.get("playback", True)),
            }
            if controller is not None and hasattr(controller, "set_lazy_sync_mode"):
                modes[target_role] = dict(controller.set_lazy_sync_mode(target_role, key, bool(enabled)) or {})
            else:
                modes[target_role] = normalized
        self._sync_mode_widgets_for_roles(target_roles, key)
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
        self._request_ui_refresh("lazy-sync-group", status=True)

    def _ensure_lazy_sync_modes(self) -> None:
        """Ensure each lazy row has explicit sync mode flags."""
        modes = self._lazy_sync_modes_state()
        groups = self._lazy_sync_groups_state()
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
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "set_lazy_sync_mode"):
            for role_key, state in modes.items():
                for mode_key, enabled in dict(state or {}).items():
                    controller.set_lazy_sync_mode(role_key, str(mode_key), bool(enabled))

    def _lazy_loader_focus_active(self) -> bool:
        """Return True when the lazy loader tree/table owns keyboard focus."""
        focused = QtWidgets.QApplication.focusWidget()
        for widget_name in ("lazy_loader_tree", "lazy_modality_table", "lazy_open_btn", "lazy_remove_btn"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            if focused is widget or widget.isAncestorOf(focused):
                return True
        return False

    def _schedule_lazy_panel_sync(self, reason: str = "state-changed") -> None:
        """Schedule a lazy-panel sync from controller state.

        This keeps UI refreshes event-driven and coalesced on the Qt loop so
        rapid state changes do not force synchronous widget rebuild cascades.
        """
        self._request_lazy_canvas_refresh(reason, refresh_table=True)

    def _sync_lazy_loader_sources(self) -> None:
        """Ensure current session images appear in the loader manifest."""
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None:
            return
        current_paths = {str(getattr(img, "path", "")) for img in getattr(self, "images", []) or []}
        if not manifest.roots:
            roots = [Path(path) for path in sorted(path for path in current_paths if path)]
            manifest.add_paths(roots, getattr(self, "_lazy_loader_path_to_ids", {}) or {})
        else:
            missing = [Path(path) for path in sorted(current_paths) if path and not manifest.contains(path)]
            if missing:
                manifest.add_paths(missing, getattr(self, "_lazy_loader_path_to_ids", {}) or {})

    def _lazy_loader_visible_image_ids(self) -> list[int]:
        """Return image ids exposed by the loader manifest."""
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None:
            return [int(getattr(img, "id", -1)) for img in getattr(self, "images", []) or []]
        self._sync_lazy_loader_sources()
        visible = manifest.visible_image_ids()
        if visible:
            return visible
        return [int(getattr(img, "id", -1)) for img in getattr(self, "images", []) or []]

    def _lazy_loader_source_images(self) -> list:
        """Return image objects that are still available to the loader controls."""
        visible_ids = set(self._lazy_loader_visible_image_ids())
        return [img for img in getattr(self, "images", []) or [] if int(getattr(img, "id", -1)) in visible_ids]

    def _refresh_lazy_loader_tree(self) -> None:
        """Rebuild the file/folder browser shown above the lazy modality table."""
        tree = getattr(self, "lazy_loader_tree", None)
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if tree is None or manifest is None:
            return
        self._sync_lazy_loader_sources()
        frame = manifest.to_frame()
        current = tree.currentItem()
        current_path = str(current.data(0, QtCore.Qt.ItemDataRole.UserRole)) if current is not None else ""
        tree.blockSignals(True)
        tree.clear()
        items = {}
        for row in frame.itertuples(index=False):
            item = QtWidgets.QTreeWidgetItem([str(row.name)])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(row.path))
            item.setToolTip(0, str(row.path))
            items[str(row.path)] = item
            parent_path = str(row.parent_path) if row.parent_path else ""
            if parent_path and parent_path in items:
                items[parent_path].addChild(item)
            else:
                tree.addTopLevelItem(item)
        if current_path and current_path in items:
            tree.setCurrentItem(items[current_path])
        elif tree.topLevelItemCount() > 0:
            tree.setCurrentItem(tree.topLevelItem(0))
        tree.expandAll()
        tree.blockSignals(False)

    def _sync_lazy_loader_selectors(self) -> None:
        """Refresh image selector widgets from controller-owned state."""
        names = [str(getattr(img, "name", f"Image {idx}")) for idx, img in enumerate(getattr(self, "images", []) or [])]
        current_primary = int(getattr(self, "current_image_idx", 0))
        current_support = int(getattr(self, "support_image_idx", 0))
        fov_list = getattr(self, "fov_list", None)
        if fov_list is not None:
            fov_list.blockSignals(True)
            fov_list.clear()
            fov_list.addItems(names)
            if names:
                fov_list.setCurrentRow(max(0, min(current_primary, len(names) - 1)))
            fov_list.blockSignals(False)
        for combo_name, current_index in (("primary_combo", current_primary), ("support_combo", current_support)):
            combo = getattr(self, combo_name, None)
            if combo is None:
                continue
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            if names:
                combo.setCurrentIndex(max(0, min(current_index, len(names) - 1)))
            combo.blockSignals(False)

    def _open_lazy_loader_dialog(self) -> None:
        """Open a small menu that can add files or folders through one button."""
        btn = getattr(self, "lazy_open_btn", None)
        if btn is None:
            return
        menu = QtWidgets.QMenu(btn)
        menu.addAction("Open image…", self._open_lazy_loader_files)
        menu.addAction("Open folder…", self._open_lazy_loader_folder)
        menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _open_lazy_loader_files(self) -> None:
        """Append selected TIFF files to the lazy loader."""
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            LAZY_LOADER_OPEN_FILES_TITLE,
            str(Path.home()),
            LAZY_LOADER_FILE_FILTER,
        )
        if not paths:
            return
        self._add_paths_to_lazy_loader([Path(path) for path in paths])

    def _open_lazy_loader_folder(self) -> None:
        """Append TIFF files discovered in a selected folder to the lazy loader."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            LAZY_LOADER_OPEN_FOLDER_TITLE,
            str(Path.home()),
        )
        if not folder:
            return
        self._add_paths_to_lazy_loader([Path(folder)])

    def _add_paths_to_lazy_loader(self, paths: list[Path]) -> None:
        """Load files/folders into the session and show them in the lazy loader.

        The controller remains the owner of image/session state. This helper
        only discovers metadata, appends images through the controller, and
        requests an asynchronous UI refresh from the resulting state change.
        """
        if getattr(self, "controller", None) is None:
            return
        roots = [Path(path) for path in paths if path]
        if not roots:
            return
        path_to_ids = dict(getattr(self, "_lazy_loader_path_to_ids", {}) or {})
        new_images = []
        base_id = len(getattr(self, "images", []) or [])
        for root in roots:
            for file_path in iter_tiff_paths(root):
                key = str(file_path)
                if key in path_to_ids:
                    continue
                image = read_metadata(file_path)
                image.id = base_id + len(new_images)
                path_to_ids[key] = [int(image.id)]
                new_images.append(image)
        if new_images:
            self.controller.add_images(new_images)
        self._lazy_loader_path_to_ids = path_to_ids
        self._lazy_loader_manifest.add_paths(roots, path_to_ids)
        self._ensure_lazy_loader_base_modalities()
        self._schedule_lazy_panel_sync("lazy-loader-open")

    def _undo_lazy_loader_removal(self) -> bool:
        """Restore the latest removed loader entry."""
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None:
            return False
        restored = manifest.undo_last_removal()
        if not restored:
            return False
        self._reconcile_lazy_loader_sources()
        self._schedule_lazy_panel_sync("lazy-loader-undo")
        self._status_success("Restored removed loader entry.", source="ui_extra.lazy_loader")
        return True

    def _reconcile_lazy_loader_sources(self) -> None:
        """Move selections away from files removed from the loader manifest."""
        visible_ids = self._lazy_loader_visible_image_ids()
        if not visible_ids:
            return
        fallback_id = int(visible_ids[0])
        if int(getattr(self, "current_image_idx", fallback_id)) not in visible_ids:
            self.current_image_idx = fallback_id
        if int(getattr(self, "support_image_idx", fallback_id)) not in visible_ids:
            self.support_image_idx = fallback_id
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        for modality in manager.get_all_modalities():
            if int(modality.image_id) not in visible_ids:
                modality.image_id = fallback_id

    def _ensure_lazy_loader_base_modalities(self) -> None:
        """Populate base frame/support rows when the modality manager is empty."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system
        from phage_annotator.session.modality import ProjectionType

        manager = ensure_modality_system(self.controller.session_state)
        if manager.get_all_modalities():
            return
        visible_ids = self._lazy_loader_visible_image_ids()
        if not visible_ids:
            return
        manager.add_modality(int(visible_ids[0]), "Modality 1", ProjectionType.RAW)
        self._panel_visibility["frame"] = True
        if len(visible_ids) > 1:
            manager.add_modality(int(visible_ids[1]), "Modality 2", ProjectionType.RAW)
            self._panel_visibility["support"] = True

    def _request_lazy_canvas_refresh(self, reason: str, *, refresh_table: bool = True) -> None:
        """Queue a lazy-panel refresh on the Qt event loop.

        ``reason`` is retained for diagnostics and for future routing through
        the shared state core trigger stream.
        """
        self._lazy_apply_table_refresh = bool(getattr(self, "_lazy_apply_table_refresh", False) or refresh_table)
        self._lazy_refresh_reason = str(reason)
        btn = getattr(self, "lazy_apply_btn", None)
        if btn is not None:
            btn.setEnabled(not bool(getattr(self, "lazy_auto_update_chk", None) and self.lazy_auto_update_chk.isChecked()))
        if bool(getattr(self, "lazy_auto_update_chk", None) and self.lazy_auto_update_chk.isChecked()):
            self._lazy_apply_timer.start()

    def _flush_lazy_canvas_refresh(self) -> None:
        """Apply queued table/tree changes to the canvas asynchronously."""
        if bool(getattr(self, "_lazy_apply_table_refresh", False)):
            # Rebuild browser + controls first, then render once from the latest state.
            self._sync_lazy_loader_selectors()
            self._refresh_lazy_modality_table()
            self._refresh_lazy_loader_tree()
        self._reconcile_lazy_loader_sources()
        self._refresh_annotation_view_controls()
        self._request_ui_refresh("lazy-panel-flush")
        self._lazy_apply_table_refresh = False
        btn = getattr(self, "lazy_apply_btn", None)
        if btn is not None:
            btn.setEnabled(False)

    def _sync_mode_toolbutton(self, table, role_key, mode_key: str):
        """Create compact lazy-table sync mode toggle button (C/Z/P)."""
        mk = str(mode_key).strip().lower()
        label = {"contrast": "C", "zoom": "Z", "playback": "P"}.get(mk, "?")
        tooltip = {
            "contrast": "Sync contrast for this row's Sync Group",
            "zoom": "Sync zoom/pan for this row's Sync Group",
            "playback": "Sync playback for this row's Sync Group",
        }.get(mk, "Sync mode")
        btn = QtWidgets.QToolButton(table)
        btn.setText(label)
        btn.setCheckable(True)
        btn.setAutoRaise(False)
        btn.setFixedWidth(24)
        btn.setEnabled(True)  # Explicitly enable the button
        btn.setToolTip(tooltip)
        btn.setProperty("syncMode", mk)
        btn.setProperty("roleKey", role_key)
        btn.setChecked(bool(self._sync_modes_for_role(role_key).get(mk, True)))
        btn.toggled.connect(
            lambda checked, rk=role_key, mode=mk: self._set_sync_mode_for_role(
                rk, mode, bool(checked)
            )
        )
        return btn

    def _role_key_for_lazy_row(self, row: int):
        """Return role key (int or builtin:*) for a lazy-table row."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return None
        item = table.item(row, LAZY_TABLE_COLUMN_NAME)
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
        col = {
            "contrast": LAZY_TABLE_COLUMN_SYNC_CONTRAST,
            "zoom": LAZY_TABLE_COLUMN_SYNC_VIEW,
            "playback": LAZY_TABLE_COLUMN_SYNC_TIME,
        }[mk]
        role_set = set(role_keys or set())
        for row in range(table.rowCount()):
            rk = self._role_key_for_lazy_row(row)
            if rk not in role_set:
                continue
            widget = table.cellWidget(row, col)
            if widget is None:
                continue
            target_checked = bool(self._sync_modes_for_role(rk).get(mk, True))
            widget.blockSignals(True)
            try:
                if hasattr(widget, "setChecked"):
                    widget.setChecked(target_checked)
            finally:
                widget.blockSignals(False)

    def _ensure_lazy_sync_group_keys(self) -> None:
        """Ensure every lazy modality/view row has a numeric sync key (default to 1)."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        row_specs = self._lazy_table_row_specs(manager)
        normalized_groups = normalize_lazy_sync_groups(
            row_specs,
            self._lazy_sync_groups_state(),
        )
        for role_key, group_key in normalized_groups.items():
            self._set_lazy_sync_group_for_role(role_key, group_key)
        self._ensure_lazy_sync_modes()

    def _add_lazy_modality_view(self, projection_key: str) -> None:
        """Add a new modality/view row and reflect it immediately on canvas."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system
        from phage_annotator.session.modality import ProjectionType

        proj_key = str(projection_key).strip().lower()
        if proj_key in {"mean", "std"}:
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            cfg = dict(builtin.get(proj_key, {}) or {})
            cfg["projection"] = proj_key
            cfg.setdefault("name", "Mean Projection" if proj_key == "mean" else "Std Projection")
            cfg.setdefault("image_id", int(getattr(self, "current_image_idx", 0)))
            builtin[proj_key] = cfg
            self._lazy_builtin_views = builtin
            self._panel_visibility[proj_key] = True
            self._ensure_lazy_sync_group_keys()
            self._request_lazy_canvas_refresh("lazy-add-builtin", refresh_table=True)
            return

        manager = ensure_modality_system(self.controller.session_state)
        proj = {
            "raw": ProjectionType.RAW,
            "mean": ProjectionType.MEAN,
            "std": ProjectionType.STD,
            "min": ProjectionType.MIN,
            "max": ProjectionType.MAX,
        }.get(proj_key, ProjectionType.RAW)
        try:
            modality = manager.add_modality(
                image_id=int(getattr(self, "current_image_idx", 0)),
                projection_type=proj,
            )
        except Exception as exc:
            self._status_error(f"Could not add modality/view: {exc}", source="ui_extra.lazy_loader")
            return
        self._panel_visibility[f"modality_{int(modality.idx)}"] = True
        self._ensure_lazy_sync_group_keys()
        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        if hasattr(self, "_refresh_modality_layers_panel"):
            self._refresh_modality_layers_panel()
        self._request_lazy_canvas_refresh("lazy-add-view", refresh_table=True)

    def _remove_selected_lazy_modality_view(self) -> None:
        """Remove the selected file/folder entry from the lazy loader tree."""
        tree = getattr(self, "lazy_loader_tree", None)
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if tree is None or manifest is None:
            return
        item = tree.currentItem()
        if item is None:
            return
        path = str(item.data(0, QtCore.Qt.ItemDataRole.UserRole) or "")
        if not path:
            return
        removed_ids = set(manifest.subtree_image_ids(path))
        remaining = [image_id for image_id in self._lazy_loader_visible_image_ids() if image_id not in removed_ids]
        if not remaining and manifest.contains(path):
            self._status_warning(
                "At least one loaded image must remain in the lazy loader.",
                source="ui_extra.lazy_loader",
            )
            return
        if not manifest.remove_path(path):
            return
        self._refresh_lazy_loader_tree()
        self._reconcile_lazy_loader_sources()
        self._request_lazy_canvas_refresh("lazy-loader-remove", refresh_table=True)
        self._status_success(f"Removed loader entry: {Path(path).name}", source="ui_extra.lazy_loader")

    def _on_lazy_modality_item_changed(self, item) -> None:
        """Handle lazy-table inline rename and propagate to canvas titles."""
        if item is None or getattr(self, "controller", None) is None:
            return
        col = int(item.column())
        if col not in (LAZY_TABLE_COLUMN_NAME, LAZY_TABLE_COLUMN_GROUP):
            return
        from phage_annotator.session.migration import ensure_modality_system

        role_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        role_text = str(role_data)
        if role_text.startswith("builtin:"):
            panel_key = role_text.split(":", 1)[1]
            if col == LAZY_TABLE_COLUMN_GROUP:
                new_key = self._set_lazy_sync_group_for_role(
                    f"builtin:{panel_key}",
                    item.text(),
                )
                item.setText(new_key)
                self._status_info("Sync group updated.", source="ui_extra.lazy_loader")
                return
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            cfg = dict(builtin.get(panel_key, {}) or {})
            cfg["name"] = str(item.text()).strip() or cfg.get("name", panel_key.title())
            builtin[panel_key] = cfg
            self._lazy_builtin_views = builtin
            self._request_lazy_canvas_refresh("lazy-builtin-rename", refresh_table=False)
            return

        modality_idx = int(role_data)
        if col == LAZY_TABLE_COLUMN_GROUP:
            new_key = self._set_lazy_sync_group_for_role(
                int(modality_idx),
                item.text(),
            )
            item.setText(new_key)
            self._status_info("Sync group updated.", source="ui_extra.lazy_loader")
            return
        new_name = str(item.text()).strip()
        if not new_name:
            return
        manager = ensure_modality_system(self.controller.session_state)
        try:
            manager.rename_modality(modality_idx, new_name)
        except Exception as exc:
            self._status_error(f"Rename rejected: {exc}", source="ui_extra.lazy_loader")
            return
        self._request_lazy_canvas_refresh("lazy-modality-rename", refresh_table=False)

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

    def _on_lazy_auto_update_toggled(self, checked: bool) -> None:
        """Handle auto-update checkbox toggle and persist preference."""
        if hasattr(self, "_settings"):
            self._settings.setValue("lazyModalityAutoUpdate", bool(checked))
        btn = getattr(self, "lazy_apply_btn", None)
        if btn is not None:
            btn.setEnabled(not bool(checked))
        if bool(checked):
            self._request_lazy_canvas_refresh("lazy-auto-update", refresh_table=True)

    def _apply_lazy_pending_updates(self) -> None:
        """Apply lazy modality table changes to canvas (triggered by Update Canvas button or auto-update)."""
        self._lazy_apply_table_refresh = True
        self._flush_lazy_canvas_refresh()

    def _on_lazy_modality_source_changed(self, modality_idx: int, image_id: int) -> None:
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        modality = manager.get_modality(int(modality_idx))
        if modality is None:
            return
        modality.image_id = int(image_id)
        self._request_lazy_canvas_refresh("lazy-source-change", refresh_table=False)

    def _on_lazy_modality_projection_changed(self, modality_idx: int, projection_key: str) -> None:
        if getattr(self, "controller", None) is None:
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
        self._request_lazy_canvas_refresh("lazy-projection-change", refresh_table=False)

    def _on_lazy_builtin_source_changed(self, panel_key: str, image_id: int) -> None:
        """Update source image for built-in mean/std panel rows."""
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(str(panel_key), {}) or {})
        cfg["image_id"] = int(image_id)
        builtin[str(panel_key)] = cfg
        self._lazy_builtin_views = builtin
        self._request_lazy_canvas_refresh("lazy-builtin-source", refresh_table=False)

    def _on_lazy_builtin_projection_changed(self, panel_key: str, projection_key: str) -> None:
        """Update projection type for built-in mean/std panel rows."""
        if str(panel_key) == "support":
            return
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(str(panel_key), {}) or {})
        cfg["projection"] = str(projection_key).strip().lower()
        builtin[str(panel_key)] = cfg
        self._lazy_builtin_views = builtin
        self._request_lazy_canvas_refresh("lazy-builtin-projection", refresh_table=False)

    def _on_lazy_builtin_support_source_changed(self, image_id: int) -> None:
        """Update support panel source image from lazy table."""
        try:
            self._set_support_combo(
                self._image_index_for_id(int(image_id)),
                refresh_lazy_table=False,
            )
        except Exception:
            self.support_image_idx = self._image_index_for_id(int(image_id))
            self._request_lazy_canvas_refresh("lazy-support-source", refresh_table=False)

    def _focus_playback_controls(self) -> None:
        """Focus playback controls in the bottom bar from sidebar launcher page."""
        slider = getattr(self, "t_slider", None)
        if slider is not None:
            slider.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
            self._status_info(
                "Playback controls are active in the bottom bar.",
                timeout_ms=3500,
                source="ui_extra.playback_focus",
            )

    def _sidebar_mode_label_for_stack_index(self, stack_idx: int) -> str:
        """Return the workflow page label associated with the stack index."""
        for action_idx, mapped_idx in dict(getattr(self, "sidebar_panel_indices", {}) or {}).items():
            if int(mapped_idx) != int(stack_idx):
                continue
            actions = getattr(self, "sidebar_actions", []) or []
            if 0 <= int(action_idx) < len(actions):
                return str(actions[int(action_idx)].text()).strip().lower()
            break
        return ""

    def _sidebar_mode_contract(self, mode_label: str) -> dict[str, object]:
        """Return the dock contract for a workflow page.

        The left sidebar declares user intent; this contract determines which
        supporting panels remain visible and which workflow panels should be
        surfaced automatically through the panel manager.
        """
        target = str(mode_label or "").strip().lower()
        contracts: dict[str, dict[str, object]] = {
            "prepare": {
                "keep": {"modality_layers", "status_details", "roi", "roi_manager", "hist"},
                "auto_open": ("modality_layers",),
                "right_mode": None,
            },
            "annotate": {
                "keep": {
                    "annotations",
                    "review_queue",
                    "suggestion_explain",
                    "modality_layers",
                    "status_details",
                    "roi",
                    "hist",
                },
                "auto_open": ("annotations",),
                "right_mode": "annotate",
            },
            "review / qc": {
                "keep": {
                    "annotations",
                    "review_queue",
                    "suggestion_explain",
                    "qc_issues",
                    "status_details",
                    "hist",
                },
                "auto_open": ("review_queue", "qc_issues"),
                "right_mode": "review",
            },
            "advanced": {
                "keep": {
                    "annotations",
                    "status_details",
                    "advanced_analysis",
                    "threshold",
                    "particles",
                    "results",
                    "density",
                    "orthoview",
                    "smlm",
                    "metadata",
                },
                "auto_open": ("advanced_analysis", "results"),
                "right_mode": None,
            },
            "export / settings": {
                "keep": {"annotations", "status_details", "performance", "logs"},
                "auto_open": (),
                "right_mode": None,
            },
        }
        return contracts.get(target, {"keep": set(), "auto_open": (), "right_mode": None})

    def _collapse_sidebar_context_docks_for_stack_index(self, stack_idx: int) -> None:
        """Collapse context docks from previous mode; keep only workflow-relevant panels."""
        mode_label = self._sidebar_mode_label_for_stack_index(stack_idx)
        keep = set(self._sidebar_mode_contract(mode_label).get("keep", set()))
        managed = {
            "annotations",
            "review_queue",
            "suggestion_explain",
            "advanced_analysis",
            "modality_layers",
            "status_details",
            "qc_issues",
            "roi",
            "roi_manager",
            "results",
            "orthoview",
            "density",
            "smlm",
            "threshold",
            "particles",
            "performance",
            "logs",
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

    def _apply_sidebar_mode_defaults_for_stack_index(self, stack_idx: int) -> None:
        """Apply default supporting docks for the active workflow page."""
        mode_label = self._sidebar_mode_label_for_stack_index(stack_idx)
        contract = self._sidebar_mode_contract(mode_label)
        right_mode = contract.get("right_mode")
        if isinstance(right_mode, str) and hasattr(self, "_set_right_dock_mode"):
            self._set_right_dock_mode(right_mode)
        for panel_id in tuple(contract.get("auto_open", ())):
            self.open_panel(str(panel_id), reason=f"sidebar_mode:{mode_label}")

    def _sidebar_action_index_for_label(self, label: str) -> int:
        """Return sidebar action index by label, or -1 if not found."""
        want = str(label).strip().lower()
        for i, act in enumerate(getattr(self, "sidebar_actions", []) or []):
            if str(act.text()).strip().lower() == want:
                return i
        return -1

    def open_preferences(self, section: str | None = None) -> None:
        """Open Export / Settings and optionally focus a specific settings section."""
        if getattr(self, "dock_sidebar", None) is not None:
            self.set_panel_visible("sidebar", True, source="open_preferences")
        self._expand_sidebar()
        pref_idx = self._sidebar_action_index_for_label("Export / Settings")
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
            "dock_qc_issues",
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
        keys = ("annotations", "review_queue", "suggestion_explain", "qc_issues")
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
            self._status_info("Review Context Pack enabled.", source="ui_extra.review_pack")
        else:
            self.set_panel_visible("annotations", True, source="review_context_pack")
            self.set_panel_visible("review_queue", False, source="review_context_pack")
            self.set_panel_visible("suggestion_explain", False, source="review_context_pack")
            self.set_panel_visible("qc_issues", False, source="review_context_pack")
            self.set_panel_visible("status_details", False, source="review_context_pack")
            self._status_info("Review Context Pack collapsed to table.", source="ui_extra.review_pack")

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
        self._status_success("Layout restored.", timeout_ms=3000, source="ui_extra.layout")

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
                "qc_issues": True,
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
                "qc_issues": True,
                "modality_layers": False,
            },
            "Assist Expert": {
                "sidebar": True,
                "annotations": True,
                "review_queue": True,
                "suggestion_explain": True,
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
                "modality_layers": True,
                "orthoview": False,
            },
        }

        preset_sidebar = {
            "Default": ("Prepare", False),
            "Minimal": (None, False),
            "Annotate": ("Annotate", True),
            "Analyze": ("Advanced", True),
            "Assist Expert": ("Review / QC", True),
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
        for fig_name in ("hist_fig", "profile_fig"):
            fig = getattr(self, fig_name, None)
            if fig is not None:
                fig.clear()
        QtWidgets.QMainWindow.closeEvent(self, event)
    def _lazy_table_row_specs(self, manager) -> list[LazyTableRowSpec]:
        """Return the complete lazy-table row set from current state.

        This is the single derived source for the loader table. File/folder
        membership comes from the lazy loader manifest, while panel behavior
        comes from controller modality state plus explicit UI/runtime flags.
        """
        specs: list[LazyTableRowSpec] = []
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        hidden_base = set(getattr(self, "_lazy_hidden_base_panel_keys", set()) or set())
        panel_visibility = dict(getattr(self, "_panel_visibility", {}) or {})
        point_visibility = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        groups = self._lazy_sync_groups_state()
        for modality in manager.get_all_modalities():
            panel_key = self._panel_key_for_modality_idx(int(modality.idx))
            if panel_key in hidden_base and int(modality.idx) <= 1:
                continue
            context = self.controller.ensure_annotation_context_for_panel(panel_key, writable=True)
            binding = self.controller.annotation_binding_for_panel(panel_key)
            specs.append(
                LazyTableRowSpec(
                    role_key=int(modality.idx),
                    panel_key=panel_key,
                    panel_name=str(modality.display_name),
                    source_image_id=int(modality.image_id),
                    projection_key=str(modality.projection_type.value),
                    group_key=str(groups.get(int(modality.idx), "")),
                    visible=bool(panel_visibility.get(panel_key, True)),
                    show_points=bool(point_visibility.get(panel_key, True)),
                    sync_contrast=bool(self._sync_modes_for_role(int(modality.idx)).get("contrast", True)),
                    sync_view=bool(self._sync_modes_for_role(int(modality.idx)).get("zoom", True)),
                    sync_time=bool(self._sync_modes_for_role(int(modality.idx)).get("playback", True)),
                    annotation_mode=str(context.get("mode", "independent")),
                    annotation_writable=bool(context.get("writable", True)),
                    annotation_context_key=str(context.get("context_key", "")),
                    annotation_binding_path=str(binding.get("path", "")),
                )
            )
        has_support = any(spec.panel_key == "support" for spec in specs)
        if not has_support and "support" not in hidden_base:
            support_name = "Support View"
            support_combo = getattr(self, "support_combo", None)
            support_image_id = 0
            if support_combo is not None and support_combo.count() > 0:
                idx = int(getattr(self, "support_image_idx", support_combo.currentIndex()))
                if 0 <= idx < support_combo.count():
                    support_name = f"Support View ({support_combo.itemText(idx)})"
                    support_image_id = int(support_combo.itemData(idx))
            elif getattr(self, "support_image", None) is not None:
                support_image_id = int(getattr(self.support_image, "id", 0))
            specs.append(
                LazyTableRowSpec(
                    role_key="builtin:support",
                    panel_key="support",
                    panel_name=support_name,
                    source_image_id=int(support_image_id),
                    projection_key="raw",
                    group_key=str(groups.get("builtin:support", "")),
                    visible=bool(panel_visibility.get("support", True)),
                    show_points=bool(point_visibility.get("support", True)),
                    sync_contrast=bool(self._sync_modes_for_role("builtin:support").get("contrast", True)),
                    sync_view=bool(self._sync_modes_for_role("builtin:support").get("zoom", True)),
                    sync_time=bool(self._sync_modes_for_role("builtin:support").get("playback", True)),
                    annotation_mode=str(self.controller.ensure_annotation_context_for_panel("support", writable=True).get("mode", "independent")),
                    annotation_writable=bool(self.controller.ensure_annotation_context_for_panel("support", writable=True).get("writable", True)),
                    annotation_context_key=str(self.controller.ensure_annotation_context_for_panel("support", writable=True).get("context_key", "")),
                    annotation_binding_path=str(self.controller.annotation_binding_for_panel("support").get("path", "")),
                    projection_editable=False,
                )
            )
        for panel_key in ("mean", "std"):
            if panel_key not in builtin:
                continue
            cfg = dict(builtin.get(panel_key, {}) or {})
            specs.append(
                LazyTableRowSpec(
                    role_key=f"builtin:{panel_key}",
                    panel_key=panel_key,
                    panel_name=str(cfg.get("name", f"{panel_key.title()} Projection")),
                    source_image_id=int(cfg.get("image_id", 0)),
                    projection_key=str(cfg.get("projection", panel_key)).strip().lower(),
                    group_key=str(groups.get(f"builtin:{panel_key}", "")),
                    visible=bool(panel_visibility.get(panel_key, True)),
                    show_points=bool(point_visibility.get(panel_key, True)),
                    sync_contrast=bool(self._sync_modes_for_role(f"builtin:{panel_key}").get("contrast", True)),
                    sync_view=bool(self._sync_modes_for_role(f"builtin:{panel_key}").get("zoom", True)),
                    sync_time=bool(self._sync_modes_for_role(f"builtin:{panel_key}").get("playback", True)),
                    annotation_mode=str(self.controller.ensure_annotation_context_for_panel(panel_key, writable=True).get("mode", "independent")),
                    annotation_writable=bool(self.controller.ensure_annotation_context_for_panel(panel_key, writable=True).get("writable", True)),
                    annotation_context_key=str(self.controller.ensure_annotation_context_for_panel(panel_key, writable=True).get("context_key", "")),
                    annotation_binding_path=str(self.controller.annotation_binding_for_panel(panel_key).get("path", "")),
                )
            )
        return specs

    def _image_index_for_id(self, image_id: int) -> int:
        """Return the current image-list index for an image id.

        Lazy-table source selectors use stable image ids as their row state,
        while several legacy display selectors still work with combo indices.
        This keeps the table source-of-truth on image ids and only adapts at
        the display-control boundary when needed.
        """
        want = int(image_id)
        for idx, image in enumerate(getattr(self, "images", []) or []):
            if int(getattr(image, "id", -1)) == want:
                return int(idx)
        return 0

    def _centered_lazy_checkbox(self, table, *, checked: bool, tooltip: str, on_toggled):
        """Create a centered checkbox cell for the lazy table."""
        container = QtWidgets.QWidget(table)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        checkbox = QtWidgets.QCheckBox(container)
        checkbox.setChecked(bool(checked))
        checkbox.setToolTip(str(tooltip))
        checkbox.toggled.connect(on_toggled)
        layout.addWidget(checkbox)
        container._checkbox = checkbox  # type: ignore[attr-defined]
        return container

    def _lazy_checkbox_from_cell(self, widget):
        """Return the actual checkbox stored inside a centered checkbox cell."""
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget
        return getattr(widget, "_checkbox", None)

    def _default_annotation_binding_path_for_panel(self, panel_key: str) -> Path:
        """Return a default annotation filename for one selected lazy-row panel."""
        binding = self.controller.annotation_binding_for_panel(panel_key)
        if binding.get("path"):
            return Path(str(binding["path"]))
        context = self.controller.ensure_annotation_context_for_panel(panel_key, writable=True)
        source_image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", 0)))
        source_image = next(
            (
                img for img in getattr(self, "images", [])
                if int(getattr(img, "id", -1)) == source_image_id
            ),
            self.primary_image,
        )
        source_path = Path(str(getattr(source_image, "path", self.primary_image.path)))
        suffix = str(context.get("panel_key", panel_key)).strip().lower() or "frame"
        return source_path.with_name(f"{source_path.stem}.{suffix}.annotations.json")

    def _set_lazy_annotation_context_mode_for_panel(self, panel_key: str, mode: str) -> None:
        """Apply annotation ownership mode for one lazy-table row/panel."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        self.controller.set_annotation_context_mode_for_panel(panel_key, mode)
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        self._request_lazy_canvas_refresh("lazy-annotation-context", refresh_table=True)
        self._status_info("Annotation ownership updated.", source="ui_extra.lazy_loader")

    def _bind_lazy_annotation_file_for_panel(self, panel_key: str) -> None:
        """Bind or rebind one lazy-row annotation context to a file."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        default_path = self._default_annotation_binding_path_for_panel(panel_key)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Bind Annotation File",
            str(default_path),
            "Annotation Files (*.json *.csv)",
        )
        if not path:
            return
        selected = Path(path)
        suffix = selected.suffix.lower()
        fmt = "json" if suffix == ".json" else "csv" if suffix == ".csv" else "other"
        self.controller.bind_annotation_file_to_panel(
            panel_key,
            str(selected),
            fmt=fmt,
            mtime=selected.stat().st_mtime if selected.exists() else None,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._refresh_lazy_modality_table()
        self._status_success("Annotation file binding updated.", source="ui_extra.lazy_loader")

    def _load_lazy_annotation_binding_for_panel(self, panel_key: str) -> None:
        """Load annotations from the bound file for one lazy-table row/panel."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        binding = self.controller.annotation_binding_for_panel(panel_key)
        path = str(binding.get("path", "") or "")
        if not path:
            return
        file_path = Path(path)
        if not file_path.exists():
            self._status_warning("Bound annotation file is missing.", source="ui_extra.lazy_loader")
            return
        context = self.controller.ensure_annotation_context_for_panel(panel_key, writable=True)
        source_image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", 0)))
        cal = self._get_calibration_state(source_image_id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        try:
            points, imports = self.controller._parse_annotations_from_paths(
                [file_path],
                image_id=source_image_id,
                pixel_size_nm=pixel_size_nm,
                force_image_id=source_image_id,
                context_panel_key=panel_key,
            )
        except Exception as exc:
            self._status_error(f"Could not load bound annotations: {exc}", source="ui_extra.lazy_loader")
            return
        self.controller._record_annotation_imports(imports)
        self.controller.replace_annotations(source_image_id, points)
        self.controller.bind_annotation_file_to_panel(
            panel_key,
            str(file_path),
            fmt=str(binding.get("format", "other")),
            mtime=file_path.stat().st_mtime if file_path.exists() else None,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._request_ui_refresh("lazy-binding-load", table=True, image=True, status=True)
        self._status_success("Loaded bound annotations.", source="ui_extra.lazy_loader")

    def _clear_lazy_annotation_binding_for_panel(self, panel_key: str) -> None:
        """Clear the bound annotation file for one lazy-table row/panel."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        self.controller.clear_annotation_binding_for_panel(
            panel_key,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._refresh_lazy_modality_table()
        self._status_info("Annotation file binding cleared.", source="ui_extra.lazy_loader")

    def _insert_lazy_table_row(self, table, row_spec: LazyTableRowSpec) -> None:
        """Insert one derived row into the lazy-loading table."""
        source_images = list(self._lazy_loader_source_images())
        projection_options = ("raw", "mean", "std", "min", "max")
        projection_labels = {
            "raw": "Source Frame",
            "mean": "Mean",
            "std": "Std",
            "min": "Min",
            "max": "Max",
        }
        row = table.rowCount()
        table.insertRow(row)
        visible_widget = self._centered_lazy_checkbox(
            table,
            checked=row_spec.visible,
            tooltip="Show or hide this panel on the canvas.",
            on_toggled=lambda checked, k=row_spec.panel_key: self._on_panel_toggle(str(k), bool(checked)),
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_SHOW, visible_widget)
        points_widget = self._centered_lazy_checkbox(
            table,
            checked=row_spec.show_points,
            tooltip="Show annotation points on this panel.",
            on_toggled=lambda checked, k=row_spec.panel_key: self._on_annotation_panel_toggle(str(k), bool(checked)),
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_POINTS, points_widget)

        name_item = QtWidgets.QTableWidgetItem(str(row_spec.panel_name))
        name_item.setData(QtCore.Qt.ItemDataRole.UserRole, row_spec.role_key)
        binding_txt = str(row_spec.annotation_binding_path or "Unbound")
        mode_map = {
            "shared_source": "Shared with source",
            "independent": "Independent",
            "read_only": "Read-only overlay",
        }
        mode_txt = str(mode_map.get(str(row_spec.annotation_mode), str(row_spec.annotation_mode).title()))
        name_item.setToolTip(
            f"Annotation mode: {mode_txt}\n"
            f"Writable: {'yes' if row_spec.annotation_writable else 'no'}\n"
            f"Context: {row_spec.annotation_context_key or 'unresolved'}\n"
            f"Binding: {binding_txt}"
        )
        table.setItem(row, LAZY_TABLE_COLUMN_NAME, name_item)

        source_combo = QtWidgets.QComboBox(table)
        for img in source_images:
            source_combo.addItem(str(getattr(img, "name", f"Image {img.id}")), int(img.id))
        src_idx = max(0, source_combo.findData(int(row_spec.source_image_id)))
        source_combo.setCurrentIndex(src_idx)
        if str(row_spec.role_key) == "builtin:support":
            source_combo.currentIndexChanged.connect(
                lambda _i, combo=source_combo: self._on_lazy_builtin_support_source_changed(int(combo.currentData()))
            )
        elif isinstance(row_spec.role_key, str) and str(row_spec.role_key).startswith("builtin:"):
            panel_key = str(row_spec.role_key).split(":", 1)[1]
            source_combo.currentIndexChanged.connect(
                lambda _i, k=panel_key, combo=source_combo: self._on_lazy_builtin_source_changed(
                    str(k), int(combo.currentData())
                )
            )
        else:
            source_combo.currentIndexChanged.connect(
                lambda _i, mid=int(row_spec.role_key), combo=source_combo: self._on_lazy_modality_source_changed(
                    mid, int(combo.currentData())
                )
            )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_SOURCE, source_combo)

        view_combo = QtWidgets.QComboBox(table)
        for projection in projection_options:
            view_combo.addItem(str(projection_labels.get(projection, projection.title())), projection)
        proj_idx = max(0, view_combo.findData(str(row_spec.projection_key).strip().lower()))
        view_combo.setCurrentIndex(proj_idx)
        view_combo.setEnabled(bool(row_spec.projection_editable))
        if isinstance(row_spec.role_key, str) and str(row_spec.role_key).startswith("builtin:"):
            panel_key = str(row_spec.role_key).split(":", 1)[1]
            view_combo.currentIndexChanged.connect(
                lambda _i, k=panel_key, combo=view_combo: self._on_lazy_builtin_projection_changed(
                    str(k), str(combo.currentData())
                )
            )
        else:
            view_combo.currentIndexChanged.connect(
                lambda _i, mid=int(row_spec.role_key), combo=view_combo: self._on_lazy_modality_projection_changed(
                    mid, str(combo.currentData())
                )
            )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_PROJECTION, view_combo)

        owner_combo = QtWidgets.QComboBox(table)
        owner_combo.addItem("Independent", "independent")
        owner_combo.addItem("Shared", "shared_source")
        owner_combo.addItem("Read-only", "read_only")
        owner_idx = max(0, owner_combo.findData(str(row_spec.annotation_mode or "independent")))
        owner_combo.setCurrentIndex(owner_idx)
        owner_combo.setToolTip(
            "Choose whether this row owns its annotations, shares the source context, or is read-only."
        )
        owner_combo.currentIndexChanged.connect(
            lambda _i, k=row_spec.panel_key, combo=owner_combo: self._set_lazy_annotation_context_mode_for_panel(
                str(k),
                str(combo.currentData()),
            )
        )
        table.setCellWidget(row, LAZY_TABLE_COLUMN_ANNOTATION_MODE, owner_combo)

        file_btn = QtWidgets.QToolButton(table)
        file_btn.setText("Bound" if row_spec.annotation_binding_path else "Unbound")
        file_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        file_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        file_btn.setToolTip(
            "Manage the annotation file linked to this row.\n"
            f"Current: {Path(row_spec.annotation_binding_path).name if row_spec.annotation_binding_path else 'Unbound'}"
        )
        menu = QtWidgets.QMenu(file_btn)
        bind_text = "Rebind file…" if row_spec.annotation_binding_path else "Bind file…"
        menu.addAction(bind_text, lambda k=row_spec.panel_key: self._bind_lazy_annotation_file_for_panel(str(k)))
        if row_spec.annotation_binding_path:
            menu.addAction("Load bound annotations", lambda k=row_spec.panel_key: self._load_lazy_annotation_binding_for_panel(str(k)))
            menu.addAction("Clear binding", lambda k=row_spec.panel_key: self._clear_lazy_annotation_binding_for_panel(str(k)))
        file_btn.setMenu(menu)
        table.setCellWidget(row, LAZY_TABLE_COLUMN_ANNOTATION_FILE, file_btn)

        group_item = QtWidgets.QTableWidgetItem(str(row_spec.group_key))
        group_item.setData(QtCore.Qt.ItemDataRole.UserRole, row_spec.role_key)
        group_item.setTextAlignment(
            int(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        )
        table.setItem(row, LAZY_TABLE_COLUMN_GROUP, group_item)
        table.setCellWidget(
            row,
            LAZY_TABLE_COLUMN_SYNC_CONTRAST,
            self._sync_mode_toolbutton(table, row_spec.role_key, "contrast"),
        )
        table.setCellWidget(
            row,
            LAZY_TABLE_COLUMN_SYNC_VIEW,
            self._sync_mode_toolbutton(table, row_spec.role_key, "zoom"),
        )
        table.setCellWidget(
            row,
            LAZY_TABLE_COLUMN_SYNC_TIME,
            self._sync_mode_toolbutton(table, row_spec.role_key, "playback"),
        )
