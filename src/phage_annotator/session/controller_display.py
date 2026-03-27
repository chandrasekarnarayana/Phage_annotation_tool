"""Display-oriented controller helpers."""

from __future__ import annotations

from phage_annotator.session.signal_hub import emit_display_changed


class SessionControllerDisplayMixin:
    """Controller helpers for display-related state."""

    def set_channel_display_settings_value(self, settings: dict) -> None:
        """Persist multi-channel display settings."""
        self.session_state.channel_display_settings = dict(settings or {})
        self.set_dirty(True)
        emit_display_changed(self)
