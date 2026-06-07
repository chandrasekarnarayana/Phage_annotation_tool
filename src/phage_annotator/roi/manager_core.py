"""Roi manager core helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Roi:
    """ROI definition in full-resolution coordinates.
    
    Position binding:
    - z_index: -1 = all z-slices, 0+ = specific z-slice
    - t_index: -1 = all time frames, 0+ = specific time frame
    - c_index: -1 = all channels, 0+ = specific channel
    
    Tags system:
    - tags: List of strings for grouping and filtering ROIs
    """

    roi_id: int
    name: str
    roi_type: str  # box|circle|polygon|polyline
    points: List[Tuple[float, float]]
    color: str = "#ffcc00"
    visible: bool = True
    z_index: int = -1  # -1 = all slices
    t_index: int = -1  # -1 = all frames
    c_index: int = -1  # -1 = all channels
    tags: List[str] = field(default_factory=list)  # tags for grouping/filtering


from phage_annotator.roi.manager_core_impl import RoiManager
