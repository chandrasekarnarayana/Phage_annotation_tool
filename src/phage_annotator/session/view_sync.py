"""Extracted method group 1 for ViewSyncManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from PyQt5 import QtCore
import phage_annotator.session.view_sync_crop as _view_sync_crop
import phage_annotator.session.view_sync_index as _view_sync_index
import phage_annotator.session.view_sync_state as _view_sync_state
import phage_annotator.session.view_sync_zoom_pan as _view_sync_zoom_pan
from phage_annotator.session.view_sync_crop import ViewSyncCropMixin
from phage_annotator.session.view_sync_index import ViewSyncIndexMixin
from phage_annotator.session.view_sync_state import ViewSyncStateMixin
from phage_annotator.session.view_sync_zoom_pan import ViewSyncZoomPanMixin


@dataclass
class ViewState:
    """View state for a single modality canvas."""

    modality_idx: int
    zoom_level: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    t_index: int = 0
    z_index: int = 0
    crop_rect: Optional[Tuple[float, float, float, float]] = None

    def clone(self) -> "ViewState":
        """Create a deep copy of this view state."""
        return ViewState(
            modality_idx=self.modality_idx,
            zoom_level=self.zoom_level,
            pan_x=self.pan_x,
            pan_y=self.pan_y,
            t_index=self.t_index,
            z_index=self.z_index,
            crop_rect=self.crop_rect,
        )


_view_sync_crop.ViewState = ViewState
_view_sync_index.ViewState = ViewState
_view_sync_state.ViewState = ViewState
_view_sync_zoom_pan.ViewState = ViewState




class ViewSyncMixin:
    """Method group 1 extracted from ViewSyncManager."""

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


class ViewSyncManager(
    ViewSyncMixin,
    ViewSyncIndexMixin,
    ViewSyncZoomPanMixin,
    ViewSyncCropMixin,
    ViewSyncStateMixin,
    QtCore.QObject,
):
    """Manage synchronized view state across multiple modalities."""

    view_changed = QtCore.pyqtSignal(int, float, float, float, int, int)
    zoom_sync_changed = QtCore.pyqtSignal(bool)
    pan_sync_changed = QtCore.pyqtSignal(bool)
    t_sync_changed = QtCore.pyqtSignal(bool)
    z_sync_changed = QtCore.pyqtSignal(bool)
    crop_sync_changed = QtCore.pyqtSignal(bool)
    crop_changed = QtCore.pyqtSignal(int, object)
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
