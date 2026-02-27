"""Zoom and pan synchronization for multi-modality views.

This module provides synchronized view state management across multiple
modalities, ensuring consistent zoom levels and pan positions when enabled.

Supports zoom/pan synchronization across modalities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from PyQt5 import QtCore


@dataclass
class ViewState:
    """View state for a single modality canvas.
    
    Attributes
    ----------
    modality_idx : int
        Index of the modality.
    zoom_level : float
        Current zoom level (1.0 = 100%, 2.0 = 200%, etc.).
    pan_x : float
        Horizontal pan offset in pixels.
    pan_y : float
        Vertical pan offset in pixels.
    t_index : int
        Current time (T) frame index.
    z_index : int
        Current depth (Z) layer index.
    crop_rect : Optional[tuple[float, float, float, float]]
        Current crop rectangle as (x, y, width, height) or None.
    """
    
    modality_idx: int
    zoom_level: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    t_index: int = 0
    z_index: int = 0
    crop_rect: Optional[Tuple[float, float, float, float]] = None
    
    def clone(self) -> ViewState:
        """Create a deep copy of this view state.
        
        Returns
        -------
        ViewState
            Copy of this state.
        """
        return ViewState(
            modality_idx=self.modality_idx,
            zoom_level=self.zoom_level,
            pan_x=self.pan_x,
            pan_y=self.pan_y,
            t_index=self.t_index,
            z_index=self.z_index,
            crop_rect=self.crop_rect
        )


class ViewSyncManager(QtCore.QObject):
    """Manages zoom, pan, slice, and crop synchronization across multiple modalities.
    
    Supports:
    - Synchronized zoom: All modalities maintain same zoom level
    - Synchronized pan: All modalities maintain same pan offset
    - Synchronized slices: All modalities maintain same T and/or Z indices
    - Synchronized crop: All modalities maintain same crop rectangle
    - Link groups: Create groups of modalities that sync together
    - Independent control: Modalities can be excluded from sync
    
    Signals
    -------
    view_changed : pyqtSignal(int, float, float, float, int, int)
        Emitted when view changes (modality_idx, zoom, pan_x, pan_y, t_idx, z_idx).
    zoom_sync_changed : pyqtSignal(bool)
        Emitted when zoom sync is enabled/disabled.
    pan_sync_changed : pyqtSignal(bool)
        Emitted when pan sync is enabled/disabled.
    t_sync_changed : pyqtSignal(bool)
        Emitted when T slice sync is enabled/disabled.
    z_sync_changed : pyqtSignal(bool)
        Emitted when Z slice sync is enabled/disabled.
    crop_sync_changed : pyqtSignal(bool)
        Emitted when crop rect sync is enabled/disabled.
    
    Example
    -------
    >>> manager = ViewSyncManager()
    >>> manager.register_modality(0)
    >>> manager.register_modality(1)
    >>> manager.enable_crop_sync(True)
    >>> manager.set_crop_rect(0, (10, 10, 100, 100))  # Both modalities crop to same rect
    """
    
    view_changed = QtCore.pyqtSignal(int, float, float, float, int, int)  # idx, zoom, pan_x, pan_y, t_idx, z_idx
    zoom_sync_changed = QtCore.pyqtSignal(bool)
    pan_sync_changed = QtCore.pyqtSignal(bool)
    t_sync_changed = QtCore.pyqtSignal(bool)
    z_sync_changed = QtCore.pyqtSignal(bool)
    crop_sync_changed = QtCore.pyqtSignal(bool)
    crop_changed = QtCore.pyqtSignal(int, object)  # idx, crop_rect
    
    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """Initialize view sync manager.
        
        Parameters
        ----------
        parent : QtCore.QObject, optional
            Parent QObject.
        """
        super().__init__(parent)
        self._states: Dict[int, ViewState] = {}
        self._zoom_sync_enabled = False
        self._pan_sync_enabled = False
        self._t_sync_enabled = False
        self._z_sync_enabled = False
        self._crop_sync_enabled = False
        self._link_groups: Dict[int, Set[int]] = {}  # group_id -> set of modality indices
        self._modality_to_group: Dict[int, int] = {}  # modality_idx -> group_id
        self._next_group_id = 0
        self._updating = False  # Prevent recursive updates
    
    def register_modality(self, modality_idx: int) -> None:
        """Register a modality for view sync management.
        
        Parameters
        ----------
        modality_idx : int
            Unique modality index.
        """
        if modality_idx not in self._states:
            self._states[modality_idx] = ViewState(modality_idx=modality_idx)
    
    def unregister_modality(self, modality_idx: int) -> None:
        """Remove a modality from view sync management.
        
        Parameters
        ----------
        modality_idx : int
            Modality index to remove.
        """
        if modality_idx in self._states:
            del self._states[modality_idx]
        
        # Remove from link groups
        if modality_idx in self._modality_to_group:
            group_id = self._modality_to_group[modality_idx]
            if group_id in self._link_groups:
                self._link_groups[group_id].discard(modality_idx)
                if not self._link_groups[group_id]:
                    del self._link_groups[group_id]
            del self._modality_to_group[modality_idx]

    def clear(self) -> None:
        """Clear all registered modalities and link groups."""
        self._states.clear()
        self._link_groups.clear()
        self._modality_to_group.clear()
        self._next_group_id = 0
    
    def enable_zoom_sync(self, enabled: bool) -> None:
        """Enable or disable zoom synchronization.
        
        Parameters
        ----------
        enabled : bool
            Whether to enable zoom sync.
        """
        if self._zoom_sync_enabled == enabled:
            return
        
        self._zoom_sync_enabled = enabled
        self.zoom_sync_changed.emit(enabled)
        
        # Sync all modalities to first modality's zoom if enabling
        if enabled and self._states:
            first_state = next(iter(self._states.values()))
            self._sync_zoom_to_all(first_state.zoom_level)
    
    def enable_pan_sync(self, enabled: bool) -> None:
        """Enable or disable pan synchronization.
        
        Parameters
        ----------
        enabled : bool
            Whether to enable pan sync.
        """
        if self._pan_sync_enabled == enabled:
            return
        
        self._pan_sync_enabled = enabled
        self.pan_sync_changed.emit(enabled)
        
        # Sync all modalities to first modality's pan if enabling
        if enabled and self._states:
            first_state = next(iter(self._states.values()))
            self._sync_pan_to_all(first_state.pan_x, first_state.pan_y)
    
    def set_zoom(self, modality_idx: int, zoom_level: float) -> None:
        """Set zoom level for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        zoom_level : float
            Zoom level (1.0 = 100%).
        """
        if self._updating:
            return  # Prevent recursive updates
        
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        zoom_level = max(0.1, min(20.0, zoom_level))  # Clamp to reasonable range
        state.zoom_level = zoom_level
        
        # Sync to others if enabled
        if self._zoom_sync_enabled:
            self._sync_zoom_to_all(zoom_level, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            # Sync within link group
            group_id = self._modality_to_group[modality_idx]
            self._sync_zoom_to_group(group_id, zoom_level, exclude=modality_idx)
        
        self.view_changed.emit(modality_idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
    
    def set_pan(self, modality_idx: int, pan_x: float, pan_y: float) -> None:
        """Set pan position for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        pan_x : float
            Horizontal pan offset.
        pan_y : float
            Vertical pan offset.
        """
        if self._updating:
            return  # Prevent recursive updates
        
        state = self._states.get(modality_idx)
        if state is None:
            return
        
        state.pan_x = pan_x
        state.pan_y = pan_y
        
        # Sync to others if enabled
        if self._pan_sync_enabled:
            self._sync_pan_to_all(pan_x, pan_y, exclude=modality_idx)
        elif modality_idx in self._modality_to_group:
            # Sync within link group
            group_id = self._modality_to_group[modality_idx]
            self._sync_pan_to_group(group_id, pan_x, pan_y, exclude=modality_idx)
        
        self.view_changed.emit(modality_idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
    
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
    
    def _sync_zoom_to_all(self, zoom_level: float, exclude: Optional[int] = None) -> None:
        """Sync zoom level to all modalities.
        
        Parameters
        ----------
        zoom_level : float
            Zoom level to apply.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating:
            return
        
        self._updating = True
        try:
            for idx, state in self._states.items():
                if idx != exclude:
                    state.zoom_level = zoom_level
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
    def _sync_pan_to_all(self, pan_x: float, pan_y: float, exclude: Optional[int] = None) -> None:
        """Sync pan position to all modalities.
        
        Parameters
        ----------
        pan_x : float
            Horizontal pan offset.
        pan_y : float
            Vertical pan offset.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating:
            return
        
        self._updating = True
        try:
            for idx, state in self._states.items():
                if idx != exclude:
                    state.pan_x = pan_x
                    state.pan_y = pan_y
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
    def _sync_zoom_to_group(self, group_id: int, zoom_level: float, exclude: Optional[int] = None) -> None:
        """Sync zoom level within a link group.
        
        Parameters
        ----------
        group_id : int
            Group ID.
        zoom_level : float
            Zoom level to apply.
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
                    state.zoom_level = zoom_level
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
    def _sync_pan_to_group(self, group_id: int, pan_x: float, pan_y: float, exclude: Optional[int] = None) -> None:
        """Sync pan position within a link group.
        
        Parameters
        ----------
        group_id : int
            Group ID.
        pan_x : float
            Horizontal pan offset.
        pan_y : float
            Vertical pan offset.
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
                    state.pan_x = pan_x
                    state.pan_y = pan_y
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
    def _sync_t_to_all(self, t_index: int, exclude: Optional[int] = None) -> None:
        """Sync T index to all modalities.
        
        Parameters
        ----------
        t_index : int
            T frame index to apply.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating:
            return
        
        self._updating = True
        try:
            for idx, state in self._states.items():
                if idx != exclude:
                    state.t_index = t_index
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
    def _sync_z_to_all(self, z_index: int, exclude: Optional[int] = None) -> None:
        """Sync Z index to all modalities.
        
        Parameters
        ----------
        z_index : int
            Z layer index to apply.
        exclude : int, optional
            Modality index to exclude from sync.
        """
        if self._updating:
            return
        
        self._updating = True
        try:
            for idx, state in self._states.items():
                if idx != exclude:
                    state.z_index = z_index
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
    def _sync_t_to_group(self, group_id: int, t_index: int, exclude: Optional[int] = None) -> None:
        """Sync T index within a link group.
        
        Parameters
        ----------
        group_id : int
            Group ID.
        t_index : int
            T frame index to apply.
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
                    state.t_index = t_index
                    self.view_changed.emit(idx, state.zoom_level, state.pan_x, state.pan_y, state.t_index, state.z_index)
        finally:
            self._updating = False
    
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
    
    def reset_view(self, modality_idx: int) -> None:
        """Reset view to defaults for a modality.
        
        Parameters
        ----------
        modality_idx : int
            Modality index.
        """
        state = self._states.get(modality_idx)
        if state:
            state.zoom_level = 1.0
            state.pan_x = 0.0
            state.pan_y = 0.0
            state.t_index = 0
            state.z_index = 0
            self.view_changed.emit(modality_idx, 1.0, 0.0, 0.0, 0, 0)
    
    def reset_all_views(self) -> None:
        """Reset all modalities to default view."""
        for idx in self._states:
            self.reset_view(idx)
    
    @property
    def zoom_sync_enabled(self) -> bool:
        """Check if zoom sync is enabled.
        
        Returns
        -------
        bool
            True if zoom sync enabled.
        """
        return self._zoom_sync_enabled
    
    @property
    def pan_sync_enabled(self) -> bool:
        """Check if pan sync is enabled.
        
        Returns
        -------
        bool
            True if pan sync enabled.
        """
        return self._pan_sync_enabled
    
    @property
    def t_sync_enabled(self) -> bool:
        """Check if T slice sync is enabled.
        
        Returns
        -------
        bool
            True if T slice sync enabled.
        """
        return self._t_sync_enabled
    
    @property
    def z_sync_enabled(self) -> bool:
        """Check if Z slice sync is enabled.
        
        Returns
        -------
        bool
            True if Z slice sync enabled.
        """
        return self._z_sync_enabled
    
    @property
    def crop_sync_enabled(self) -> bool:
        """Check if crop sync is enabled.
        
        Returns
        -------
        bool
            True if crop sync enabled.
        """
        return self._crop_sync_enabled
    
    def to_dict(self) -> Dict:
        """Serialize view sync state to dictionary.
        
        Used for saving preferences to .pat/.json files.
        
        Returns
        -------
        dict
            Serializable dictionary containing:
            - sync_flags: zoom/pan/t/z/crop sync states
            - view_states: per-modality view data
            - link_groups: group assignments
        """
        # Serialize sync enabled flags
        result = {
            "zoom_sync_enabled": self._zoom_sync_enabled,
            "pan_sync_enabled": self._pan_sync_enabled,
            "t_sync_enabled": self._t_sync_enabled,
            "z_sync_enabled": self._z_sync_enabled,
            "crop_sync_enabled": self._crop_sync_enabled,
        }
        
        # Serialize per-modality view states
        view_states = {}
        for idx, state in self._states.items():
            view_states[str(idx)] = {
                "zoom_level": state.zoom_level,
                "pan_x": state.pan_x,
                "pan_y": state.pan_y,
                "t_index": state.t_index,
                "z_index": state.z_index,
                "crop_rect": state.crop_rect,
            }
        result["view_states"] = view_states
        
        # Serialize link groups
        link_groups = {}
        for group_id, indices in self._link_groups.items():
            link_groups[str(group_id)] = sorted(list(indices))
        result["link_groups"] = link_groups
        
        # Save modality -> group mapping for reconstruction
        modality_to_group = {}
        for mod_idx, grp_id in self._modality_to_group.items():
            modality_to_group[str(mod_idx)] = grp_id
        result["modality_to_group"] = modality_to_group
        result["next_group_id"] = self._next_group_id
        
        return result
    
    def from_dict(self, data: Dict) -> None:
        """Deserialize view sync state from dictionary.
        
        Restores sync settings, view states, and link groups.
        
        Parameters
        ----------
        data : dict
            Dictionary from to_dict() or saved file.
        """
        # Restore sync flags
        self._zoom_sync_enabled = data.get("zoom_sync_enabled", False)
        self._pan_sync_enabled = data.get("pan_sync_enabled", False)
        self._t_sync_enabled = data.get("t_sync_enabled", False)
        self._z_sync_enabled = data.get("z_sync_enabled", False)
        self._crop_sync_enabled = data.get("crop_sync_enabled", False)
        
        # Restore per-modality view states
        view_states_data = data.get("view_states", {})
        for idx_str, state_data in view_states_data.items():
            try:
                idx = int(idx_str)
                if idx not in self._states:
                    self.register_modality(idx)
                
                state = self._states[idx]
                state.zoom_level = state_data.get("zoom_level", 1.0)
                state.pan_x = state_data.get("pan_x", 0.0)
                state.pan_y = state_data.get("pan_y", 0.0)
                state.t_index = state_data.get("t_index", 0)
                state.z_index = state_data.get("z_index", 0)
                
                crop_rect = state_data.get("crop_rect")
                if crop_rect is not None and isinstance(crop_rect, (list, tuple)):
                    state.crop_rect = tuple(crop_rect)
            except (ValueError, KeyError):
                continue
        
        # Restore link groups
        link_groups_data = data.get("link_groups", {})
        self._link_groups.clear()
        self._modality_to_group.clear()
        
        for group_id_str, indices_list in link_groups_data.items():
            try:
                group_id = int(group_id_str)
                indices_set = set(indices_list)
                self._link_groups[group_id] = indices_set
                for idx in indices_set:
                    self._modality_to_group[idx] = group_id
            except (ValueError, TypeError):
                continue
        
        # Restore next_group_id
        self._next_group_id = data.get("next_group_id", 0)
        if self._link_groups:
            self._next_group_id = max(int(k) for k in self._link_groups.keys()) + 1
