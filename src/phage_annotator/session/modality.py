"""Multi-modality system: specification and management.

This module provides the core data structures and logic for managing multiple
image modalities (views) in a session, supporting arbitrary numbers of modalities
with independent display settings, projections, and synchronization options.

Phase α: Foundation for multi-modality support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class ProjectionType(Enum):
    """Types of projections that can be applied to image data."""
    RAW = "raw"           # Single frame from stack
    MEAN = "mean"         # Mean projection across axis
    STD = "std"           # Standard deviation projection
    MIN = "min"           # Minimum intensity projection
    MAX = "max"           # Maximum intensity projection


@dataclass
class ModalityDisplaySettings:
    """Display settings for a single modality.
    
    Parameters
    ----------
    vmin : float
        Minimum value for brightness mapping (black point).
    vmax : float
        Maximum value for brightness mapping (white point).
    lut : int
        Colormap/LUT index (0=grayscale, etc).
    projection_axis : str
        Which axis to project over: "t" (time) or "z" (depth).
    gamma : float
        Gamma correction factor (default 1.0 = linear).
    """
    vmin: float = 0.0
    vmax: float = 255.0
    lut: int = 0
    projection_axis: str = "t"
    gamma: float = 1.0


@dataclass
class ModalitySpec:
    """Specification for a single modality (image view).
    
    A modality represents one independent view of image data, with:
    - Reference to source image
    - Projection type (raw, mean, std, min, max)
    - Display settings (brightness, contrast, colormap)
    - Custom display name (editable by user)
    
    Parameters
    ----------
    idx : int
        Unique modality index (0, 1, 2, ...).
    image_id : int
        Index of source image in session.images list.
    display_name : str
        User-visible name ("Modality 1", "TIRF", etc).
    projection_type : ProjectionType
        Type of projection to apply.
    display_settings : ModalityDisplaySettings
        Brightness, contrast, colormap settings.
    """
    
    idx: int
    image_id: int
    display_name: str
    projection_type: ProjectionType = ProjectionType.RAW
    display_settings: ModalityDisplaySettings = field(default_factory=ModalityDisplaySettings)
    
    def clone(self) -> ModalitySpec:
        """Create a deep copy of this modality spec."""
        return ModalitySpec(
            idx=self.idx,
            image_id=self.image_id,
            display_name=self.display_name,
            projection_type=self.projection_type,
            display_settings=ModalityDisplaySettings(
                vmin=self.display_settings.vmin,
                vmax=self.display_settings.vmax,
                lut=self.display_settings.lut,
                projection_axis=self.display_settings.projection_axis,
                gamma=self.display_settings.gamma,
            ),
        )
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "idx": self.idx,
            "image_id": self.image_id,
            "display_name": self.display_name,
            "projection_type": self.projection_type.value,
            "display_settings": {
                "vmin": self.display_settings.vmin,
                "vmax": self.display_settings.vmax,
                "lut": self.display_settings.lut,
                "projection_axis": self.display_settings.projection_axis,
                "gamma": self.display_settings.gamma,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> ModalitySpec:
        """Deserialize from dictionary."""
        proj_type_str = data.get("projection_type", "raw")
        try:
            proj_type = ProjectionType(proj_type_str)
        except ValueError:
            proj_type = ProjectionType.RAW
        
        display_settings_data = data.get("display_settings", {})
        display_settings = ModalityDisplaySettings(
            vmin=display_settings_data.get("vmin", 0.0),
            vmax=display_settings_data.get("vmax", 255.0),
            lut=display_settings_data.get("lut", 0),
            projection_axis=display_settings_data.get("projection_axis", "t"),
            gamma=display_settings_data.get("gamma", 1.0),
        )
        
        return cls(
            idx=data["idx"],
            image_id=data["image_id"],
            display_name=data["display_name"],
            projection_type=proj_type,
            display_settings=display_settings,
        )


@dataclass
class ModalityLinks:
    """Synchronization links between modalities.
    
    Parameters
    ----------
    zoom_pan_linked : Set[Tuple[int, int]]
        Pairs of modality indices whose zoom/pan are linked.
    contrast_sync_options : Dict[str, bool]
        Global sync options: sync_vmin, sync_vmax, sync_contrast.
    playback_linked : Set[Tuple[int, int]]
        Pairs of modalities whose playback is linked (synchronized).
    """
    zoom_pan_linked: Set[Tuple[int, int]] = field(default_factory=set)
    contrast_sync_options: Dict[str, bool] = field(
        default_factory=lambda: {
            "sync_vmin": False,
            "sync_vmax": False,
            "sync_contrast": False,
        }
    )
    playback_linked: Set[Tuple[int, int]] = field(default_factory=set)
    playback_mode: str = "synchronized"  # synchronized, independent, sequential


class ModalityManager:
    """Manager for multi-modality operations.
    
    Handles:
    - Adding/removing modalities
    - Renaming modalities (with validation)
    - Querying modality properties
    - Managing synchronization links
    - Serialization/deserialization
    
    Public API
    ----------
    add_modality(image_id, custom_name) -> ModalitySpec
    remove_modality(modality_idx) -> bool
    rename_modality(modality_idx, new_name) -> bool
    get_modality(modality_idx) -> Optional[ModalitySpec]
    get_all_modalities() -> List[ModalitySpec]
    modality_count() -> int
    """
    
    RESERVED_NAMES = {"Primary", "Support", "Frame", "Stack"}
    
    def __init__(self):
        """Initialize empty modality manager."""
        self.modalities: List[ModalitySpec] = []
        self.links = ModalityLinks()
        self._next_idx = 0
    
    def add_modality(
        self,
        image_id: int,
        custom_name: Optional[str] = None,
        projection_type: ProjectionType = ProjectionType.RAW,
    ) -> ModalitySpec:
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
            projection_type=projection_type,
        )
        
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
        """Link or unlink playback between two modalities.
        
        Parameters
        ----------
        modality_idx1, modality_idx2 : int
            Indices of modalities to link.
        link : bool
            True to link, False to unlink.
        """
        pair = tuple(sorted([modality_idx1, modality_idx2]))
        
        if link:
            self.links.playback_linked.add(pair)
        else:
            self.links.playback_linked.discard(pair)
    
    def are_playback_linked(self, modality_idx1: int, modality_idx2: int) -> bool:
        """Check if two modalities are playback linked."""
        pair = tuple(sorted([modality_idx1, modality_idx2]))
        return pair in self.links.playback_linked
    
    def set_contrast_sync_option(self, option: str, enabled: bool) -> None:
        """Set global contrast synchronization option.
        
        Parameters
        ----------
        option : str
            One of: "sync_vmin", "sync_vmax", "sync_contrast".
        enabled : bool
            Enable or disable the option.
        """
        if option in self.links.contrast_sync_options:
            self.links.contrast_sync_options[option] = enabled
    
    def get_contrast_sync_option(self, option: str) -> bool:
        """Get global contrast synchronization option."""
        return self.links.contrast_sync_options.get(option, False)
    
    def _is_valid_name(self, name: str) -> bool:
        """Check if name is valid (non-empty, not reserved)."""
        if name is None or not isinstance(name, str):
            return False
        if not name.strip():  # Empty or whitespace-only
            return False
        if name.strip() in self.RESERVED_NAMES:
            return False
        # Allow alphanumeric, spaces, hyphens, underscores
        return all(c.isalnum() or c in (' ', '-', '_') for c in name)
    
    def _name_exists(self, name: str) -> bool:
        """Check if name is already used."""
        return any(m.display_name == name for m in self.modalities)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "modalities": [m.to_dict() for m in self.modalities],
            "links": {
                "zoom_pan_linked": list(self.links.zoom_pan_linked),
                "playback_linked": list(self.links.playback_linked),
                "contrast_sync_options": self.links.contrast_sync_options,
                "playback_mode": self.links.playback_mode,
            },
            "_next_idx": self._next_idx,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> ModalityManager:
        """Deserialize from dictionary."""
        manager = cls()
        
        # Restore modalities
        for mod_data in data.get("modalities", []):
            modality = ModalitySpec.from_dict(mod_data)
            manager.modalities.append(modality)
            manager._next_idx = max(manager._next_idx, modality.idx + 1)
        
        # Restore links
        links_data = data.get("links", {})
        manager.links.zoom_pan_linked = {
            tuple(pair) for pair in links_data.get("zoom_pan_linked", [])
        }
        manager.links.playback_linked = {
            tuple(pair) for pair in links_data.get("playback_linked", [])
        }
        manager.links.contrast_sync_options = links_data.get(
            "contrast_sync_options",
            {
                "sync_vmin": False,
                "sync_vmax": False,
                "sync_contrast": False,
            },
        )
        manager.links.playback_mode = links_data.get("playback_mode", "synchronized")
        
        manager.modalities.sort(key=lambda m: m.idx)
        return manager
    
    @staticmethod
    def create_from_primary_support(
        primary_img_id: int,
        support_img_id: Optional[int] = None,
    ) -> ModalityManager:
        """Create manager with default Primary/Support modalities.
        
        Used for backward compatibility when upgrading old sessions.
        
        Parameters
        ----------
        primary_img_id : int
            Index of primary image.
        support_img_id : int, optional
            Index of support image (if 2-modality session).
        
        Returns
        -------
        ModalityManager
            New manager with Modality 1 and optionally Modality 2.
        """
        manager = ModalityManager()
        manager.add_modality(primary_img_id, "Modality 1")
        if support_img_id is not None and support_img_id >= 0:
            manager.add_modality(support_img_id, "Modality 2")
        return manager
