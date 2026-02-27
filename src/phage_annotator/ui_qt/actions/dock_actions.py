"""Dock and panel visibility actions."""

from __future__ import annotations

from typing import Optional


class DockActionsMixin:
    """Panel visibility actions with synchronized dock/menu/button state."""

    def _toggle_profile_panel(self) -> None:
        self._set_panel_visibility("profile")

    def _toggle_hist_panel(self) -> None:
        self._set_panel_visibility("hist")

    def _set_panel_visibility(self, panel: str, visible: Optional[bool] = None) -> None:
        """Single source of truth for panel visibility (dock/menu/checkbox/buttons)."""
        key = str(panel).strip().lower()
        dock = None
        panel_docks = getattr(self, "panel_docks", {})
        if isinstance(panel_docks, dict):
            dock = panel_docks.get(key)
        if dock is None:
            dock = getattr(self, f"dock_{key}", None)
        if dock is None:
            return
        target = (not dock.isVisible()) if visible is None else bool(visible)
        if dock.isVisible() != target:
            dock.setVisible(target)
        self._sync_panel_visibility_state()

    def _sync_panel_visibility_state(self) -> None:
        """Sync visibility state across dock, menu toggles, and panel checkboxes."""
        panel_keys = ("hist", "profile", "qc_issues", "density", "logs", "metadata", "results")
        for key in panel_keys:
            dock = None
            panel_docks = getattr(self, "panel_docks", {})
            if isinstance(panel_docks, dict):
                dock = panel_docks.get(key)
            if dock is None:
                dock = getattr(self, f"dock_{key}", None)
            if dock is None:
                continue
            visible = bool(dock.isVisible())
            chk = getattr(self, f"{key}_chk", None)
            if chk is not None and chk.isChecked() != visible:
                chk.blockSignals(True)
                chk.setChecked(visible)
                chk.blockSignals(False)
            toggle = getattr(self, f"toggle_{key}_act", None)
            if toggle is not None and toggle.isChecked() != visible:
                toggle.blockSignals(True)
                toggle.setChecked(visible)
                toggle.blockSignals(False)
            dock_actions = getattr(self, "dock_actions", {})
            if isinstance(dock_actions, dict):
                act = dock_actions.get(key)
                if act is not None and act.isChecked() != visible:
                    act.blockSignals(True)
                    act.setChecked(visible)
                    act.blockSignals(False)
        if getattr(self, "quick_hist_btn", None) is not None and getattr(self, "dock_hist", None) is not None:
            self.quick_hist_btn.setText(
                "Histogram (On)" if bool(self.dock_hist.isVisible()) else "Histogram (Off)"
            )
        if getattr(self, "quick_profile_btn", None) is not None and getattr(self, "dock_profile", None) is not None:
            self.quick_profile_btn.setText(
                "Profile (On)" if bool(self.dock_profile.isVisible()) else "Profile (Off)"
            )

    def _update_qc_button_highlight(self, issue_count: int) -> None:
        """Highlight QC quick button when active issues exist."""
        btn = getattr(self, "quick_qc_btn", None)
        if btn is None:
            return
        count = int(max(0, issue_count))
        btn.setText(f"QC Issues ({count})" if count > 0 else "QC Issues")
        if count > 0:
            btn.setStyleSheet(
                "QPushButton { background-color: #f4c542; color: #1f1f1f; font-weight: 600; }"
            )
        else:
            btn.setStyleSheet("")

