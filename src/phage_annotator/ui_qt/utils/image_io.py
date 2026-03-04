"""Image metadata and loading helpers for the GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np
import tifffile as tif

from phage_annotator.ui_qt.utils.constants import BIG_TIFF_BYTES_THRESHOLD
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.config.performance import MEMORY_THRESHOLD_BYTES, DOWNSAMPLE_FACTOR_FOR_PRESSURE
from phage_annotator.data.models import LazyImage
from phage_annotator.io import parse_axes_info, read_metadata_summary, standardize_axes
from phage_annotator.data.pyramid import downsample_mean_pool


class DiagnosticArray(np.ndarray):
    """NumPy array subclass that can carry lightweight diagnostics metadata."""


def _attach_diagnostics(arr: np.ndarray, diagnostics: dict[str, Any]) -> np.ndarray:
    """Attach diagnostics metadata to an array in a NumPy-safe way.

    Plain ``numpy.ndarray`` instances do not support arbitrary attributes.
    Converting the view to ``DiagnosticArray`` preserves the underlying buffer
    while allowing us to expose ``_diagnostics`` to downstream consumers.
    """
    if not isinstance(arr, DiagnosticArray):
        arr = arr.view(DiagnosticArray)
    arr._diagnostics = diagnostics  # type: ignore[attr-defined]
    return arr


def _downsample_spatial(arr: np.ndarray, factor: int) -> np.ndarray:
    """Downsample the last two (Y, X) dimensions by mean pooling.

    For 2D arrays this delegates to ``downsample_mean_pool``. For nD arrays
    (for example TZYX), all leading dimensions are preserved and only spatial
    dimensions are reduced.
    """
    factor = int(max(1, factor))
    if factor == 1:
        return arr
    if arr.ndim == 2:
        return downsample_mean_pool(arr, factor)
    if arr.ndim < 2:
        return arr

    h, w = arr.shape[-2], arr.shape[-1]
    h_trim = (h // factor) * factor
    w_trim = (w // factor) * factor
    if h_trim == 0 or w_trim == 0:
        return arr
    trimmed = arr[..., :h_trim, :w_trim]
    leading = trimmed.shape[:-2]
    reshaped = trimmed.reshape(
        *leading,
        h_trim // factor,
        factor,
        w_trim // factor,
        factor,
    )
    return reshaped.mean(axis=(-3, -1), dtype=np.float32)


def read_metadata(path: Path) -> LazyImage:
    """Read lightweight metadata for an image without loading full data."""
    summary = read_metadata_summary(path)
    with tif.TiffFile(str(path)) as tf:
        page = tf.series[0]
        shape = page.shape
        dtype = str(page.dtype)
        ome_axes = page.axes  # Read axes from tifffile (works with metadata dict or OME-XML)
    interpret = "auto"
    if ome_axes and len(ome_axes) == len(shape):
        axes = ome_axes.upper()
        if len(shape) == 3:
            if "T" in axes and "Z" not in axes:
                interpret = "time"
            elif "Z" in axes and "T" not in axes:
                interpret = "depth"
    axis_info = parse_axes_info(shape, ome_axes=ome_axes, interpret_3d_as=interpret)
    axis_auto_used = axis_info.get("source") == "heuristic" and len(shape) == 3
    axis_auto_mode = None
    if axis_auto_used:
        axis_auto_mode = "time" if axis_info.get("axes", "").startswith("T") else "depth"
    return LazyImage(
        path=path,
        name=path.name,
        shape=shape,
        dtype=dtype,
        has_time=axis_info.get("has_time", False),
        has_z=axis_info.get("has_z", False),
        interpret_3d_as=interpret,
        ome_axes=ome_axes,
        axis_auto_used=axis_auto_used,
        axis_auto_mode=axis_auto_mode,
        channel_count=int(axis_info.get("channel_count", 1)),
        axis_info=axis_info,
        metadata_summary=summary,
    )


def load_array(
    path: Path,
    interpret_3d_as: str = "auto",
    ome_axes: Optional[str] = None,
    channel_idx: int = 0,
) -> Tuple[object, bool, bool]:
    """Load image data and standardize to (T, Z, Y, X).
    
    If memory pressure detected (nbytes > MEMORY_THRESHOLD_BYTES), applies
    spatial downsampling (2x default) to reduce memory footprint while maintaining
    temporal/depth dimensions. The downsampling reason is attached to the array.
    
    Returns
    -------
    Tuple[np.ndarray, bool, bool]
        (standardized_array, has_time, has_z)
    """
    with tif.TiffFile(str(path)) as tf:
        nbytes = tf.asarray().nbytes
    
    # Determine load strategy
    use_memmap = nbytes >= BIG_TIFF_BYTES_THRESHOLD
    downsample_reason = None
    downsample_factor = 1
    
    if nbytes >= BIG_TIFF_BYTES_THRESHOLD:
        debug_log(f"Using memmap for {path} ({nbytes/1e9:.2f} GB)")
        arr = tif.memmap(str(path))
    else:
        debug_log(f"Loading into memory {path} ({nbytes/1e9:.2f} GB)")
        arr = tif.imread(str(path))
    
    # Check if memory pressure warrants downsampling
    if nbytes > MEMORY_THRESHOLD_BYTES:
        downsample_factor = DOWNSAMPLE_FACTOR_FOR_PRESSURE
        downsample_reason = (
            f"Memory pressure: {nbytes/1e9:.2f} GB > {MEMORY_THRESHOLD_BYTES/1e9:.2f} GB threshold"
        )
        debug_log(downsample_reason)
    
    std, has_time, has_z = standardize_axes(
        arr,
        interpret_3d_as=interpret_3d_as,
        ome_axes=ome_axes,
        channel_idx=channel_idx,
    )
    
    # Apply spatial downsampling if memory pressure detected
    if downsample_factor > 1 and std.ndim >= 2:
        # Downsample spatial dimensions (Y, X are last 2 dims in (T, Z, Y, X) order)
        # Use mean-pool to preserve image content quality
        original_shape = std.shape
        std = _downsample_spatial(std, downsample_factor)
        debug_log(
            f"Downsampled image from {original_shape} to {std.shape} "
            f"({downsample_factor}x spatial downsampling)"
        )
    
    diagnostics = {
        "downsampled": bool(downsample_reason),
        "downsampling_reason": downsample_reason,
        "downsample_factor": int(downsample_factor),
    }
    std = _attach_diagnostics(std, diagnostics)

    return std, has_time, has_z
