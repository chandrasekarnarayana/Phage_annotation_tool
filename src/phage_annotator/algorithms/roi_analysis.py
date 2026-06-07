"""ROI masking, timeseries extraction, and bleach-curve fitting helpers."""

from __future__ import annotations

import logging
from typing import Iterable, List, Tuple

import numpy as np
import tifffile as tif
from scipy.optimize import curve_fit

from phage_annotator.io import standardize_axes

_logger = logging.getLogger(__name__)


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


def compute_roi_mean_for_path(
    path: str,
    roi_rect: Tuple[float, float, float, float],
    roi_shape: str,
    crop_rect: Tuple[float, float, float, float],
) -> float:
    """Load a TIFF and compute ROI mean on first frame."""
    arr = tif.imread(path, maxworkers=1)
    std, _, _ = standardize_axes(arr)
    frame = std[0, 0, :, :]
    frame_cropped = apply_crop_rect(frame, crop_rect)
    roi_mask = roi_mask_for_shape(frame_cropped.shape, roi_rect, roi_shape)
    vals = frame_cropped[roi_mask]
    return float(vals.mean()) if vals.size else float("nan")


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
        """Run the exp decay workflow."""
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


def map_point_to_crop(
    x: float, y: float, crop_rect: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Map a full-frame point into cropped coordinates."""
    cx, cy, _, _ = crop_rect
    return x - cx, y - cy


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
