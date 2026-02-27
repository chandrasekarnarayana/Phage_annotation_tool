"""Lightweight image metadata containers used by the GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


@dataclass
class LazyImage:
    """Metadata and lazy-loaded array for a single image.

    Arrays are loaded on demand and standardized to (T, Z, Y, X). When memmap
    is enabled, ``array`` may be a numpy memmap slice view.
    
    Diagnostics
    -----------
    downsampled : bool
        True if array was spatially downsampled due to memory pressure.
    downsampling_reason : Optional[str]
        Reason for downsampling (e.g., "Memory pressure: 2.1 GB > 1.5 GB threshold").
    downsample_factor : int
        Factor by which image was downsampled (default 1 = no downsampling).
    """

    path: Path
    name: str
    shape: Tuple[int, ...]
    dtype: str
    has_time: bool
    has_z: bool
    array: Optional[np.ndarray] = None
    id: int = -1
    interpret_3d_as: str = "auto"
    ome_axes: Optional[str] = None
    axis_auto_used: bool = False
    axis_auto_mode: Optional[str] = None
    channel_count: int = 1
    channel_idx: int = 0
    axis_info: dict = field(default_factory=dict)
    metadata_summary: dict = field(default_factory=dict)
    mean_proj: Optional[np.ndarray] = None
    std_proj: Optional[np.ndarray] = None
    downsampled: bool = False
    downsampling_reason: Optional[str] = None
    downsample_factor: int = 1
