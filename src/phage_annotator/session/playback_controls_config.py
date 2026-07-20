"""Extracted method group 3 for ModalityPlaybackManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable, TYPE_CHECKING

from PyQt5 import QtCore

if TYPE_CHECKING:
    # Runtime bindings for PlaybackMode/ModalityPlaybackState are injected by
    # phage_annotator.session.multi_playback (which imports this module) to
    # avoid a circular import; this import is for static analysis only.
    from phage_annotator.session.multi_playback import (
        ModalityPlaybackState,
        PlaybackMode,
    )


class PlaybackControlsConfigMixin:
    """Method group 3 extracted from ModalityPlaybackManager."""

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
