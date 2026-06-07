"""Extracted method group 4 for ViewSyncManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from PyQt5 import QtCore




class ViewSyncCropMixin:
    """Method group 4 extracted from ViewSyncManager."""

    def _sync_z_to_group(self, group_id: int, z_index: int, exclude: Optional[int] = None) -> None:
        """Sync Z index within a link group.
        
        Parameters
        ----------
        group_id : int
            Group ID.
        z_index : int
            Z layer index to apply.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating or group_id not in self._link_groups:
            return
        
        self._updating = True
        try:
            for idx in self._link_groups[group_id]:
                if idx != exclude and idx in self._states:
                    state = self._states[idx]
                    state.z_index = z_index
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    def enable_crop_sync(self, enabled: bool) -> None:
        """Enable or disable crop rectangle synchronization.
        
        When enabled, setting the crop rectangle on one modality will
        propagate to all others (or within link groups if linking enabled).
        When disabled, each modality maintains independent crop rectangles.
        
        Parameters
        ----------
        enabled : bool
            True to enable crop sync, False to disable.
        """
        if self._crop_sync_enabled == enabled:
            return
        
        self._crop_sync_enabled = enabled
        self.crop_sync_changed.emit(enabled)
        
        # If enabling and at least one modality has a crop rect, sync it
        if enabled:
            for idx in self._states:
                if self._states[idx].crop_rect is not None:
                    crop_rect = self._states[idx].crop_rect
                    self._sync_crop_to_all(crop_rect, exclude=idx)
                    break
    def set_crop_rect(self, modality_idx: int, crop_rect: Optional[Tuple[float, float, float, float]]) -> None:
        """Set crop rectangle for a modality.
        
        If crop sync is enabled, propagates to all modalities or link group.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        crop_rect : tuple[float, float, float, float] or None
            Crop rectangle as (x, y, width, height) or None to clear.
        """
        if modality_idx not in self._states:
            return
        
        state = self._states[modality_idx]
        state.crop_rect = crop_rect
        
        self.crop_changed.emit(modality_idx, crop_rect)
        
        if self._crop_sync_enabled and not self._updating:
            # Check if modality is in a link group
            if modality_idx in self._modality_to_group:
                group_id = self._modality_to_group[modality_idx]
                self._sync_crop_to_group(group_id, crop_rect, exclude=modality_idx)
            else:
                # Sync to all modalities not in groups
                self._sync_crop_to_all(crop_rect, exclude=modality_idx)
    def _sync_crop_to_all(self, crop_rect: Optional[Tuple[float, float, float, float]], exclude: Optional[int] = None) -> None:
        """Sync crop rectangle to all modalities.
        
        Parameters
        ----------
        crop_rect : tuple[float, float, float, float] or None
            Crop rectangle to apply.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating:
            return
        
        self._updating = True
        try:
            for idx in self._states:
                if idx != exclude:
                    state = self._states[idx]
                    state.crop_rect = crop_rect
                    self.crop_changed.emit(idx, crop_rect)
        finally:
            self._updating = False
    def _sync_crop_to_group(self, group_id: int, crop_rect: Optional[Tuple[float, float, float, float]], exclude: Optional[int] = None) -> None:
        """Sync crop rectangle within a link group.
        
        Parameters
        ----------
        group_id : int
            Group ID.
        crop_rect : tuple[float, float, float, float] or None
            Crop rectangle to apply.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating or group_id not in self._link_groups:
            return
        
        self._updating = True
        try:
            for idx in self._link_groups[group_id]:
                if idx != exclude and idx in self._states:
                    state = self._states[idx]
                    state.crop_rect = crop_rect
                    self.crop_changed.emit(idx, crop_rect)
        finally:
            self._updating = False
    def create_link_group(self, modality_indices: Set[int]) -> int:
        """Create a link group for modalities.
        
        Parameters
        ----------
        modality_indices : Set[int]
            Set of modality indices to link.
        
        Returns
        -------
        int
            Group ID.
        """
        group_id = self._next_group_id
        self._next_group_id += 1
        
        self._link_groups[group_id] = modality_indices.copy()
        for idx in modality_indices:
            self._modality_to_group[idx] = group_id
        
        return group_id
    def remove_link_group(self, group_id: int) -> None:
        """Remove a link group.
        
        Parameters
        ----------
        group_id : int
            Group ID to remove.
        """
        if group_id not in self._link_groups:
            return
        
        # Remove modality mappings
        for idx in self._link_groups[group_id]:
            if idx in self._modality_to_group:
                del self._modality_to_group[idx]
        
        del self._link_groups[group_id]
    def get_view_state(self, modality_idx: int) -> Optional[ViewState]:
        """Get the current view state for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        
        Returns
        -------
        ViewState or None
            View state if found, else None.
        """
        state = self._states.get(modality_idx)
        return state.clone() if state else None
