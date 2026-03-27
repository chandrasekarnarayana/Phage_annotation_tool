"""Multi-modality playback synchronization system.

This module provides playback coordination across multiple modalities with
support for:
- SYNCHRONIZED: All modalities play at the same frame rate and time
- INDEPENDENT: Each modality has its own playback state
- SEQUENTIAL: Play one modality, then the next, etc.

Provides multi-modality playback and synchronization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable

from PyQt5 import QtCore


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


class ModalityPlaybackManager(QtCore.QObject):
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
    >>> manager.start_playback(0)  # Starts both if synchronized
    """
    
    frame_changed = QtCore.pyqtSignal(int, int)
    playback_started = QtCore.pyqtSignal(int)
    playback_stopped = QtCore.pyqtSignal(int)
    mode_changed = QtCore.pyqtSignal(str)
    
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
    
    def stop_playback(self, modality_idx: Optional[int] = None) -> None:
        """Stop playback for one or all modalities.
        
        Parameters
        ----------
        modality_idx : int, optional
            Modality to stop. If None, stops all.
        """
        if modality_idx is None:
            self._stop_all()
        else:
            state = self._states.get(modality_idx)
            if state is None:
                return
            
            state.is_playing = False
            self.playback_stopped.emit(modality_idx)
            
            # Stop timer if no modalities are playing
            if not any(s.is_playing for s in self._states.values()):
                self._timer.stop()
    
    def _stop_all(self) -> None:
        """Stop playback for all modalities."""
        for state in self._states.values():
            if state.is_playing:
                state.is_playing = False
                self.playback_stopped.emit(state.modality_idx)
        self._timer.stop()
    
    def toggle_playback(self, modality_idx: int) -> None:
        """Toggle playback on/off for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality to toggle.
        """
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        if state.is_playing:
            self.stop_playback(modality_idx)
        else:
            self.start_playback(modality_idx)
    
    def _on_timer_tick(self) -> None:
        """Handle timer tick to advance frames."""
        if self._mode == PlaybackMode.SYNCHRONIZED:
            # Advance all playing modalities together
            target_indices = (
                self._sync_group
                if self._sync_group is not None
                else set(self._states.keys())
            )
            for idx in sorted(target_indices):
                state = self._states.get(idx)
                if state is None or not state.is_playing:
                    continue
                if state.advance_frame():
                    self.frame_changed.emit(state.modality_idx, state.current_frame)
                else:
                    # Reached end without loop, stop all
                    self._stop_all()
                    break
        
        elif self._mode == PlaybackMode.INDEPENDENT:
            # Advance each playing modality independently
            any_playing = False
            for state in self._states.values():
                if state.is_playing:
                    any_playing = True
                    if state.advance_frame():
                        self.frame_changed.emit(state.modality_idx, state.current_frame)
                    else:
                        # This modality stopped
                        self.playback_stopped.emit(state.modality_idx)
            
            # Stop timer if nothing playing
            if not any_playing:
                self._timer.stop()
        
        elif self._mode == PlaybackMode.SEQUENTIAL:
            # Play current modality in sequence
            if not self._sequential_queue or self._sequential_index >= len(self._sequential_queue):
                self._timer.stop()
                return
            
            current_idx = self._sequential_queue[self._sequential_index]
            state = self._states.get(current_idx)
            
            if state is None or not state.is_playing:
                # Move to next in sequence
                self._advance_sequential_queue()
                return
            
            if state.advance_frame():
                self.frame_changed.emit(state.modality_idx, state.current_frame)
            else:
                # Finished this modality, move to next
                self.playback_stopped.emit(state.modality_idx)
                self._advance_sequential_queue()
    
    def _advance_sequential_queue(self) -> None:
        """Move to next modality in sequential playback."""
        self._sequential_index += 1
        
        if self._sequential_index < len(self._sequential_queue):
            # Start next modality
            next_idx = self._sequential_queue[self._sequential_index]
            state = self._states.get(next_idx)
            if state:
                state.is_playing = True
                state.reset()
                self.playback_started.emit(next_idx)
                self._timer.setInterval(int(1000 / state.fps))
        else:
            # Finished all modalities
            self._timer.stop()
            # Loop back to start if enabled
            if self._states:
                first_state = next(iter(self._states.values()))
                if first_state.loop:
                    self._sequential_index = 0
                    self.start_playback()
    
    def set_frame(self, modality_idx: int, frame: int) -> None:
        """Set the current frame for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        frame : int
            Frame index to set (0-indexed).
        """
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        frame = max(0, min(frame, state.frame_count - 1))
        state.current_frame = frame
        self.frame_changed.emit(modality_idx, frame)
    
    def get_frame(self, modality_idx: int) -> Optional[int]:
        """Get the current frame for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        
        Returns
        -------
        int or None
            Current frame index, or None if modality not found.
        """
        state = self._states.get(modality_idx)
        return state.current_frame if state else None
    
    def is_playing(self, modality_idx: int) -> bool:
        """Check if a modality is currently playing.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        
        Returns
        -------
        bool
            True if playing, False otherwise.
        """
        state = self._states.get(modality_idx)
        return state.is_playing if state else False
    
    def set_fps(self, modality_idx: int, fps: float) -> None:
        """Set playback FPS for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        fps : float
            Frames per second (must be > 0).
        """
        state = self._states.get(modality_idx)
        if state:
            state.fps = max(0.1, fps)  # Minimum 0.1 FPS
            
            # Update timer if this modality is currently playing alone
            if self._mode == PlaybackMode.INDEPENDENT and state.is_playing:
                self._timer.setInterval(int(1000 / state.fps))
    
    def set_loop(self, modality_idx: int, loop: bool) -> None:
        """Set loop mode for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        loop : bool
            Whether to loop playback.
        """
        state = self._states.get(modality_idx)
        if state:
            state.loop = loop
    
    def reset_all(self) -> None:
        """Reset all modalities to frame 0."""
        for state in self._states.values():
            state.reset()
            self.frame_changed.emit(state.modality_idx, 0)
    
    def get_state(self, modality_idx: int) -> Optional[ModalityPlaybackState]:
        """Get the playback state for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        
        Returns
        -------
        ModalityPlaybackState or None
            The playback state if found, else None.
        """
        return self._states.get(modality_idx)
    
    @property
    def mode(self) -> PlaybackMode:
        """Get the current playback mode.
        
        Returns
        -------
        PlaybackMode
            Current mode.
        """
        return self._mode
    
    def to_dict(self) -> Dict:
        """Serialize playback manager state to dictionary.
        
        Used for saving preferences to .pat/.json files.
        
        Returns
        -------
        dict
            Serializable dictionary containing:
            - mode: current playback mode
            - playback_states: per-modality FPS and loop settings
            - sync_group: set of indices in sync group
        """
        # Serialize playback mode
        result = {
            "mode": self._mode.value,
        }
        
        # Serialize per-modality states
        modality_states = {}
        for idx, state in self._states.items():
            modality_states[str(idx)] = {
                "fps": state.fps,
                "loop": state.loop,
                "frame_count": state.frame_count,
            }
        result["modality_states"] = modality_states
        
        # Serialize sync group
        if self._sync_group is not None:
            result["sync_group"] = sorted(list(self._sync_group))
        else:
            result["sync_group"] = None
        
        return result
    
    def from_dict(self, data: Dict) -> None:
        """Deserialize playback manager state from dictionary.
        
        Restores playback mode, FPS values, and sync settings.
        
        Parameters
        ----------
        data : dict
            Dictionary from to_dict() or saved file.
        """
        # Restore playback mode
        mode_str = data.get("mode", "independent")
        try:
            self._mode = PlaybackMode(mode_str)
        except ValueError:
            self._mode = PlaybackMode.INDEPENDENT
        
        # Restore per-modality states
        modality_states_data = data.get("modality_states", {})
        for idx_str, state_data in modality_states_data.items():
            try:
                idx = int(idx_str)
                if idx in self._states:
                    state = self._states[idx]
                    state.fps = max(0.1, state_data.get("fps", 10.0))
                    state.loop = state_data.get("loop", True)
                    # frame_count is not restored (read from image)
            except (ValueError, KeyError):
                continue
        
        # Restore sync group
        sync_group_data = data.get("sync_group")
        if sync_group_data is not None:
            self._sync_group = set(sync_group_data)
            # Rebuild sequential queue if in sequential mode
            if self._mode == PlaybackMode.SEQUENTIAL:
                self._sequential_queue = sorted(
                    self._sync_group if self._sync_group is not None else list(self._states.keys())
                )
        else:
            self._sync_group = None
