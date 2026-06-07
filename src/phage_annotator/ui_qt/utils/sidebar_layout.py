"""Extracted method group 1 for UiExtrasMixin."""

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



class SidebarLayoutMixin:
    """Method group 1 extracted from UiExtrasMixin."""

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
        self.sidebar_breadcrumb.setText(self.sidebar_manager.breadcrumb_text("Annotation"))
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
                if isinstance(icon, QtGui.QIcon):
                    resolved_icon = icon
                else:
                    resolved_icon = workflow_sidebar_icon(self.style(), str(label))
                act = QtWidgets.QAction(resolved_icon, label, self)
                act.setObjectName(f"sidebar_action_{label.lower().replace('/', '_').replace(' ', '_')}")
                act.setCheckable(True)
                act.setToolTip(label)
                
                # Connect with toggle behavior
                act.triggered.connect(lambda checked, i=page_idx: self._on_sidebar_action_triggered(i))
                self.sidebar_actions.append(act)
                bar.addAction(act)
                
                # Map to stack index.
                self.sidebar_panel_indices[page_idx] = stack_idx
                stack_idx += 1
            
            # Default to Lazy Loading for startup setup tasks.
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
                "Annotation",
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
