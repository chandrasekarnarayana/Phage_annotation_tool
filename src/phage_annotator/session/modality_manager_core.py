"""Extracted method group 1 for ModalityManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple





class ModalityManagerCoreMixin:
    """Method group 1 extracted from ModalityManager."""

    def __init__(self):
        """Initialize empty modality manager."""
        self.modalities: List[ModalitySpec] = []
        self.links = ModalityLinks()
        self._next_idx = 0
    def add_modality(
        self,
        image_id: int,
        custom_name: Optional[str] = None,
        projection_type: object | None = None) -> ModalitySpec:
        """Add a new modality.
        
        Parameters
        ----------
        image_id : int
            Index of image to associate with modality.
        custom_name : str, optional
            User-visible name (e.g., "TIRF", "Confocal").
            If None, auto-generates "Modality N".
        projection_type : ProjectionType
            Type of projection to apply.
        
        Returns
        -------
        ModalitySpec
            The newly created modality.
        
        Raises
        ------
        ValueError
            If image_id is invalid or custom_name is reserved.
        """
        if projection_type is None:
            projection_type = ProjectionType.RAW
        idx = self._next_idx
        self._next_idx += 1
        
        if custom_name is None:
            custom_name = f"Modality {idx + 1}"
        
        if not self._is_valid_name(custom_name):
            raise ValueError(f"Invalid or reserved modality name: {custom_name}")
        
        if self._name_exists(custom_name):
            raise ValueError(f"Modality name already exists: {custom_name}")
        
        modality = ModalitySpec(
            idx=idx,
            image_id=image_id,
            display_name=custom_name,
            projection_type=projection_type)
        
        self.modalities.append(modality)
        self.modalities.sort(key=lambda m: m.idx)
        
        return modality
    def remove_modality(self, modality_idx: int) -> bool:
        """Remove a modality.
        
        Parameters
        ----------
        modality_idx : int
            Index of modality to remove.
        
        Returns
        -------
        bool
            True if removed, False if not found.
        """
        original_count = len(self.modalities)
        self.modalities = [m for m in self.modalities if m.idx != modality_idx]
        
        # Clean up links involving this modality
        self.links.zoom_pan_linked = {
            pair for pair in self.links.zoom_pan_linked
            if modality_idx not in pair
        }
        self.links.playback_linked = {
            pair for pair in self.links.playback_linked
            if modality_idx not in pair
        }
        
        return len(self.modalities) < original_count
    def rename_modality(self, modality_idx: int, new_name: str) -> bool:
        """Rename a modality.
        
        Parameters
        ----------
        modality_idx : int
            Index of modality to rename.
        new_name : str
            New display name.
        
        Returns
        -------
        bool
            True if renamed, False if not found or invalid name.
        
        Raises
        ------
        ValueError
            If new_name is reserved or already exists.
        """
        if not self._is_valid_name(new_name):
            raise ValueError(f"Invalid or reserved modality name: {new_name}")
        
        # Check if name already exists (excluding current modality)
        for modality in self.modalities:
            if modality.idx != modality_idx and modality.display_name == new_name:
                raise ValueError(f"Modality name already exists: {new_name}")
        
        modality = self.get_modality(modality_idx)
        if modality is not None:
            modality.display_name = new_name
            return True
        
        return False
    def get_modality(self, modality_idx: int) -> Optional[ModalitySpec]:
        """Get modality by index.
        
        Parameters
        ----------
        modality_idx : int
            Modality index to retrieve.
        
        Returns
        -------
        ModalitySpec or None
            The modality, or None if not found.
        """
        for modality in self.modalities:
            if modality.idx == modality_idx:
                return modality
        return None
    def get_all_modalities(self) -> List[ModalitySpec]:
        """Get all modalities in index order.
        
        Returns
        -------
        List[ModalitySpec]
            Modalities sorted by idx.
        """
        return sorted(self.modalities, key=lambda m: m.idx)
    def modality_count(self) -> int:
        """Return number of modalities."""
        return len(self.modalities)
    def set_zoom_pan_link(self, modality_idx1: int, modality_idx2: int, link: bool) -> None:
        """Link or unlink zoom/pan between two modalities.
        
        Parameters
        ----------
        modality_idx1, modality_idx2 : int
            Indices of modalities to link.
        link : bool
            True to link, False to unlink.
        """
        pair = tuple(sorted([modality_idx1, modality_idx2]))
        
        if link:
            self.links.zoom_pan_linked.add(pair)
        else:
            self.links.zoom_pan_linked.discard(pair)
    def are_zoom_pan_linked(self, modality_idx1: int, modality_idx2: int) -> bool:
        """Check if two modalities are zoom/pan linked."""
        pair = tuple(sorted([modality_idx1, modality_idx2]))
        return pair in self.links.zoom_pan_linked

    def set_playback_link(self, modality_idx1: int, modality_idx2: int, link: bool) -> None:
        """Link or unlink playback between two modalities."""
        pair = tuple(sorted([modality_idx1, modality_idx2]))
        if link:
            self.links.playback_linked.add(pair)
        else:
            self.links.playback_linked.discard(pair)

    def are_playback_linked(self, modality_idx1: int, modality_idx2: int) -> bool:
        """Return whether two modalities share playback state."""
        pair = tuple(sorted([modality_idx1, modality_idx2]))
        return pair in self.links.playback_linked

    def set_contrast_sync_option(self, option: str, enabled: bool) -> None:
        """Set a named contrast synchronization option."""
        self.links.contrast_sync_options[str(option)] = bool(enabled)

    def get_contrast_sync_option(self, option: str) -> bool:
        """Return a named contrast synchronization option."""
        return bool(self.links.contrast_sync_options.get(str(option), False))

    def to_dict(self) -> dict:
        """Serialize modalities and synchronization links."""
        return {
            "modalities": [modality.to_dict() for modality in self.get_all_modalities()],
            "links": {
                "zoom_pan_linked": [list(pair) for pair in sorted(self.links.zoom_pan_linked)],
                "playback_linked": [list(pair) for pair in sorted(self.links.playback_linked)],
                "contrast_sync_options": dict(self.links.contrast_sync_options),
                "playback_mode": self.links.playback_mode,
            },
            "next_idx": self._next_idx,
            "_next_idx": self._next_idx,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a modality manager from project data."""
        manager = cls()
        manager.modalities = [
            ModalitySpec.from_dict(item) for item in data.get("modalities", [])
        ]
        manager._next_idx = int(data.get("next_idx", data.get("_next_idx", 0)))
        if manager.modalities:
            manager._next_idx = max(manager._next_idx, max(m.idx for m in manager.modalities) + 1)
        links = data.get("links", {})
        manager.links.zoom_pan_linked = {
            tuple(sorted(pair)) for pair in links.get("zoom_pan_linked", [])
        }
        manager.links.playback_linked = {
            tuple(sorted(pair)) for pair in links.get("playback_linked", [])
        }
        manager.links.contrast_sync_options.update(links.get("contrast_sync_options", {}))
        manager.links.playback_mode = str(links.get("playback_mode", manager.links.playback_mode))
        return manager

    @classmethod
    def create_from_primary_support(cls, primary_image_id: int, support_image_id: int | None = None):
        """Create modalities from legacy primary/support image ids."""
        manager = cls()
        manager.add_modality(primary_image_id)
        if support_image_id is not None:
            manager.add_modality(support_image_id)
        return manager

    def _is_valid_name(self, name: str) -> bool:
        """Validate user-visible modality names."""
        text = str(name or "").strip()
        return bool(text) and text not in self.RESERVED_NAMES

    def _name_exists(self, name: str) -> bool:
        """Return whether a display name is already assigned."""
        return any(modality.display_name == name for modality in self.modalities)
