"""Playback state handlers for the session controller."""

from __future__ import annotations

class SessionPlaybackMixin:
    """Mixin for playback state handlers."""
    def start_playback(self, axis: str) -> None:
        """Set playback mode to start running."""
        if axis not in ("t", "z"):
            return
        if self.view_state.play_mode == axis:
            return
        self.view_state.play_mode = axis
        self.playback_changed.emit()

    def stop_playback(self) -> None:
        """Stop playback mode."""
        if self.view_state.play_mode is None:
            return
        self.view_state.play_mode = None
        self.playback_changed.emit()

    def set_loop(self, loop: bool) -> None:
        """Enable/disable playback loop."""
        if self.view_state.loop_playback == loop:
            return
        self.view_state.loop_playback = loop
        self.playback_changed.emit()

    def set_fps(self, fps: int) -> None:
        """Set playback FPS."""
        if self.session_state.fps == fps:
            return
        self.session_state.fps = int(fps)
        self.state_changed.emit()
