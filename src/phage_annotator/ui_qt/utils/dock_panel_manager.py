"""Panel management helpers: PanelManager class and open_panel delegate."""

from __future__ import annotations

import logging
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.panel_helpers import (
    _auto_trigger_from_reason,
    _is_user_intent_reason,
    _show_status_message,
    _show_auto_open_toast,
    _select_system_tab_for_panel,
)
from phage_annotator.ui_qt.utils.dock_panel_registry_impl import (
    is_panel_auto_open_enabled,
    is_panel_auto_open_enabled_for_trigger,
    set_panel_pinned,
)
from phage_annotator.ui_qt.utils.dock_panel_init_chunk1 import get_dock
from phage_annotator.ui_qt.utils.dock_panel_init_chunk2 import (
    _apply_panel_constraints,
    _canonical_area_for_panel,
    _tabify_group_for_panel,
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



def _flash_dock(self, dock: QtWidgets.QDockWidget) -> None:
    """Flash the dock tab entry with a short animation (fallback to dock border)."""
    if dock is None:
        return
    tabbar, tab_idx = (self, dock)
    if tabbar is not None and tab_idx >= 0:
        rect = tabbar.tabRect(tab_idx).adjusted(2, 2, -2, -2)
        overlay = QtWidgets.QWidget(tabbar)
        overlay.setObjectName("dock_tab_flash_overlay")
        overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setGeometry(rect)
        overlay.setStyleSheet(
            "#dock_tab_flash_overlay {"
            "background: rgba(30, 136, 229, 120); border-radius: 4px; }"
        )
        effect = QtWidgets.QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        overlay.show()
        anim = QtCore.QPropertyAnimation(effect, b"opacity", overlay)
        anim.setDuration(700)
        anim.setStartValue(0.0)
        anim.setKeyValueAt(0.4, 0.95)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)

        def _cleanup() -> None:
            """Handle the cleanup helper flow."""
            try:
                overlay.hide()
            except Exception:
                pass
            try:
                overlay.deleteLater()
            except Exception:
                pass

        anim.finished.connect(_cleanup)
        if not isinstance(getattr(tabbar, "_flash_anims", None), list):
            tabbar._flash_anims = []
        tabbar._flash_anims.append(anim)
        self._tab_flash_anims = tabbar._flash_anims

        def _remove_anim() -> None:
            """Remove anim for the current workflow."""
            anims = getattr(tabbar, "_flash_anims", None)
            if isinstance(anims, list):
                try:
                    anims.remove(anim)
                except ValueError:
                    pass

        anim.finished.connect(_remove_anim)
        anim.start()
        return

    # Fallback for non-tabified docks.
    original = dock.styleSheet()
    dock.setStyleSheet(
        f"{original}\nQDockWidget {{ border: 2px solid #1976d2; background: #e3f2fd; }}"
    )

    def _restore() -> None:
        """Restore restore for the current workflow."""
        try:
            dock.setStyleSheet(original)
        except RuntimeError:
            return

    QtCore.QTimer.singleShot(650, _restore)

class PanelManager:
    """Single entrypoint for panel open/place/raise/flash behavior."""

    def __init__(self, window) -> None:
        """Initialize the object and prepare its runtime state."""
        self.window = window

    def open_panel(self, panel_id: str, *, reason: str = "user") -> Optional[QtWidgets.QDockWidget]:
        """Open panel for the current workflow."""
        spec = (self.window, panel_id)
        dock = get_dock(self.window, panel_id)
        if spec is None or dock is None:
            return dock
        reason_text = str(reason or "user")
        is_auto = (reason_text)
        panel_key = str(panel_id)
        auto_trigger = _auto_trigger_from_reason(reason_text)
        if is_auto and not is_panel_auto_open_enabled(self.window, panel_key):
            _show_status_message(self.window, f"Auto-open skipped for {spec.title} (disabled).")
            return dock
        if is_auto and not is_panel_auto_open_enabled_for_trigger(
            self.window, panel_key, auto_trigger
        ):
            _show_status_message(
                self.window,
                f"Auto-open skipped for {spec.title} ({auto_trigger} disabled).")
            return dock
        _apply_panel_constraints(self.window, dock, spec)
        if spec.constraints.fixed_area:
            try:
                self.window.addDockWidget(_canonical_area_for_panel(self.window, spec), dock)
            except Exception:
                pass
        _tabify_group_for_panel(self.window, panel_id)
        dock.show()
        _select_system_tab_for_panel(self.window, panel_key)
        if not is_auto:
            dock.raise_()
            try:
                dock.activateWindow()
            except Exception:
                pass
        self._focus_panel_widget(dock)
        opened_by = "auto" if is_auto else "user"
        if not isinstance(getattr(self.window, "_panel_opened_by", None), dict):
            self.window._panel_opened_by = {}
        if not isinstance(getattr(self.window, "_panel_opened_reason", None), dict):
            self.window._panel_opened_reason = {}
        self.window._panel_opened_by[panel_key] = opened_by
        self.window._panel_opened_reason[panel_key] = reason_text
        if (not is_auto) and _is_user_intent_reason(reason_text):
            set_panel_pinned(self.window, panel_key, True)
        if is_auto:
            shown = getattr(self.window, "_panel_auto_notice_shown", set())
            if panel_key not in shown:
                _show_auto_open_toast(self.window, panel_key, str(spec.title))
                shown.add(panel_key)
                self.window._panel_auto_notice_shown = shown
        if str(reason) in {"user", "command_palette", "panel_switcher"}:
            _flash_dock(self.window, dock)
        return dock

    @staticmethod
    def _focus_panel_widget(dock: QtWidgets.QDockWidget) -> None:
        """Handle the focus panel widget helper flow."""
        try:
            root = dock.widget()
        except Exception:
            root = None
        if root is None:
            return
        try:
            if root.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus:
                root.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
                return
        except Exception:
            pass
        for child in root.findChildren(QtWidgets.QWidget):
            try:
                if not child.isVisible():
                    continue
                if child.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus:
                    continue
                child.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
                return
            except Exception:
                continue

def _panel_manager(self) -> PanelManager:
    """Handle the panel manager helper flow."""
    manager = getattr(self, "_panel_manager_obj", None)
    if not isinstance(manager, PanelManager):
        manager = PanelManager(self)
        self._panel_manager_obj = manager
    return manager

def open_panel(self, panel_id: str, *, reason: str = "user") -> Optional[QtWidgets.QDockWidget]:
    """Open panel by id with canonical placement, raise, and flash."""
    return _panel_manager(self).open_panel(panel_id, reason=reason)
