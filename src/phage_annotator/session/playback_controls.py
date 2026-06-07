"""Extracted method group 1 for ModalityPlaybackManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable

from PyQt5 import QtCore




class PlaybackControlsMixin:
    """Method group 1 extracted from ModalityPlaybackManager."""

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """Initialize playback manager.
        
        Parameters
        ----------
        parent : QtCore.QObject, optional
            Parent QObject.
        """
        super().__init__(parent)
        self._mode = PlaybackMode.INDEPENDENT
        self._states: Dict[int, ModalityPlaybackState] = {}
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.setInterval(100)  # 10 FPS default
        self._sequential_queue: List[int] = []
        self._sequential_index = 0
        self._sync_group: Optional[set[int]] = None
    def set_sync_group(self, modality_indices: Optional[set[int]]) -> None:
        """Set the synchronized playback group.

        Parameters
        ----------
        modality_indices : set[int] or None
            Modalities to include in synchronized playback.
            `None` means all registered modalities. An empty set means no
            synchronized playback targets are currently eligible.
        """
        self._sync_group = None if modality_indices is None else set(modality_indices)
        if self._mode == PlaybackMode.SEQUENTIAL:
            self._sequential_queue = sorted(
                self._sync_group if self._sync_group is not None else self._states.keys()
            )
            self._sequential_index = 0
        if self._mode == PlaybackMode.SYNCHRONIZED and self._timer.isActive():
            self._stop_all()
    def register_modality(
        self,
        modality_idx: int,
        modality_name: str,
        frame_count: int,
        fps: float = 10.0
    ) -> None:
        """Register a modality for playback management.
        
        Parameters
        ----------
        modality_idx : int
            Unique modality index.
        modality_name : str
            Display name (for logging/debugging).
        frame_count : int
            Total number of frames.
        fps : float, optional
            Playback frames per second (default: 10.0).
        """
        self._states[modality_idx] = ModalityPlaybackState(
            modality_idx=modality_idx,
            current_frame=0,
            is_playing=False,
            frame_count=frame_count,
            fps=fps,
            loop=True
        )
    def unregister_modality(self, modality_idx: int) -> None:
        """Remove a modality from playback management.
        
        Parameters
        ----------
        modality_idx : int
            Modality index to remove.
        """
        if modality_idx in self._states:
            # Stop playback if active
            if self._states[modality_idx].is_playing:
                self.stop_playback(modality_idx)
            del self._states[modality_idx]
    def set_mode(self, mode: PlaybackMode) -> None:
        """Set the playback synchronization mode.
        
        Parameters
        ----------
        mode : PlaybackMode
            New playback mode.
        """
        if mode == self._mode:
            return
        
        # Stop all playback when changing modes
        self._stop_all()
        
        self._mode = mode
        
        # Setup sequential queue if needed
        if mode == PlaybackMode.SEQUENTIAL:
            self._sequential_queue = sorted(
                self._sync_group if self._sync_group is not None else self._states.keys()
            )
            self._sequential_index = 0
        
        self.mode_changed.emit(mode.value)
    def start_playback(self, modality_idx: Optional[int] = None) -> None:
        """Start playback for one or all modalities.
        
        Parameters
        ----------
        modality_idx : int, optional
            Modality to start. If None with SYNCHRONIZED mode, starts all.
        """
        if self._mode == PlaybackMode.SYNCHRONIZED:
            # Start all modalities together
            target_indices = (
                self._sync_group
                if self._sync_group is not None
                else set(self._states.keys())
            )
            if not target_indices:
                return
            for idx in sorted(target_indices):
                state = self._states.get(idx)
                if state is None:
                    continue
                state.is_playing = True
                self.playback_started.emit(state.modality_idx)
            
            # Use fastest FPS from all modalities
            max_fps = max(
                (self._states[idx].fps for idx in target_indices if idx in self._states),
                default=10.0,
            )
            self._timer.setInterval(int(1000 / max_fps))
            self._timer.start()
        
        elif self._mode == PlaybackMode.INDEPENDENT:
            if modality_idx is None:
                return  # Must specify modality in independent mode
            
            state = self._states.get(modality_idx)
            if state is None:
                return
            
            state.is_playing = True
            self.playback_started.emit(modality_idx)
            
            # Start timer if not already running
            if not self._timer.isActive():
                # Use this modality's FPS
                self._timer.setInterval(int(1000 / state.fps))
                self._timer.start()
        
        elif self._mode == PlaybackMode.SEQUENTIAL:
            # Start first modality in queue
            if not self._sequential_queue:
                return
            
            self._sequential_index = 0
            first_idx = self._sequential_queue[0]
            state = self._states.get(first_idx)
            if state is None:
                return
            
            state.is_playing = True
            self.playback_started.emit(first_idx)
            
            self._timer.setInterval(int(1000 / state.fps))
            self._timer.start()
