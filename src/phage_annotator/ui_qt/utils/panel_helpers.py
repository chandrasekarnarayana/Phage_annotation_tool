"""Standalone utility helpers for dock panel management.

These helpers have no dependencies on GUI mixin classes,
making them safe to import from any panel management module.
"""

from __future__ import annotations

import logging
from typing import Any, Generator, Optional

from matplotlib.backends.qt_compat import QtWidgets

logger = logging.getLogger(__name__)

PANEL_TAB_GROUPS = {
    "tools_roi": ("roi", "roi_manager", "results", "orthoview", "metadata"),
    "plots_hist": ("hist", "profile"),
    "system": ("logs", "performance", "recorder"),
}

AUTO_REASON_PREFIXES = ("auto", "trigger", "workflow", "suggest")
USER_INTENT_REASONS = {"user", "command_palette", "panel_switcher"}


def _panel_auto_open_key(panel_id: str) -> str:
    return f"panel_auto_open/{panel_id}"


def _panel_pinned_key(panel_id: str) -> str:
    return f"panel_pinned/{panel_id}"


def _panel_auto_open_trigger_key(panel_id: str, trigger: str) -> str:
    return f"panel_auto_open_trigger/{panel_id}/{trigger}"


def _is_auto_reason(reason: str) -> bool:
    reason = str(reason or "").lower().strip()
    if not reason or reason in USER_INTENT_REASONS:
        return False
    return any(reason.startswith(p) for p in AUTO_REASON_PREFIXES) or reason not in USER_INTENT_REASONS


def _auto_trigger_from_reason(reason: str) -> str:
    reason = str(reason or "").lower().strip()
    if not reason or reason in USER_INTENT_REASONS:
        return "default"
    return reason


def _is_user_intent_reason(reason: str) -> bool:
    return str(reason or "").lower().strip() in USER_INTENT_REASONS


def _show_status_message(self: Any, msg: str, timeout: int = 2500) -> None:
    try:
        self.statusBar().showMessage(str(msg), timeout)
    except Exception:
        pass


def _hide_auto_open_toast(self: Any, panel_key: str) -> None:
    notices = getattr(self, "_panel_auto_notice_shown", set())
    notices.discard(str(panel_key))
    self._panel_auto_notice_shown = notices


def _show_auto_open_toast(self: Any, panel_key: str, title: str) -> None:
    _show_status_message(self, f"Panel auto-opened: {title}", 3000)


def _merge_system_docks(self: Any) -> None:
    """Merge logs/performance/recorder into a single tabbed System dock."""
    from phage_annotator.ui_qt.utils.dock_panel_create import create_dock
    from matplotlib.backends.qt_compat import QtCore

    dock_logs = getattr(self, "dock_logs", None)
    dock_perf = getattr(self, "dock_performance", None)
    dock_rec = getattr(self, "dock_recorder", None)
    if dock_logs is None or dock_perf is None or dock_rec is None:
        return
    if getattr(self, "dock_system", None) is not None:
        return

    logs_w = dock_logs.widget()
    perf_w = dock_perf.widget()
    rec_w = dock_rec.widget()
    if logs_w is None or perf_w is None or rec_w is None:
        return

    tabs = QtWidgets.QTabWidget(self)
    tabs.setObjectName("system_tabs")
    tabs.addTab(logs_w, "Logs / Diagnostics")
    tabs.addTab(perf_w, "Performance")
    tabs.addTab(rec_w, "Recorder")

    container = QtWidgets.QWidget(self)
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(tabs)
    self.system_tabs = tabs

    system_dock = create_dock(self, "system", "System", container)
    self.addDockWidget(QtCore.Qt.RightDockWidgetArea, system_dock)
    system_dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
    system_dock.setFloating(False)
    try:
        features = system_dock.features()
        system_dock.setFeatures(features & ~QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
    except Exception:
        pass
    self.dock_system = system_dock

    # Remove old standalone docks and remap panel ids to unified dock.
    for old in (dock_logs, dock_perf, dock_rec):
        try:
            self.removeDockWidget(old)
        except Exception:
            pass
        try:
            old.hide()
        except Exception:
            pass
    self.panel_docks["logs"] = system_dock
    self.panel_docks["performance"] = system_dock
    self.panel_docks["recorder"] = system_dock
    self.panel_docks["system"] = system_dock
    self.dock_logs = system_dock
    self.dock_performance = system_dock
    self.dock_recorder = system_dock


def _select_system_tab_for_panel(self: Any, panel_key: str) -> None:
    """Select the appropriate tab inside merged System dock for a panel id."""
    tabs = getattr(self, "system_tabs", None)
    if tabs is None:
        return
    panel_key = str(panel_key)
    target_idx = {"logs": 0, "performance": 1, "recorder": 2}.get(panel_key)
    if target_idx is None:
        return
    if 0 <= int(target_idx) < int(tabs.count()):
        tabs.setCurrentIndex(int(target_idx))


def _iter_unique_dock_specs(self: Any) -> Generator:
    """Yield first spec for each unique dock object in current panel mapping."""
    seen: set = set()
    for spec in getattr(self, "panel_specs", []) or []:
        dock = getattr(self, "panel_docks", {}).get(spec.id)
        if dock is None:
            continue
        key = id(dock)
        if key in seen:
            continue
        seen.add(key)
        yield spec, dock
