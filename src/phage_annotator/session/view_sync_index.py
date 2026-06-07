"""Extracted method group 2 for ViewSyncManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from PyQt5 import QtCore




class ViewSyncIndexMixin:
    """Method group 2 extracted from ViewSyncManager."""

    def set_view(self, modality_idx: int, zoom_level: float, pan_x: float, pan_y: float) -> None:
        """Set both zoom and pan for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        zoom_level : float
            Zoom level.
        pan_x : float
            Horizontal pan offset.
        pan_y : float
            Vertical pan offset.
        """
        if self._updating:
            return
        
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        zoom_level = max(0.1, min(20.0, zoom_level))
        state.zoom_level = zoom_level
        state.pan_x = pan_x
        state.pan_y = pan_y
        
        # Sync to others if enabled
        if self._zoom_sync_enabled:
            self._sync_zoom_to_all(zoom_level, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            self._sync_zoom_to_group(group_id, zoom_level, exclude=modality_idx)
        
        if self._pan_sync_enabled:
            self._sync_pan_to_all(pan_x, pan_y, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            self._sync_pan_to_group(group_id, pan_x, pan_y, exclude=modality_idx)
        
        self.view_changed.emit(modality_idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
    def enable_t_sync(self, enabled: bool) -> None:
        """Enable or disable T (time) slice synchronization.
        
        Parameters
        ----------
        enabled : bool
            Whether to enable T slice sync.
        """
        if self._t_sync_enabled == enabled:
            return
        
        self._t_sync_enabled = enabled
        self.t_sync_changed.emit(enabled)
        
        # Sync all modalities to first modality's T index if enabling
        if enabled and self._states:
            first_state = next(iter(self._states.values()))
            self._sync_t_to_all(first_state.t_index)
    def enable_z_sync(self, enabled: bool) -> None:
        """Enable or disable Z (depth) slice synchronization.
        
        Parameters
        ----------
        enabled : bool
            Whether to enable Z slice sync.
        """
        if self._z_sync_enabled == enabled:
            return
        
        self._z_sync_enabled = enabled
        self.z_sync_changed.emit(enabled)
        
        # Sync all modalities to first modality's Z index if enabling
        if enabled and self._states:
            first_state = next(iter(self._states.values()))
            self._sync_z_to_all(first_state.z_index)
    def set_t_index(self, modality_idx: int, t_index: int) -> None:
        """Set T (time) frame index for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        t_index : int
            T frame index (0-based).
        """
        if self._updating:
            return
        
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        t_index = max(0, t_index)  # Ensure non-negative
        state.t_index = t_index
        
        # Sync to others if enabled
        if self._t_sync_enabled:
            self._sync_t_to_all(t_index, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            self._sync_t_to_group(group_id, t_index, exclude=modality_idx)
        
        self.view_changed.emit(modality_idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
    def set_z_index(self, modality_idx: int, z_index: int) -> None:
        """Set Z (depth) layer index for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        z_index : int
            Z layer index (0-based).
        """
        if self._updating:
            return
        
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        z_index = max(0, z_index)  # Ensure non-negative
        state.z_index = z_index
        
        # Sync to others if enabled
        if self._z_sync_enabled:
            self._sync_z_to_all(z_index, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            self._sync_z_to_group(group_id, z_index, exclude=modality_idx)
        
        self.view_changed.emit(modality_idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
    def set_slice_indices(self, modality_idx: int, t_index: int, z_index: int) -> None:
        """Set both T and Z slice indices for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        t_index : int
            T frame index.
        z_index : int
            Z layer index.
        """
        if self._updating:
            return
        
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        t_index = max(0, t_index)
        z_index = max(0, z_index)
        state.t_index = t_index
        state.z_index = z_index
        
        # Sync to others if enabled
        if self._t_sync_enabled:
            self._sync_t_to_all(t_index, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            self._sync_t_to_group(group_id, t_index, exclude=modality_idx)
        
        if self._z_sync_enabled:
            self._sync_z_to_all(z_index, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            self._sync_z_to_group(group_id, z_index, exclude=modality_idx)
        
        self.view_changed.emit(modality_idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
