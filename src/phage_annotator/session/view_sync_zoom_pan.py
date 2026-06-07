"""Extracted method group 3 for ViewSyncManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from PyQt5 import QtCore




class ViewSyncZoomPanMixin:
    """Method group 3 extracted from ViewSyncManager."""

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
