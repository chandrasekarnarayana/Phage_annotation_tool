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
    pass


def _select_system_tab_for_panel(self: Any, panel_key: str) -> None:
    pass


def _iter_unique_dock_specs(self: Any) -> Generator:
    seen: set = set()
    for spec in getattr(self, "panel_specs", []) or []:
        if getattr(spec, "id", None) not in seen:
            seen.add(getattr(spec, "id", None))
            yield spec
