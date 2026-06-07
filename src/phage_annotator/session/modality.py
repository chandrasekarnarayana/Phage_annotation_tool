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
    MEDIAN = "median"     # Median projection across axis
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


import phage_annotator.session.modality_manager_core as _modality_core
from phage_annotator.session.modality_manager_core import ModalityManagerCoreMixin

_modality_core.ModalityDisplaySettings = ModalityDisplaySettings
_modality_core.ModalityLinks = ModalityLinks
_modality_core.ModalitySpec = ModalitySpec
_modality_core.ProjectionType = ProjectionType


class ModalityManager(ModalityManagerCoreMixin):
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
modality_count() -> int"""

    RESERVED_NAMES = {"Primary", "Support", "Frame", "Stack"}
