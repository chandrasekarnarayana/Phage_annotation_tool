"""Dock panel creation helpers: create_dock, wire_dock_action, apply_panel_defaults."""

from __future__ import annotations

import logging
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.panel_helpers import PANEL_TAB_GROUPS

logger = logging.getLogger(__name__)


PANEL_TAB_GROUPS = {
    # Right inspect panels are intentionally NOT tabified; they are shown as
    # distinct panels via right-sidebar selection.
    "tools_roi": ("roi", "roi_manager", "results", "orthoview", "metadata"),
    "plots_hist": ("hist", "profile"),
    "system": ("logs", "performance", "recorder"),
}
# so placement recipes are defined in one declarative source of truth.



def apply_panel_defaults(self) -> None:
    """Reset dock placement/visibility using PanelSpec defaults."""
    for spec, dock in (self):
        (self, dock, spec)
        self.addDockWidget(spec.default_area, dock)
        dock.setVisible(spec.default_visible)
    for group_id, members in PANEL_TAB_GROUPS.items():
        if len(members) < 2:
            continue
        anchor = self.panel_docks.get(members[0])
        if anchor is None:
            continue
        for member in members[1:]:
            dock = self.panel_docks.get(member)
            if dock is None:
                continue
            try:
                self.tabifyDockWidget(anchor, dock)
            except Exception:
                continue

def create_dock(self, name: str, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QDockWidget:
    """Create a standard dock widget with common features enabled."""
    dock = QtWidgets.QDockWidget(title, self)
    dock.setObjectName(name)
    dock.setWidget(widget)
    dock.setFeatures(
        QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
    return dock

def wire_dock_action(
    self,
    dock: QtWidgets.QDockWidget,
    action: QtWidgets.QAction,
    checkbox: Optional[QtWidgets.QCheckBox] = None) -> None:
    """Keep dock visibility, menu toggle, and optional checkbox in sync."""

    def _set_visible(checked: bool) -> None:
        """Set visible for the current workflow."""
        setter = getattr(self, "set_panel_visible", None)
        panel_id = str(dock.objectName() or "")
        if callable(setter) and panel_id:
            setter(panel_id, bool(checked), source="menu:panels")
        else:
            dock.setVisible(bool(checked))

    def _sync_action(visible: bool) -> None:
        """Synchronize action for the current workflow."""
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
        if checkbox is not None:
            checkbox.blockSignals(True)
            checkbox.setChecked(visible)
            checkbox.blockSignals(False)
            try:
                self._request_ui_refresh("ui-docks")
            except RuntimeError:
                return

    action.toggled.connect(_set_visible)
    dock.visibilityChanged.connect(_sync_action)
