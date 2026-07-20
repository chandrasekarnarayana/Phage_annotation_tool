"""Readers reader io helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
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
    "read_contiguous_block",
    "read_metadata_bundle",
    "read_metadata_summary",
]


AXIS_CONTRACT = {
    "required_axes": ("Y", "X"),
    "supported_axes": ("T", "Z", "Y", "X", "C"),
    "heuristic_3d": "axis0<=5 => time else depth",
}


def read_contiguous_block(arr: np.ndarray, t_start: int, t_stop: int, z_idx: int) -> np.ndarray:
    """Return a contiguous block (T slice) from a standardized (T, Z, Y, X) array.

    Contiguous slicing helps the OS perform sequential reads for memmap-backed
    arrays, reducing disk seek overhead during playback.
    """
    return arr[t_start:t_stop, z_idx, :, :]

def read_metadata_bundle(path: Path) -> MetadataBundle:
    """Read full metadata bundle from a TIFF/OME-TIFF."""
    return _read_metadata(str(path))

def read_metadata_summary(path: Path) -> dict:
    """Read a summary metadata dict without parsing full raw tags."""
    return _read_summary(str(path))
