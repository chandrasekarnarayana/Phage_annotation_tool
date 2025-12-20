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
    metadata_summary: dict = field(default_factory=dict)
    mean_proj: Optional[np.ndarray] = None
    std_proj: Optional[np.ndarray] = None
