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


def _validate_ome_axes(
    ome_axes: str,
    shape: tuple[int, ...],
    strict: bool,
) -> str | None:
    axes = ome_axes.upper()
    if len(axes) != len(shape):
        if strict:
            raise ValueError(
                f"OME axes length {len(axes)} does not match shape {len(shape)}"
            )
        return None
    if any(ax not in AXIS_CONTRACT["supported_axes"] for ax in axes):
        if strict:
            raise ValueError(f"Unsupported OME axes: {axes}")
        return None
    if not all(ax in axes for ax in AXIS_CONTRACT["required_axes"]):
        if strict:
            raise ValueError(f"OME axes must include {AXIS_CONTRACT['required_axes']}")
        return None
    return axes


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
    arr: np.ndarray,
    interpret_3d_as: str = "auto",
    ome_axes: Optional[str] = None,
    channel_idx: int = 0,
    strict: bool = False,
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
    - strict=True raises ValueError on invalid axes metadata.
    """
    if ome_axes:
        axes = _validate_ome_axes(ome_axes, arr.shape, strict)
        if axes is None:
            ome_axes = None
        else:
            ome_axes = axes
    if ome_axes:
        axes = ome_axes.upper()
        if "C" in axes:
            c_idx = axes.index("C")
            if arr.shape[c_idx] > 1:
                if channel_idx < 0 or channel_idx >= arr.shape[c_idx]:
                    if strict:
                        raise ValueError(
                            f"Invalid channel_idx {channel_idx} for size {arr.shape[c_idx]}"
                        )
                    channel_idx = 0
                arr = np.take(arr, int(channel_idx), axis=c_idx)
            else:
                arr = np.squeeze(arr, axis=c_idx)
            axes = "".join(ax for ax in axes if ax != "C")
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
    elif ndim == 5:
        if strict:
            raise ValueError(f"Unsupported image ndim={ndim}, shape={arr.shape}")
        # Heuristic: assume channel axis first (CTZYX) and select first channel.
        arr = arr[0]
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
        if isinstance(p, (tuple, list)) and p:
            p = p[0]
        p = Path(p)
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
    channel_idx: int = 0,
    apply_memory_sampling: bool = False,
) -> np.ndarray:
    """Read a contiguous block of frames from disk and standardize axes.

    This helper prefers tifffile's key slicing for contiguous reads and falls
    back to a per-frame loop when key slicing is unavailable.
    
    Parameters
    ----------
    path : Path
        Path to TIFF file.
    t_start, t_stop : int
        Time frame range [t_start, t_stop) to read.
    z_idx : int
        Z-slice index to extract.
    interpret_3d_as : str
        Interpretation for 3D stacks ("auto", "time", "depth").
    ome_axes : Optional[str]
        OME axes metadata if available.
    channel_idx : int
        Channel index for multi-channel selection.
    apply_memory_sampling : bool
        If True, apply spatial 2x downsampling to reduce memory footprint.
        Used when prefetching under memory pressure.
        
    Returns
    -------
    np.ndarray
        Contiguous block of shape (t_stop - t_start, Y, X) or (t_stop - t_start, Y//2, X//2) if downsampled.
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
    std, _, _ = standardize_axes(
        arr,
        interpret_3d_as=interpret_3d_as,
        ome_axes=ome_axes,
        channel_idx=channel_idx,
    )
    result = std[:, z_idx, :, :]
    
    # Apply spatial downsampling if memory sampling enabled
    if apply_memory_sampling and result.ndim >= 2:
        result = result[::2, ::2]
    
    return result


def read_metadata_bundle(path: Path) -> MetadataBundle:
    """Read full metadata bundle from a TIFF/OME-TIFF."""
    return _read_metadata(str(path))


def read_metadata_summary(path: Path) -> dict:
    """Read a summary metadata dict without parsing full raw tags."""
    return _read_summary(str(path))
