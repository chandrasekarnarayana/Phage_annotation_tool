"""Dock panel policy/registry implementation (auto-open, pinned, trigger state)."""

from __future__ import annotations

import logging
from typing import Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.utils.panel_helpers import (
    _panel_pinned_key,
    _panel_auto_open_trigger_key,
)

logger = logging.getLogger(__name__)


PANEL_TAB_GROUPS = {
    # Right inspect panels are intentionally NOT tabified; they are shown as
    # distinct panels via right-sidebar selection.
    "tools_roi": ("roi", "roi_manager", "results", "orthoview", "metadata"),
    "plots_hist": ("hist", "profile"),
    "system": ("logs", "performance", "recorder"),
}
# so placement recipes are defined in one declarative source of truth.



def _find_tab_for_dock(self, dock: QtWidgets.QDockWidget) -> tuple[Optional[QtWidgets.QTabBar], int]:
    """Find QTabBar/index entry corresponding to a dock title."""
    title = str(dock.windowTitle() or "")
    for bar in self.findChildren(QtWidgets.QTabBar):
        try:
            for idx in range(bar.count()):
                if str(bar.tabText(idx) or "") == title:
                    return bar, idx
        except Exception:
            continue
    return None, -1

def _init_panel_auto_policy_state(self) -> None:
    """Initialize panel auto policy state for the current workflow."""
    settings = getattr(self, "_settings", None)
    self._panel_auto_open_enabled = {}
    self._panel_auto_open_enabled_by_trigger = {}
    self._panel_pinned = {}
    self._panel_opened_by = {}
    self._panel_auto_notice_shown = set()
    for spec in getattr(self, "panel_specs", []) or []:
        panel_id = str(spec.id)
        enabled = True
        pinned = False
        default_auto_open = panel_id not in {"density", "performance", "logs", "qc_issues"}
        if settings is not None:
            try:
                enabled = bool(
                    settings.value(
                        (panel_id),
                        default_auto_open,
                        type=bool)
                )
            except Exception:
                enabled = default_auto_open
        else:
            enabled = default_auto_open
            try:
                pinned = bool(settings.value(_panel_pinned_key(panel_id), False, type=bool))
            except Exception:
                pinned = False
        self._panel_auto_open_enabled[panel_id] = enabled
        self._panel_pinned[panel_id] = pinned

def refresh_panel_policy_actions(self) -> None:
    """Synchronize menu quick-policy action check states from policy state."""
    auto_actions = dict(getattr(self, "panel_policy_quick_auto_actions", {}) or {})
    pin_actions = dict(getattr(self, "panel_policy_quick_pin_actions", {}) or {})
    for panel_id, action in auto_actions.items():
        if action is None:
            continue
        desired = bool(is_panel_auto_open_enabled(self, panel_id))
        if action.isChecked() != desired:
            action.blockSignals(True)
            action.setChecked(desired)
            action.blockSignals(False)
    for panel_id, action in pin_actions.items():
        if action is None:
            continue
        desired = bool(is_panel_pinned(self, panel_id))
        if action.isChecked() != desired:
            action.blockSignals(True)
            action.setChecked(desired)
            action.blockSignals(False)

def is_panel_auto_open_enabled(self, panel_id: str) -> bool:
    """Return whether panel auto open enabled is true for the current state."""
    state = getattr(self, "_panel_auto_open_enabled", {}) or {}
    return bool(state.get(str(panel_id), True))

def is_panel_auto_open_enabled_for_trigger(self, panel_id: str, trigger: str) -> bool:
    """Return whether panel auto open enabled for trigger is true for the current state."""
    trigger_state = getattr(self, "_panel_auto_open_enabled_by_trigger", {}) or {}
    panel_id = str(panel_id)
    trigger = str(trigger or "default")
    panel_map = trigger_state.get(panel_id)
    if not isinstance(panel_map, dict):
        panel_map = {}
        self._panel_auto_open_enabled_by_trigger[panel_id] = panel_map
    if trigger not in panel_map:
        settings = getattr(self, "_settings", None)
        enabled = True
        if settings is not None:
            try:
                enabled = bool(
                    settings.value(
                        _panel_auto_open_trigger_key(panel_id, trigger),
                        True,
                        type=bool)
                )
            except Exception:
                enabled = True
        panel_map[trigger] = enabled
    return bool(panel_map.get(trigger, True))

def set_panel_auto_open_enabled(self, panel_id: str, enabled: bool) -> None:
    """Set panel auto open enabled for the current workflow."""
    key = str(panel_id)
    if not hasattr(self, "_panel_auto_open_enabled") or not isinstance(
        getattr(self, "_panel_auto_open_enabled", None), dict
    ):
        self._panel_auto_open_enabled = {}
    self._panel_auto_open_enabled[key] = bool(enabled)
    settings = getattr(self, "_settings", None)
    if settings is not None:
        try:
            settings.setValue((key), bool(enabled))
        except Exception:
            pass
    refresh_panel_policy_actions(self)
    if hasattr(self, "_refresh_panel_policy_controls"):
        try:
            self._refresh_panel_policy_controls()
        except Exception:
            pass

def set_panel_auto_open_enabled_for_trigger(
    self,
    panel_id: str,
    trigger: str,
    enabled: bool) -> None:
    """Set panel auto open enabled for trigger for the current workflow."""
    panel_key = str(panel_id)
    trigger_key = str(trigger or "default")
    if not isinstance(getattr(self, "_panel_auto_open_enabled_by_trigger", None), dict):
        self._panel_auto_open_enabled_by_trigger = {}
    panel_map = self._panel_auto_open_enabled_by_trigger.get(panel_key)
    if not isinstance(panel_map, dict):
        panel_map = {}
        self._panel_auto_open_enabled_by_trigger[panel_key] = panel_map
    panel_map[trigger_key] = bool(enabled)
    settings = getattr(self, "_settings", None)
    if settings is not None:
        try:
            settings.setValue(
                _panel_auto_open_trigger_key(panel_key, trigger_key),
                bool(enabled))
        except Exception:
            pass

def is_panel_pinned(self, panel_id: str) -> bool:
    """Return whether panel pinned is true for the current state."""
    state = getattr(self, "_panel_pinned", {}) or {}
    return bool(state.get(str(panel_id), False))

def set_panel_pinned(self, panel_id: str, pinned: bool) -> None:
    """Set panel pinned for the current workflow."""
    key = str(panel_id)
    if not hasattr(self, "_panel_pinned") or not isinstance(
        getattr(self, "_panel_pinned", None), dict
    ):
        self._panel_pinned = {}
    self._panel_pinned[key] = bool(pinned)
    settings = getattr(self, "_settings", None)
    if settings is not None:
        try:
            settings.setValue(_panel_pinned_key(key), bool(pinned))
        except Exception:
            pass
    refresh_panel_policy_actions(self)
    if hasattr(self, "_refresh_panel_policy_controls"):
        try:
            self._refresh_panel_policy_controls()
        except Exception:
            pass
