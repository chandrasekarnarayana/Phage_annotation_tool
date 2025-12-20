"""Image metadata and loading helpers for the GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import tifffile as tif

from phage_annotator.gui_constants import BIG_TIFF_BYTES_THRESHOLD
from phage_annotator.gui_debug import debug_log
from phage_annotator.image_models import LazyImage
from phage_annotator.io import read_metadata_summary, standardize_axes


def read_metadata(path: Path) -> LazyImage:
    """Read lightweight metadata for an image without loading full data."""
    summary = read_metadata_summary(path)
    with tif.TiffFile(str(path)) as tf:
        page = tf.series[0]
        shape = page.shape
        dtype = str(page.dtype)
        ome_axes = page.axes if tf.ome_metadata else None
    interpret = "auto"
    axis_auto_used = False
    axis_auto_mode = None
    if ome_axes and len(ome_axes) == len(shape):
        axes = ome_axes.upper()
        has_time = "T" in axes
        has_z = "Z" in axes
        if len(shape) == 3:
            if "T" in axes and "Z" not in axes:
                interpret = "time"
            elif "Z" in axes and "T" not in axes:
                interpret = "depth"
    else:
        # Heuristic: only used when no OME metadata is available.
        if len(shape) == 3:
            axis_auto_used = True
            axis_auto_mode = "time" if shape[0] <= 5 else "depth"
        has_time = len(shape) == 4 or (len(shape) == 3 and axis_auto_mode == "time")
        has_z = len(shape) == 4 or (len(shape) == 3 and axis_auto_mode == "depth")
    if ome_axes:
        has_time = "T" in ome_axes.upper()
        has_z = "Z" in ome_axes.upper()
    return LazyImage(
        path=path,
        name=path.name,
        shape=shape,
        dtype=dtype,
        has_time=has_time,
        has_z=has_z,
        interpret_3d_as=interpret,
        ome_axes=ome_axes,
        axis_auto_used=axis_auto_used,
        axis_auto_mode=axis_auto_mode,
        metadata_summary=summary,
    )


def load_array(path: Path, interpret_3d_as: str = "auto", ome_axes: Optional[str] = None) -> Tuple[object, bool, bool]:
    """Load image data and standardize to (T, Z, Y, X)."""
    with tif.TiffFile(str(path)) as tf:
        nbytes = tf.asarray().nbytes
    if nbytes >= BIG_TIFF_BYTES_THRESHOLD:
        debug_log(f"Using memmap for {path} ({nbytes/1e6:.1f} MB)")
        arr = tif.memmap(str(path))
    else:
        debug_log(f"Loading into memory {path} ({nbytes/1e6:.1f} MB)")
        arr = tif.imread(str(path))
    std, has_time, has_z = standardize_axes(arr, interpret_3d_as=interpret_3d_as, ome_axes=ome_axes)
    return std, has_time, has_z
