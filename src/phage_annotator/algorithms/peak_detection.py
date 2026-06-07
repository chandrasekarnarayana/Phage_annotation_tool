"""Peak finding and 2D Gaussian fitting helpers."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.optimize import curve_fit

_logger = logging.getLogger(__name__)


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
