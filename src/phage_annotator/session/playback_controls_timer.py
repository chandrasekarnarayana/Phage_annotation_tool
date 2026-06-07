"""Extracted method group 2 for ModalityPlaybackManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable

from PyQt5 import QtCore




class PlaybackControlsTimerMixin:
    """Method group 2 extracted from ModalityPlaybackManager."""

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
