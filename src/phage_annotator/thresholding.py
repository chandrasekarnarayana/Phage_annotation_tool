"""Thresholding helpers for Fiji-style preview and masks (no Qt)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:  # Optional dependencies
    from skimage import filters as sk_filters
    from skimage import morphology as sk_morph
except Exception:  # pragma: no cover - optional import
    sk_filters = None
    sk_morph = None

try:  # Optional dependency
    from scipy import ndimage as ndi
except Exception:  # pragma: no cover - optional import
    ndi = None


AUTO_METHODS = [
    "Otsu",
    "Yen",
    "Li",
    "Triangle",
    "IsoData",
    "Minimum",
    "Mean",
    "Moments",
    "RenyiEntropy",
    "Percentile",
    "Intermodes",
]


@dataclass(frozen=True)
class PostprocessOptions:
    """Post-processing parameters for binary masks."""

    min_area_px: int = 5
    fill_holes: bool = False
    open_radius_px: int = 1
    close_radius_px: int = 1
    invert: bool = False
    despeckle: bool = False
    watershed_split: bool = False


def compute_threshold(pixels: np.ndarray, method: str, *, background: str = "dark") -> float:
    """Compute a scalar threshold value for the given pixels."""
    data = np.asarray(pixels).astype(np.float32, copy=False)
    if data.size == 0:
        return float("nan")
    if background == "bright":
        max_val = float(np.max(data))
        data = max_val - data
    if method.lower() == "mean":
        return float(np.mean(data))
    if method.lower() == "manual":
        return float("nan")
    if sk_filters is None:
        if method.lower() == "otsu":
            return _otsu_threshold(data)
        return float("nan")
    fn = _skimage_threshold_fn(method)
    if fn is None:
        return float("nan")
    return float(fn(data))


def make_mask(
    image2d: np.ndarray,
    thr_low: float,
    thr_high: Optional[float] = None,
    invert: bool = False,
) -> np.ndarray:
    """Create a binary mask from a 2D image using low/high thresholds."""
    data = np.asarray(image2d)
    if thr_high is None or np.isnan(thr_high):
        mask = data >= thr_low
    else:
        mask = (data >= thr_low) & (data <= thr_high)
    if invert:
        mask = ~mask
    return mask


def postprocess_mask(mask: np.ndarray, opts: PostprocessOptions) -> np.ndarray:
    """Apply optional post-processing to a binary mask."""
    out = mask.astype(bool, copy=False)
    if opts.invert:
        out = ~out
    if opts.despeckle and opts.min_area_px > 0:
        out = remove_small_objects(out, opts.min_area_px)
    if opts.fill_holes:
        out = fill_holes(out)
    if opts.open_radius_px > 0:
        out = binary_open(out, opts.open_radius_px)
    if opts.close_radius_px > 0:
        out = binary_close(out, opts.close_radius_px)
    if opts.watershed_split:
        out = watershed_split(out)
    return out


def remove_small_objects(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Remove connected components smaller than min_area."""
    if min_area <= 0:
        return mask
    if sk_morph is not None:
        return sk_morph.remove_small_objects(mask, min_size=min_area)
    if ndi is None:
        return mask
    labeled, num = ndi.label(mask)
    if num == 0:
        return mask
    counts = np.bincount(labeled.ravel())
    keep = counts >= min_area
    keep[0] = False
    return keep[labeled]


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill holes in a binary mask."""
    if sk_morph is not None:
        return sk_morph.remove_small_holes(mask, area_threshold=16)
    if ndi is None:
        return mask
    return ndi.binary_fill_holes(mask)


def binary_open(mask: np.ndarray, radius: int) -> np.ndarray:
    """Binary opening with a disk footprint."""
    if radius <= 0:
        return mask
    if sk_morph is not None:
        return sk_morph.binary_opening(mask, sk_morph.disk(radius))
    if ndi is None:
        return mask
    return ndi.binary_opening(mask, structure=_disk(radius))


def binary_close(mask: np.ndarray, radius: int) -> np.ndarray:
    """Binary closing with a disk footprint."""
    if radius <= 0:
        return mask
    if sk_morph is not None:
        return sk_morph.binary_closing(mask, sk_morph.disk(radius))
    if ndi is None:
        return mask
    return ndi.binary_closing(mask, structure=_disk(radius))


def smooth_image(image2d: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing for threshold preview."""
    if sigma <= 0:
        return image2d
    if ndi is not None:
        return ndi.gaussian_filter(image2d, sigma=float(sigma))
    return image2d


def watershed_split(mask: np.ndarray) -> np.ndarray:
    """Split touching blobs using distance-transform watershed."""
    if mask.size == 0:
        return mask
    if sk_filters is None or sk_morph is None:
        return mask
    dist = sk_morph.distance_transform_edt(mask)
    if dist.max() <= 0:
        return mask
    markers = sk_morph.label(dist > np.percentile(dist[dist > 0], 70))
    if markers.max() == 0:
        return mask
    try:
        from skimage.segmentation import watershed
    except Exception:
        return mask
    labels = watershed(-dist, markers, mask=mask)
    return labels > 0


def _skimage_threshold_fn(name: str):
    if sk_filters is None:
        return None
    mapping = {
        "otsu": sk_filters.threshold_otsu,
        "yen": sk_filters.threshold_yen,
        "li": sk_filters.threshold_li,
        "triangle": sk_filters.threshold_triangle,
        "isodata": sk_filters.threshold_isodata,
        "minimum": sk_filters.threshold_minimum,
        "mean": sk_filters.threshold_mean,
        "moments": sk_filters.threshold_moments,
        "renyientropy": sk_filters.threshold_renyi_entropy,
        "percentile": sk_filters.threshold_percentile,
        "intermodes": sk_filters.threshold_intermodes,
    }
    return mapping.get(name.lower())


def _otsu_threshold(data: np.ndarray) -> float:
    hist, bin_edges = np.histogram(data.ravel(), bins=256)
    hist = hist.astype(np.float64)
    prob = hist / hist.sum()
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * np.arange(len(hist)))
    mu_t = mu[-1]
    sigma_b = (mu_t * omega - mu) ** 2 / (omega * (1 - omega) + 1e-12)
    idx = int(np.argmax(sigma_b))
    return float(bin_edges[idx])


def _disk(radius: int) -> np.ndarray:
    r = int(max(1, radius))
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    return (x * x + y * y) <= r * r
