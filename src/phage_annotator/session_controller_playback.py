"""Playback state handlers for the session controller.

This mixin provides simple controls for starting/stopping playback, toggling
loop mode, and adjusting frames-per-second. All methods emit appropriate
signals when state changes.
"""

from __future__ import annotations


class SessionPlaybackMixin:
    """Mixin for playback state handlers."""

    def start_playback(self, axis: str) -> None:
        """Start playback along a given axis.

        Parameters
        ----------
        axis : str
            Either "t" (time) or "z" (depth).
        """
        if axis not in ("t", "z"):
            return
        if self.view_state.play_mode == axis:
            return
        self.view_state.play_mode = axis
        self.playback_changed.emit()

    def stop_playback(self) -> None:
        """Stop playback mode if active."""
        if self.view_state.play_mode is None:
            return
        self.view_state.play_mode = None
        self.playback_changed.emit()

    def set_loop(self, loop: bool) -> None:
        """Enable or disable playback loop.

        Parameters
        ----------
        loop : bool
            Whether playback should loop.
        """
        if self.view_state.loop_playback == loop:
            return
        self.view_state.loop_playback = loop
        self.playback_changed.emit()

    def set_fps(self, fps: int) -> None:
        """Set playback frames-per-second.

        Parameters
        ----------
        fps : int
            Target FPS value.
        """
        if self.session_state.fps == fps:
            return
        self.session_state.fps = int(fps)
        self.state_changed.emit()
