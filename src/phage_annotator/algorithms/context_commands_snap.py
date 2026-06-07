"""Algorithms context commands snap helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Tuple

import numpy as np
import tifffile as tif
from scipy.ndimage import maximum_filter
from scipy.optimize import curve_fit

from phage_annotator.io import standardize_axes

_logger = logging.getLogger(__name__)


def roi_stats(frame: np.ndarray, roi_mask: np.ndarray) -> Tuple[float, float, float, float, int]:
    """Compute mean/std/min/max and area for an ROI mask."""
    vals = frame[roi_mask]
    if vals.size == 0:
        return (
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            int(roi_mask.sum()),
        )
    return (
        float(vals.mean()),
        float(vals.std()),
        float(vals.min()),
        float(vals.max()),
        int(roi_mask.sum()),
    )

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

def local_maxima(masked: np.ndarray, threshold: float, footprint: int = 3) -> np.ndarray:
    """Return coordinates of local maxima above a threshold.

    Parameters
    ----------
    masked : numpy.ndarray
        Input 2D array (background outside ROI can be -inf).
    threshold : float
        Minimum value for detected peaks.
    footprint : int
        Neighborhood size for local maxima detection.

    Returns
    -------
    coords : numpy.ndarray
        Array of (y, x) coordinates for candidate peaks.
    """
    if masked.size == 0:
        return np.empty((0, 2), dtype=int)
    size = max(3, int(footprint))
    max_filt = maximum_filter(masked, size=size, mode="nearest")
    peaks = (masked == max_filt) & (masked >= threshold)
    coords = np.column_stack(np.nonzero(peaks))
    return coords

def gaussian_2d(
    coords: Tuple[np.ndarray, np.ndarray],
    amp: float,
    x0: float,
    y0: float,
    sigma: float,
    offset: float,
) -> np.ndarray:
    """Evaluate a symmetric 2D Gaussian on a meshgrid."""
    x, y = coords
    g = amp * np.exp(-(((x - x0) ** 2 + (y - y0) ** 2) / (2 * sigma**2))) + offset
    return g.ravel()

def fit_gaussian_2d(
    patch: np.ndarray,
) -> Tuple[float, float, float, float, float, Optional[np.ndarray]]:
    """Fit a symmetric 2D Gaussian to a small patch.

    Returns
    -------
    amp, x0, y0, sigma, offset, cov : tuple
        Fit parameters and covariance matrix (or None if fit fails).
    """
    h, w = patch.shape
    if h < 3 or w < 3:
        raise ValueError("Patch too small for Gaussian fit.")
    y = np.arange(h)
    x = np.arange(w)
    xx: np.ndarray
    yy: np.ndarray
    xx, yy = np.meshgrid(x, y)
    amp0 = float(patch.max() - patch.min())
    offset0 = float(patch.min())
    x0 = float(w / 2)
    y0 = float(h / 2)
    sigma0 = max(0.6, min(h, w) / 3)
    try:
        popt, pcov = curve_fit(
            gaussian_2d,
            (xx, yy),
            patch.ravel(),
            p0=(amp0, x0, y0, sigma0, offset0),
            maxfev=5000,
        )
    except Exception as exc:
        raise ValueError("Gaussian fit failed.") from exc
    amp, x0, y0, sigma, offset = [float(v) for v in popt]
    return amp, x0, y0, sigma, offset, pcov
