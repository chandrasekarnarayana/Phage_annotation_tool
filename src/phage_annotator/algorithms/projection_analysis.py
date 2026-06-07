"""Projection computation and statistical helper functions."""

from __future__ import annotations

import logging
from typing import Iterable, Optional, Tuple

import numpy as np

_logger = logging.getLogger(__name__)


def compute_mean_std(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute mean/std projections over T and Z dimensions."""
    mean_proj = arr.mean(axis=(0, 1)).astype(np.float32, copy=False)
    std_proj = arr.std(axis=(0, 1)).astype(np.float32, copy=False)
    return mean_proj, std_proj


def compute_projections(
    arr: np.ndarray,
    kinds: Iterable[str],
    axis: str = "tz",
) -> dict[str, np.ndarray]:
    """Compute multiple projections over the requested axes.

    Parameters
    ----------
    arr : np.ndarray
        Image array in (T, Z, Y, X) order.
    kinds : Iterable[str]
        Projection kinds: "mean", "median", "std", "min", "max".
    axis : str
        Projection axis: "tz" (default), "t", or "z".

    Returns
    -------
    dict[str, np.ndarray]
        Mapping of kind -> projection array (2D).
    """
    axis = axis.lower()
    reduce_axes: tuple[int, ...]
    if axis == "t":
        reduce_axes = (0,)
    elif axis == "z":
        reduce_axes = (1,)
    else:
        reduce_axes = (0, 1)

    results: dict[str, np.ndarray] = {}
    for kind in kinds:
        kind_l = kind.lower()
        if kind_l == "mean":
            proj = arr.mean(axis=reduce_axes)
        elif kind_l == "median":
            proj = np.median(arr, axis=reduce_axes)
        elif kind_l == "std":
            proj = arr.std(axis=reduce_axes)
        elif kind_l == "min":
            proj = arr.min(axis=reduce_axes)
        elif kind_l == "max":
            proj = arr.max(axis=reduce_axes)
        else:
            raise ValueError(f"Unsupported projection kind: {kind}")
        results[kind_l] = proj.astype(np.float32, copy=False)
    return results


def compute_projection(arr: np.ndarray, kind: str, axis: str = "tz") -> np.ndarray:
    """Compute a single projection over the requested axes."""
    if str(kind).lower() not in {"mean", "std", "min", "max"}:
        raise ValueError(f"Unsupported projection kind: {kind}")
    return compute_projections(arr, [kind], axis=axis)[kind.lower()]


def compute_auto_window(
    array_or_sampler,
    low_pct: float,
    high_pct: float,
    roi_mask: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    """Compute an auto-contrast window using percentile bounds.

    Parameters
    ----------
    array_or_sampler : np.ndarray or callable
        Source data or a callable returning a 1D sample array.
    low_pct, high_pct : float
        Percentile bounds in [0, 100].
    roi_mask : np.ndarray, optional
        Boolean mask to apply when array input is used.

    Returns
    -------
    vmin, vmax : float
        Percentile window bounds.
    """
    if callable(array_or_sampler):
        sample = array_or_sampler()
    else:
        arr = np.asarray(array_or_sampler)
        if roi_mask is not None and roi_mask.shape == arr.shape:
            sample = arr[roi_mask]
        else:
            sample = arr.ravel()
    if sample.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(sample, low_pct))
    vmax = float(np.percentile(sample, high_pct))
    if vmin > vmax:
        vmin, vmax = vmax, vmin
    return vmin, vmax


def mad_sigma(arr: np.ndarray, scale: float = 1.4826) -> float:
    """Estimate noise sigma using the median absolute deviation (MAD)."""
    data = np.asarray(arr).ravel()
    if data.size == 0:
        return 0.0
    med = np.median(data)
    mad = np.median(np.abs(data - med))
    return float(scale * mad)
