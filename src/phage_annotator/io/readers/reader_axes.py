"""Readers reader axes helpers for the phage annotation tool.

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
from phage_annotator.io.readers.reader_axes_impl import (
    ImageMeta,
    _validate_ome_axes,
    load_images,
    read_contiguous_block_from_path,
    standardize_axes,
)
from phage_annotator.io.readers.reader_io import (
    read_contiguous_block,
    read_metadata_bundle,
    read_metadata_summary,
)

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


def parse_axes_info(
    shape: Tuple[int, ...],
    ome_axes: Optional[str] = None,
    interpret_3d_as: str = "auto",
) -> dict:
    """Parse axes metadata into a normalized axis info dictionary."""
    axes = None
    source = "heuristic"
    inferred = True
    ndim = len(shape)
    if ome_axes and len(ome_axes) == ndim:
        axes = ome_axes.upper()
        source = "ome"
        inferred = False
    else:
        mode = interpret_3d_as.lower()
        if mode not in {"auto", "time", "depth"}:
            mode = "auto"
        if ndim == 2:
            axes = "YX"
        elif ndim == 3:
            if mode == "auto":
                mode = "time" if shape[0] <= 5 else "depth"
            axes = "TYX" if mode == "time" else "ZYX"
        elif ndim == 4:
            axes = "TZYX"
        elif ndim == 5:
            axes = "CTZYX"
        else:
            axes = ""
    channel_axis = axes.find("C") if "C" in axes else None
    channel_count = int(shape[channel_axis]) if channel_axis is not None else 1
    mapping = dict(zip(axes, shape)) if axes else {}
    t_dim = int(mapping.get("T", 1))
    z_dim = int(mapping.get("Z", 1))
    y_dim = int(mapping.get("Y", shape[-2] if ndim >= 2 else 1))
    x_dim = int(mapping.get("X", shape[-1] if ndim >= 1 else 1))
    return {
        "axes": axes,
        "shape": tuple(shape),
        "channel_axis": channel_axis,
        "channel_count": channel_count,
        "has_time": "T" in axes if axes else False,
        "has_z": "Z" in axes if axes else False,
        "tzyx": (t_dim, z_dim, y_dim, x_dim),
        "inferred": inferred,
        "source": source,
    }
