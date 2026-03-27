"""Playback state handlers for the session controller."""

from __future__ import annotations

from phage_annotator.session.signal_hub import emit_playback_changed, emit_state_changed

class SessionPlaybackMixin:
    """Mixin for playback state handlers."""
    def start_playback(self, axis: str) -> None:
        """Set playback mode to start running."""
        if axis not in ("t", "z"):
            return
        if self.view_state.play_mode == axis:
            return
        self.view_state.play_mode = axis
        emit_playback_changed(self)

    def stop_playback(self) -> None:
        """Stop playback mode."""
        if self.view_state.play_mode is None:
            return
        self.view_state.play_mode = None
        emit_playback_changed(self)

    def set_loop(self, loop: bool) -> None:
        """Enable/disable playback loop."""
        if self.view_state.loop_playback == loop:
            return
        self.view_state.loop_playback = loop
        emit_playback_changed(self)

    def set_fps(self, fps: int) -> None:
        """Set playback FPS."""
        if self.session_state.fps == fps:
            return
        self.session_state.fps = int(fps)
        emit_state_changed(self)
