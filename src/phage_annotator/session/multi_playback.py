"""Multi-modality playback synchronization system.

This module provides playback coordination across multiple modalities with
support for:
- SYNCHRONIZED: All modalities play at the same frame rate and time
- INDEPENDENT: Each modality has its own playback state
- SEQUENTIAL: Play one modality, then the next, etc.

Provides multi-modality playback and synchronization.
"""

from __future__ import annotations

from PyQt5 import QtCore
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable
import phage_annotator.session.playback_controls as _playback_controls
import phage_annotator.session.playback_controls_config as _playback_config
import phage_annotator.session.playback_controls_timer as _playback_timer
from phage_annotator.session.playback_controls import PlaybackControlsMixin
from phage_annotator.session.playback_controls_config import PlaybackControlsConfigMixin
from phage_annotator.session.playback_controls_timer import PlaybackControlsTimerMixin


class PlaybackMode(Enum):
    """Playback synchronization strategies."""
    
    SYNCHRONIZED = "synchronized"  # All modalities play together (locked time)
    INDEPENDENT = "independent"    # Each modality has independent playback
    SEQUENTIAL = "sequential"       # Play modalities one after another

@dataclass
class ModalityPlaybackState:
    """Playback state for a single modality.
    
    Attributes
    ----------
    modality_idx : int
        Index of the modality.
    current_frame : int
        Current frame/time index (0-indexed).
    is_playing : bool
        Whether playback is active for this modality.
    frame_count : int
        Total number of frames in this modality.
    fps : float
        Frames per second for playback.
    loop : bool
        Whether to loop playback when reaching the end.
    """
    
    modality_idx: int
    current_frame: int = 0
    is_playing: bool = False
    frame_count: int = 1
    fps: float = 10.0
    loop: bool = True
    
    def advance_frame(self) -> bool:
        """Advance to next frame.
        
        Returns
        -------
        bool
            True if advanced, False if at end (and not looping).
        """
        if self.current_frame < self.frame_count - 1:
            self.current_frame += 1
            return True
        elif self.loop:
            self.current_frame = 0
            return True
        else:
            self.is_playing = False
            return False
    
    def reset(self) -> None:
        """Reset playback to frame 0."""
        self.current_frame = 0


_playback_controls.ModalityPlaybackState = ModalityPlaybackState
_playback_controls.PlaybackMode = PlaybackMode
_playback_config.ModalityPlaybackState = ModalityPlaybackState
_playback_config.PlaybackMode = PlaybackMode
_playback_timer.ModalityPlaybackState = ModalityPlaybackState
_playback_timer.PlaybackMode = PlaybackMode


class ModalityPlaybackManager(
    PlaybackControlsMixin,
    PlaybackControlsTimerMixin,
    PlaybackControlsConfigMixin,
    QtCore.QObject,
):
    """Manages playback synchronization across multiple modalities.

Signals
-------
frame_changed : pyqtSignal(int, int)
    Emitted when a modality advances to a new frame (modality_idx, frame_idx).
playback_started : pyqtSignal(int)
    Emitted when playback starts for a modality (modality_idx).
playback_stopped : pyqtSignal(int)
    Emitted when playback stops for a modality (modality_idx).
mode_changed : pyqtSignal(str)
    Emitted when playback mode changes (mode string).

Example
-------
>>> manager = ModalityPlaybackManager()
>>> manager.register_modality(0, "TIRF", frame_count=100)
>>> manager.register_modality(1, "Confocal", frame_count=100)
>>> manager.set_mode(PlaybackMode.SYNCHRONIZED)
>>> manager.start_playback(0)  # Starts both if synchronized"""

    frame_changed = QtCore.pyqtSignal(int, int)
    playback_started = QtCore.pyqtSignal(int)
    playback_stopped = QtCore.pyqtSignal(int)
    mode_changed = QtCore.pyqtSignal(str)
