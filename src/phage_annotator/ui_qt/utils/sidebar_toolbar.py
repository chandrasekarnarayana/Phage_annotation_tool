"""Extracted method group 2 for UiExtrasMixin."""

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



class SidebarToolbarMixin:
    """Method group 2 extracted from UiExtrasMixin."""

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
            right_sidebar_icon(self.style(), "annotations"),
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
            right_sidebar_icon(self.style(), "review_queue"),
            "Assist",
            self,
        )
        queue_act.setObjectName("right_sidebar_assist_toggle")
        queue_act.setCheckable(True)
        queue_act.setChecked(False)
        queue_act.setToolTip("Assist: review suggestions, rationale, and accept/reject actions.")
        queue_act.setStatusTip("Open assist review tools for the current context.")
        queue_act.triggered.connect(
            lambda checked=False: self._toggle_assist_sidebar_mode()
        )
        bar.addAction(queue_act)

        advanced_act = QtWidgets.QAction(
            right_sidebar_icon(self.style(), "advanced_settings"),
            "Advanced Settings",
            self,
        )
        advanced_act.setObjectName("right_sidebar_advanced_settings_toggle")
        advanced_act.setCheckable(True)
        advanced_act.setChecked(False)
        advanced_act.setToolTip("Advanced Settings: calibration and expert image/session controls.")
        advanced_act.setStatusTip("Open advanced settings for pixel size, axis interpretation, and metadata access.")
        advanced_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("advanced_settings")
        )
        bar.addAction(advanced_act)

        analysis_act = QtWidgets.QAction(
            right_sidebar_icon(self.style(), "advanced_analysis"),
            "Analysis",
            self,
        )
        analysis_act.setObjectName("right_sidebar_analysis_toggle")
        analysis_act.setCheckable(True)
        analysis_act.setChecked(False)
        analysis_act.setToolTip("Analysis: advanced quantitative and diagnostics tools.")
        analysis_act.setStatusTip("Open advanced analysis tools on the right sidebar.")
        analysis_act.triggered.connect(
            lambda checked=False: self._toggle_right_sidebar_panel("advanced_analysis")
        )
        bar.addAction(analysis_act)

        qc_act = QtWidgets.QAction(
            right_sidebar_icon(self.style(), "qc_issues"),
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

        self.annotation_toolbar = bar
        self.annotation_toolbar_action = table_act
        self.right_sidebar_actions = {
            "annotations": table_act,
            "review_queue": queue_act,
            "advanced_settings": advanced_act,
            "advanced_analysis": analysis_act,
            "qc_issues": qc_act,
        }

        self.addToolBar(QtCore.Qt.RightToolBarArea, bar)

        for panel_id in PRIMARY_RIGHT_SIDEBAR_PANELS:
            dock = getattr(self, f"dock_{panel_id}", None)
            if dock is not None:
                dock.visibilityChanged.connect(self._sync_annotation_toolbar)
                dock.visibilityChanged.connect(lambda _v: self._capture_right_sidebar_width())
        self._ensure_right_sidebar_panels_not_tabified()
        self._sync_annotation_toolbar(True)
    def _primary_right_sidebar_panels(self) -> tuple[str, ...]:
        """Handle the primary right sidebar panels helper flow."""
        return PRIMARY_RIGHT_SIDEBAR_PANELS
    def _all_right_sidebar_panels(self) -> tuple[str, ...]:
        """Handle the all right sidebar panels helper flow."""
        return ALL_RIGHT_SIDEBAR_PANELS
    def _capture_right_sidebar_width(self) -> None:
        """Persist right-sidebar open width for consistent reopen behavior."""
        for panel_id in self._all_right_sidebar_panels():
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
            for panel_id in self._all_right_sidebar_panels()
        ):
            # Only auto-open if sidebar is NOT explicitly collapsed
            if (getattr(self, "dock_annotations", None) is not None 
                and not getattr(self, "_right_sidebar_collapsed", False)
                and not getattr(self, "_right_sidebar_intentionally_closed", False)):
                self.set_panel_visible("annotations", True, source="right_sidebar:auto_default")
    def _toggle_assist_sidebar_mode(self) -> None:
        """Toggle assist as one coherent right-side workflow surface."""
        assist_ids = ("review_queue", "qc_issues")
        assist_visible = any(
            bool(getattr(self, f"dock_{panel_id}", None) and getattr(self, f"dock_{panel_id}").isVisible())
            for panel_id in assist_ids
        )
        annotations_visible = bool(
            getattr(self, "dock_annotations", None) is not None and self.dock_annotations.isVisible()
        )
        if assist_visible and not annotations_visible:
            for panel_id in assist_ids:
                self.set_panel_visible(panel_id, False, source="right_sidebar")
            self._collapse_right_sidebar()
            self._right_sidebar_intentionally_closed = True
            self._sync_annotation_toolbar(False)
            return
        self._set_right_dock_mode("review")
    def _ensure_right_sidebar_panels_not_tabified(self) -> None:
        """Keep right inspect panels as standalone docks (never tab peers)."""
        panel_ids = self._all_right_sidebar_panels()
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
