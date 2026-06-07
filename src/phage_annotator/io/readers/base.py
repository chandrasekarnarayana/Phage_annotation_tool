"""TIFF/OME-TIFF loading and axis normalization utilities.

This module standardizes image arrays into (T, Z, Y, X) order and carries
axis metadata derived from OME when available. When OME metadata is missing,
it falls back to a conservative heuristic for 3D stacks.

Conventions
-----------
- Arrays are returned in (T, Z, Y, X) order.
- OME metadata has priority when available and consistent with array shape.
- Heuristic fallback uses axis0 <= 5 to interpret 3D as time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np
import tifffile as tif

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.io.metadata.reader import read_metadata as _read_metadata
from phage_annotator.io.metadata.reader import read_metadata_summary as _read_summary

__all__ = [
    "ImageMeta",
    "load_images",
    "parse_axes_info",
    "standardize_axes",
    "read_contiguous_block",
    "read_contiguous_block_from_path",
    "read_metadata_bundle",
    "read_metadata_summary",
]


AXIS_CONTRACT = {
    "required_axes": ("Y", "X"),
    "supported_axes": ("T", "Z", "Y", "X", "C"),
    "heuristic_3d": "axis0<=5 => time else depth",
}


from phage_annotator.io.readers.reader_axes import parse_axes_info
from phage_annotator.io.readers.reader_axes import _validate_ome_axes, ImageMeta, standardize_axes, load_images, read_contiguous_block_from_path
from phage_annotator.io.readers.reader_io import read_contiguous_block, read_metadata_bundle, read_metadata_summary
