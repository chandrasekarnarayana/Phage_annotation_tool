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

from phage_annotator.metadata_reader import MetadataBundle
from phage_annotator.metadata_reader import read_metadata as _read_metadata
from phage_annotator.metadata_reader import read_metadata_summary as _read_summary

__all__ = [
    "ImageMeta",
    "load_images",
    "standardize_axes",
    "read_contiguous_block",
    "read_contiguous_block_from_path",
    "read_metadata_bundle",
    "read_metadata_summary",
]


@dataclass
class ImageMeta:
    """Container for a loaded image stack standardized to (T, Z, Y, X).

    Attributes mirror the file path, a standardized array, original shape, and flags for time/Z axes.
    """

    id: int
    path: Path
    name: str
    array: np.ndarray  # shape (T, Z, Y, X)
    original_shape: Tuple[int, ...]
    has_time: bool
    has_z: bool


def standardize_axes(
    arr: np.ndarray, interpret_3d_as: str = "auto", ome_axes: Optional[str] = None
) -> tuple[np.ndarray, bool, bool]:
    """Standardize an array to (T, Z, Y, X) and report time/Z presence.

    Parameters
    ----------
    arr : numpy.ndarray
        Input array in an unknown axis order.
    interpret_3d_as : {"auto", "time", "depth"}
        Interpretation for 3D stacks when metadata is unavailable.
    ome_axes : str, optional
        OME axes string (e.g., "TCZYX") when available.

    Returns
    -------
    tuple[numpy.ndarray, bool, bool]
        Standardized array, has_time, has_z flags.

    Notes
    -----
    - OME metadata takes priority when available and consistent.
    - Heuristic fallback for 3D uses axis0 <= 5 as time.
    """
    if ome_axes:
        axes = ome_axes.upper()
        if len(axes) == arr.ndim:
            keep_axes = []
            squeeze_axes = []
            for idx, ax in enumerate(axes):
                if ax in {"T", "Z", "Y", "X"}:
                    keep_axes.append((idx, ax))
                else:
                    if arr.shape[idx] == 1:
                        squeeze_axes.append(idx)
                    else:
                        keep_axes = []
                        break
            if keep_axes:
                if squeeze_axes:
                    arr = np.squeeze(arr, axis=tuple(squeeze_axes))
                axes_kept = "".join(ax for _, ax in keep_axes)
                order = [axes_kept.index(ax) for ax in "TZYX" if ax in axes_kept]
                arr = np.transpose(arr, order)
                for pos, ax in enumerate("TZYX"):
                    if ax not in axes_kept:
                        arr = np.expand_dims(arr, axis=pos)
                has_time = "T" in axes_kept
                has_z = "Z" in axes_kept
                return arr, has_time, has_z

    ndim = arr.ndim
    if ndim == 2:
        arr = arr[np.newaxis, np.newaxis, :, :]
        has_time, has_z = False, False
    elif ndim == 3:
        axis0 = arr.shape[0]
        mode = interpret_3d_as.lower()
        if mode not in {"auto", "time", "depth"}:
            raise ValueError(f"Invalid interpret_3d_as: {interpret_3d_as}")
        if mode == "auto":
            mode = "time" if axis0 <= 5 else "depth"
        if mode == "time":
            arr = arr[:, np.newaxis, :, :]
            has_time, has_z = True, False
        else:
            arr = arr[np.newaxis, :, :, :]
            has_time, has_z = False, True
    elif ndim == 4:
        has_time, has_z = True, True
    else:
        raise ValueError(f"Unsupported image ndim={ndim}, shape={arr.shape}")
    return arr, has_time, has_z


def load_images(paths: Iterable[Path]) -> List[ImageMeta]:
    """Load TIFF/OME-TIFF stacks, standardize axes, and wrap in ImageMeta.

    OME metadata is used when available; otherwise, the heuristic fallback
    in ``standardize_axes`` is applied.
    """
    metas: List[ImageMeta] = []
    for idx, p in enumerate(paths):
        axes = None
        try:
            with tif.TiffFile(str(p)) as tf:
                if tf.ome_metadata:
                    axes = tf.series[0].axes
        except Exception:
            axes = None
        arr = tif.imread(str(p))
        std, has_time, has_z = standardize_axes(arr, ome_axes=axes)
        metas.append(
            ImageMeta(
                id=idx,
                path=p,
                name=p.name,
                array=std,
                original_shape=arr.shape,
                has_time=has_time,
                has_z=has_z,
            )
        )
    return metas


def read_contiguous_block(arr: np.ndarray, t_start: int, t_stop: int, z_idx: int) -> np.ndarray:
    """Return a contiguous block (T slice) from a standardized (T, Z, Y, X) array.

    Contiguous slicing helps the OS perform sequential reads for memmap-backed
    arrays, reducing disk seek overhead during playback.
    """
    return arr[t_start:t_stop, z_idx, :, :]


def read_contiguous_block_from_path(
    path: Path,
    t_start: int,
    t_stop: int,
    z_idx: int,
    interpret_3d_as: str = "auto",
    ome_axes: Optional[str] = None,
) -> np.ndarray:
    """Read a contiguous block of frames from disk and standardize axes.

    This helper prefers tifffile's key slicing for contiguous reads and falls
    back to a per-frame loop when key slicing is unavailable.
    """
    try:
        arr = tif.imread(str(path), key=slice(t_start, t_stop))
    except Exception:
        frames = []
        with tif.TiffFile(str(path)) as tf:
            series = tf.series[0]
            for idx in range(t_start, t_stop):
                frames.append(series.asarray(key=idx))
        if not frames:
            return np.empty((0, 0, 0), dtype=np.float32)
        arr = np.stack(frames, axis=0)
    std, _, _ = standardize_axes(arr, interpret_3d_as=interpret_3d_as, ome_axes=ome_axes)
    return std[:, z_idx, :, :]


def read_metadata_bundle(path: Path) -> MetadataBundle:
    """Read full metadata bundle from a TIFF/OME-TIFF."""
    return _read_metadata(str(path))


def read_metadata_summary(path: Path) -> dict:
    """Read a lightweight metadata summary without pixel data."""
    return _read_summary(str(path))
