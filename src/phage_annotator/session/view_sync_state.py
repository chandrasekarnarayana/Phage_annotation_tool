"""Extracted method group 5 for ViewSyncManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from PyQt5 import QtCore




class ViewSyncStateMixin:
    """Method group 5 extracted from ViewSyncManager."""

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
