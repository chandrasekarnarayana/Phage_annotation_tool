"""Controller helpers for lazy sync-group and ROI-sharing state.

This keeps sync grouping in session state instead of window-local attributes so
contrast/view/playback/ROI behavior can share one source of truth.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from phage_annotator.session.signal_hub import emit_view_changed


class SessionControllerSyncMixin:
    """Controller APIs for lazy sync-group and sync-mode ownership."""

    def get_lazy_sync_groups(self) -> Dict[Any, str]:
        """Return a copy of the current lazy sync-group mapping."""
        return dict(getattr(self.session_state, "lazy_sync_groups", {}) or {})

    def set_lazy_sync_group(self, role_key: Any, group_key: object) -> str:
        """Persist one role's numeric sync-group key."""
        text = str(group_key or "").strip()
        if not text.isdigit():
            text = "1"
        groups = dict(getattr(self.session_state, "lazy_sync_groups", {}) or {})
        groups[role_key] = text
        self.session_state.lazy_sync_groups = groups
        emit_view_changed(self, change_type="sync_group")
        return text

    def get_lazy_sync_modes(self) -> Dict[Any, Dict[str, bool]]:
        """Return a deep-ish copy of per-role lazy sync mode flags."""
        modes = dict(getattr(self.session_state, "lazy_sync_modes", {}) or {})
        return {key: dict(value or {}) for key, value in modes.items()}

    def set_lazy_sync_mode(self, role_key: Any, mode_key: str, enabled: bool) -> Dict[str, bool]:
        """Persist one sync mode flag for one role."""
        key = str(mode_key or "").strip().lower()
        if key not in {"contrast", "zoom", "playback"}:
            key = "contrast"
        modes = self.get_lazy_sync_modes()
        current = dict(modes.get(role_key, {}) or {})
        current[key] = bool(enabled)
        modes[role_key] = {
            "contrast": bool(current.get("contrast", True)),
            "zoom": bool(current.get("zoom", True)),
            "playback": bool(current.get("playback", True)),
        }
        self.session_state.lazy_sync_modes = modes
        emit_view_changed(self, change_type="sync_mode")
        return dict(modes[role_key])

    def roi_state_for_sync_group(self, group_key: str) -> Optional[Dict[str, object]]:
        """Return stored ROI state for one sync group, if any."""
        key = str(group_key or "").strip()
        return dict(
            dict(getattr(self.session_state, "roi_by_sync_group", {}) or {}).get(key, {}) or {}
        ) or None

    def set_roi_state_for_sync_group(
        self,
        group_key: str,
        state: Optional[Dict[str, object]],
    ) -> None:
        """Persist ROI state keyed by sync group."""
        key = str(group_key or "").strip()
        if not key:
            return
        store = dict(getattr(self.session_state, "roi_by_sync_group", {}) or {})
        store[key] = None if state is None else dict(state)
        self.session_state.roi_by_sync_group = store
        emit_view_changed(self, change_type="roi_sync_group")
