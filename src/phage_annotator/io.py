from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import tifffile as tif

__all__ = ["ImageMeta", "load_images", "standardize_axes"]


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


def standardize_axes(arr: np.ndarray, interpret_3d_as: str = "auto") -> tuple[np.ndarray, bool, bool]:
    """
    Convert an array to (T, Z, Y, X) format and report the presence of time/Z axes.

    Rules:
      - 2D (Y,X) -> (1,1,Y,X)
      - 3D (Z,Y,X) -> (1,Z,Y,X)
      - 3D (T,Y,X) -> (T,1,Y,X) or (1,Z,Y,X) based on interpretation
      - 4D (T,Z,Y,X) -> (T,Z,Y,X)

    Heuristic for 3D when interpret_3d_as="auto": if the first axis <= 5, treat as time; otherwise treat as depth.
    """
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
    """Load TIFF/OME-TIFF stacks, standardize axes, and wrap in ImageMeta."""
    metas: List[ImageMeta] = []
    for idx, p in enumerate(paths):
        arr = tif.imread(str(p))
        std, has_time, has_z = standardize_axes(arr)
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
