"""Dock and panel visibility actions."""

from __future__ import annotations

from typing import Optional


class DockActionsMixin:
    """Panel visibility actions with synchronized dock/menu/button state."""

    def _toggle_profile_panel(self) -> None:
        self._set_panel_visibility("profile")

    def _toggle_hist_panel(self) -> None:
        self._set_panel_visibility("hist")

    def _resolve_panel_dock(self, panel: str):
        """Return dock widget for a panel id, if present."""
        key = str(panel).strip().lower()
        dock = None
        panel_docks = getattr(self, "panel_docks", {})
        if isinstance(panel_docks, dict):
            dock = panel_docks.get(key)
        if dock is None:
            dock = getattr(self, f"dock_{key}", None)
        return key, dock

    def set_panel_visible(self, panel_id: str, visible: bool, *, source: str = "unknown") -> None:
        """Canonical panel-visibility writer used by menus/toolbars/presets."""
        _key, dock = self._resolve_panel_dock(panel_id)
        if dock is None:
            return
        target = bool(visible)
        if target:
            opener = getattr(self, "open_panel", None)
            if callable(opener):
                opener(_key, reason=str(source))
            elif dock.isVisible() != target:
                dock.setVisible(target)
        elif dock.isVisible() != target:
            dock.setVisible(target)
        self._sync_panel_visibility_state()

    def apply_panel_visibility_preset(self, preset: dict[str, bool], *, source: str = "preset") -> None:
        """Apply a visibility preset through the canonical visibility writer."""
        for panel_id, visible in dict(preset).items():
            self.set_panel_visible(str(panel_id), bool(visible), source=source)

    def _set_panel_visibility(self, panel: str, visible: Optional[bool] = None) -> None:
        """Backward-compatible wrapper for panel visibility updates."""
        key, dock = self._resolve_panel_dock(panel)
        if dock is None:
            return
        target = (not dock.isVisible()) if visible is None else bool(visible)
        self.set_panel_visible(key, target, source="legacy_wrapper")

    def _sync_panel_visibility_state(self) -> None:
        """Sync visibility state across dock, menu toggles, and panel checkboxes."""
        try:
            _ = self.objectName() if hasattr(self, "objectName") else None
        except RuntimeError:
            return
        panel_keys = (
            "sidebar",
            "hist",
            "profile",
            "qc_issues",
            "density",
            "logs",
            "metadata",
            "results",
            "annotations",
            "review_queue",
            "suggestion_explain",
            "advanced_analysis",
        )
        for key in panel_keys:
            try:
                dock = None
                panel_docks = getattr(self, "panel_docks", {})
            except RuntimeError:
                return
            if isinstance(panel_docks, dict):
                dock = panel_docks.get(key)
            if dock is None:
                try:
                    dock = getattr(self, f"dock_{key}", None)
                except RuntimeError:
                    return
            if dock is None:
                continue
            visible = bool(dock.isVisible())
            try:
                chk = getattr(self, f"{key}_chk", None)
            except RuntimeError:
                return
            if chk is not None and chk.isChecked() != visible:
                chk.blockSignals(True)
                chk.setChecked(visible)
                chk.blockSignals(False)
            try:
                toggle = getattr(self, f"toggle_{key}_act", None)
            except RuntimeError:
                return
            if toggle is not None and toggle.isChecked() != visible:
                toggle.blockSignals(True)
                toggle.setChecked(visible)
                toggle.blockSignals(False)
            try:
                dock_actions = getattr(self, "dock_actions", {})
            except RuntimeError:
                return
            if isinstance(dock_actions, dict):
                act = dock_actions.get(key)
                if act is not None and act.isChecked() != visible:
                    act.blockSignals(True)
                    act.setChecked(visible)
                    act.blockSignals(False)
        hist_act = getattr(self, "quick_hist_act", None)
        if hist_act is not None and getattr(self, "dock_hist", None) is not None:
            hist_act.blockSignals(True)
            hist_act.setChecked(bool(self.dock_hist.isVisible()))
            hist_act.setText("Histogram")
            hist_act.blockSignals(False)
        profile_act = getattr(self, "quick_profile_act", None)
        if profile_act is not None and getattr(self, "dock_profile", None) is not None:
            profile_act.blockSignals(True)
            profile_act.setChecked(bool(self.dock_profile.isVisible()))
            profile_act.setText("Profile")
            profile_act.blockSignals(False)
        qc_act = getattr(self, "quick_qc_act", None)
        if qc_act is not None and getattr(self, "dock_qc_issues", None) is not None:
            qc_act.blockSignals(True)
            qc_act.setChecked(bool(self.dock_qc_issues.isVisible()))
            qc_act.blockSignals(False)

    def _update_qc_button_highlight(self, issue_count: int) -> None:
        """Highlight QC quick button when active issues exist."""
        btn = getattr(self, "quick_panels_btn", None)
        act = getattr(self, "quick_qc_act", None)
        if btn is None and act is None:
            return
        count = int(max(0, issue_count))
        if act is not None:
            act.setText(f"QC Issues ({count})" if count > 0 else "QC Issues")
        if count > 0:
            if btn is not None:
                btn.setStyleSheet(
                    "QToolButton { background-color: #f4c542; color: #1f1f1f; font-weight: 600; }"
                )
        else:
            if btn is not None:
                btn.setStyleSheet("")
