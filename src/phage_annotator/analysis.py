"""Pure analysis helpers for background jobs (no Qt dependencies).

Functions in this module are safe to run in background threads. They operate
on numpy arrays and plain data structures, avoiding any Qt or GUI state.

Conventions
-----------
- Arrays are expected in (T, Z, Y, X) order.
- Coordinates are full-resolution image coordinates unless explicitly cropped.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

import numpy as np
import tifffile as tif
from scipy.ndimage import maximum_filter
from scipy.optimize import curve_fit

from phage_annotator.io import standardize_axes


def compute_mean_std(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute mean/std projections over (T, Z) axes.

    Parameters
    ----------
    arr : numpy.ndarray
        Input array in (T, Z, Y, X).

    Returns
    -------
    mean_proj, std_proj : numpy.ndarray
        Mean and standard deviation projections in (Y, X).
    """
    mean_proj = arr.mean(axis=(0, 1)).astype(np.float32, copy=False)
    std_proj = arr.std(axis=(0, 1)).astype(np.float32, copy=False)
    return mean_proj, std_proj


def compute_roi_mean_for_path(
    path: str,
    roi_rect: Tuple[float, float, float, float],
    roi_shape: str,
    crop_rect: Tuple[float, float, float, float],
) -> float:
    """Load a TIFF path and compute ROI mean on the first frame.

    Parameters
    ----------
    path : str
        TIFF path to load.
    roi_rect : tuple[float, float, float, float]
        ROI rectangle in (X, Y, W, H) in full-resolution coordinates.
    roi_shape : {"box", "circle"}
        Shape of the ROI.
    crop_rect : tuple[float, float, float, float]
        Display crop (X, Y, W, H); ROI is applied after cropping.
    """
    arr = tif.imread(path, maxworkers=1)
    std, _, _ = standardize_axes(arr)
    frame = std[0, 0, :, :]
    frame_cropped = apply_crop_rect(frame, crop_rect)
    roi_mask = roi_mask_for_shape(frame_cropped.shape, roi_rect, roi_shape)
    vals = frame_cropped[roi_mask]
    return float(vals.mean()) if vals.size else float("nan")


def compute_bleach_means(
    arr: np.ndarray,
    roi_rect: Tuple[float, float, float, float],
    roi_shape: str,
    crop_rect: Tuple[float, float, float, float],
) -> list[float]:
    """Compute per-frame ROI mean over time for a (T, Z, Y, X) array."""
    means: list[float] = []
    for t in range(arr.shape[0]):
        frame = arr[t, 0, :, :]
        frame_cropped = apply_crop_rect(frame, crop_rect)
        roi_mask = roi_mask_for_shape(frame_cropped.shape, roi_rect, roi_shape)
        vals = frame_cropped[roi_mask]
        means.append(float(vals.mean()) if vals.size else float("nan"))
    return means


def fit_bleach_curve(means: Iterable[float]) -> Tuple[np.ndarray, np.ndarray, str]:
    """Fit an exponential decay curve to ROI means.

    Returns
    -------
    xs : numpy.ndarray
        Frame indices.
    fit : numpy.ndarray
        Fitted curve values.
    eq : str
        Equation string for display.
    """
    ys = np.array(list(means), dtype=float)
    xs = np.arange(len(ys))

    def exp_decay(x, a, b, c):
        return a * np.exp(-b * x) + c

    popt, _ = curve_fit(exp_decay, xs, ys, maxfev=10000)
    fit = exp_decay(xs, *popt)
    eq = f"y = {popt[0]:.3f}*exp(-{popt[1]:.3f}*x)+{popt[2]:.3f}"
    return xs, fit, eq


def apply_crop_rect(frame: np.ndarray, crop_rect: Tuple[float, float, float, float]) -> np.ndarray:
    """Apply a rectangular crop to a 2D frame."""
    x, y, w, h = crop_rect
    if w <= 0 or h <= 0:
        return frame
    x0 = int(max(0, x))
    y0 = int(max(0, y))
    x1 = int(min(frame.shape[1], x + w))
    y1 = int(min(frame.shape[0], y + h))
    return frame[y0:y1, x0:x1]


def roi_mask_for_shape(
    shape: Tuple[int, int], roi_rect: Tuple[float, float, float, float], roi_shape: str
) -> np.ndarray:
    """Return a boolean ROI mask for the given shape and ROI spec."""
    h, w = shape
    y = np.arange(h)[:, None]
    x = np.arange(w)[None, :]
    rx, ry, rw, rh = roi_rect
    if roi_shape == "circle":
        cx, cy = rx + rw / 2, ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r**2
    return (rx <= x) & (x <= rx + rw) & (ry <= y) & (y <= ry + rh)


def map_point_to_crop(
    x: float, y: float, crop_rect: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Map a full-frame point into cropped coordinates."""
    cx, cy, _, _ = crop_rect
    return x - cx, y - cy


def roi_mask_for_polygon(
    shape: Tuple[int, int], points: Iterable[Tuple[float, float]]
) -> np.ndarray:
    """Return a polygon mask using matplotlib Path."""
    from matplotlib.path import Path

    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    coords = np.vstack((xx.ravel(), yy.ravel())).T
    poly = Path(list(points))
    mask = poly.contains_points(coords).reshape(h, w)
    return mask


def roi_mask_from_points(
    shape: Tuple[int, int],
    roi_type: str,
    points: Iterable[Tuple[float, float]],
) -> np.ndarray:
    """Create an ROI mask from a generic ROI definition."""
    pts = list(points)
    if roi_type == "circle" and len(pts) >= 2:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        r = float(np.hypot(x1 - x0, y1 - y0))
        h, w = shape
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        return (x - x0) ** 2 + (y - y0) ** 2 <= r**2
    if roi_type == "box" and len(pts) >= 2:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        x_min, x_max = sorted([x0, x1])
        y_min, y_max = sorted([y0, y1])
        h, w = shape
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        return (x >= x_min) & (x <= x_max) & (y >= y_min) & (y <= y_max)
    if roi_type in ("polygon", "polyline") and len(pts) >= 3:
        return roi_mask_for_polygon(shape, pts)
    return np.zeros(shape, dtype=bool)


def roi_mean_timeseries(
    arr: np.ndarray,
    roi_mask: np.ndarray,
) -> List[float]:
    """Compute ROI mean over time for a (T, Z, Y, X) array using Z=0."""
    means: List[float] = []
    for t in range(arr.shape[0]):
        frame = arr[t, 0, :, :]
        vals = frame[roi_mask]
        means.append(float(vals.mean()) if vals.size else float("nan"))
    return means


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
