"""Dock panel placement helpers: _apply_panel_constraints, _canonical_area_for_panel, _tabify_group_for_panel."""

from __future__ import annotations

import logging
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.panels.registry import PanelConstraints, PanelSpec
from phage_annotator.ui_qt.utils.panel_helpers import PANEL_TAB_GROUPS

logger = logging.getLogger(__name__)

def _apply_panel_constraints(self, dock: QtWidgets.QDockWidget, spec: PanelSpec) -> None:
    """Apply floatability and allowed-area constraints from PanelSpec."""
    constraints = spec.constraints if isinstance(spec.constraints, PanelConstraints) else PanelConstraints()
    features = QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
    # Exclude close button from sidebar panels (left and right) that have collapse/expand controls
    right_sidebar_panels = {
        "annotations",
        "review_queue",
        "advanced_settings",
        "advanced_analysis",
        "qc_issues",
        "status_details",
    }
    if spec.id not in {"sidebar"} | right_sidebar_panels:
        features |= QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
    if constraints.floatable:
        features |= QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
    dock.setFeatures(features)
    if constraints.allowed_areas:
        allowed = QtCore.Qt.DockWidgetAreas(0)
        for area in constraints.allowed_areas:
            allowed |= area
        dock.setAllowedAreas(allowed)
    else:
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
    if spec.id in right_sidebar_panels:
        dock.setMinimumWidth(360)
        dock.setStyleSheet(
            "QDockWidget { margin: 0px; padding: 0px; }"
            "QDockWidget::title { padding: 6px 8px; font-weight: 600; }"
        )

def _canonical_area_for_panel(self, spec: PanelSpec) -> QtCore.Qt.DockWidgetArea:
    """Return canonical dock area for the panel."""
    constraints = spec.constraints if isinstance(spec.constraints, PanelConstraints) else PanelConstraints()
    if constraints.allowed_areas:
        return constraints.allowed_areas[0]
    return spec.default_area

def _tabify_group_for_panel(self, panel_id: str) -> None:
    """Ensure panel is tabified into its configured group."""
    from phage_annotator.ui_qt.utils.dock_panel_init_chunk1 import get_panel_spec, get_dock
    spec = get_panel_spec(self, panel_id)
    if spec is None or not spec.tab_group:
        return
    group_ids = PANEL_TAB_GROUPS.get(str(spec.tab_group), ())
    if len(group_ids) < 2:
        return
    anchor = get_dock(self, group_ids[0])
    target = get_dock(self, panel_id)
    if anchor is None or target is None or anchor is target:
        return
    try:
        self.tabifyDockWidget(anchor, target)
    except Exception:
        return
