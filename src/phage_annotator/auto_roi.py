"""Auto ROI proposal for uniform, artifact-free regions."""

from __future__ import annotations

from typing import Dict, Literal, Optional, Tuple

import numpy as np

from phage_annotator.session_state import RoiSpec


def propose_roi(
    image2d: np.ndarray,
    *,
    shape: Literal["box", "circle", "auto"] = "box",
    request_w: Optional[int] = None,
    request_h: Optional[int] = None,
    request_area: Optional[int] = None,
    min_side: int = 100,
    max_circle_radius: int = 300,
    max_area: Optional[int] = None,
    use_mean_projection_hint: bool = True,
    stride: Optional[int] = None,
    bg_sigma: float = 30.0,
    p_low: float = 1.0,
    p_high: float = 99.5,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[RoiSpec, Dict[str, float]]:
    """Propose a ROI location with uniform illumination and minimal artifacts.

    Parameters
    ----------
    image2d : np.ndarray
        2D image slice in full-resolution pixel coordinates.
    shape : {"box", "circle", "auto"}, optional
        ROI shape to propose. "auto" currently defaults to box.
    request_w, request_h : int, optional
        Requested width/height in pixels for box ROIs.
    request_area : int, optional
        Requested ROI area in pixels (used for box or circle).
    min_side : int, optional
        Minimum ROI side length in pixels.
    max_circle_radius : int, optional
        Maximum circle radius in pixels.
    max_area : int, optional
        Maximum ROI area in pixels. Defaults to circle area with max radius.
    use_mean_projection_hint : bool, optional
        Reserved hint for future projection-based scoring.
    stride : int, optional
        Step size for candidate window sampling; auto-derived if None.
    bg_sigma : float, optional
        Gaussian sigma for background smoothing.
    p_low, p_high : float, optional
        Percentiles used to define low/high outliers.
    weights : dict, optional
        Scoring weights for {"var","grad","low","high"}.

    Returns
    -------
    RoiSpec
        ROI specification in full-resolution coordinates.
    dict
        Diagnostics with score components.
    """
    _ = use_mean_projection_hint
    img = np.asarray(image2d, dtype=np.float32)
    if img.ndim != 2:
        raise ValueError("propose_roi expects a 2D array.")
    if np.isnan(img).any():
        med = np.nanmedian(img)
        img = np.nan_to_num(img, nan=float(med))

    h, w = img.shape
    max_area = int(max_area) if max_area is not None else int(np.pi * max_circle_radius**2)
    shape = "box" if shape == "auto" else shape

    req_w = request_w if request_w is not None else request_h
    req_h = request_h if request_h is not None else request_w
    if request_area is not None and (req_w is None or req_h is None):
        side = int(np.sqrt(max(1.0, float(request_area))))
        req_w = side
        req_h = side
    req_w = req_w if req_w is not None else min_side
    req_h = req_h if req_h is not None else min_side

    if shape == "circle":
        if request_area is not None:
            radius = int(np.sqrt(max(1.0, float(request_area)) / np.pi))
        else:
            radius = int(min(req_w, req_h) / 2)
        radius = max(1, min(max_circle_radius, radius))
        if max_area is not None:
            radius = min(radius, int(np.sqrt(max_area / np.pi)))
        req_w = req_h = radius * 2
    else:
        if max_area is not None and req_w * req_h > max_area:
            side = int(np.sqrt(max_area))
            req_w = min(req_w, side)
            req_h = min(req_h, side)
        if request_w is None and request_h is None:
            side = max(min_side, min(req_w, req_h))
            req_w = req_h = side

    req_w = int(max(1, min(req_w, w)))
    req_h = int(max(1, min(req_h, h)))
    if req_w < min_side and w >= min_side:
        req_w = min_side
    if req_h < min_side and h >= min_side:
        req_h = min_side

    stride = stride or max(8, min(req_w, req_h) // 8)
    stride = max(1, int(stride))

    bg = _gaussian_blur(img, bg_sigma) if bg_sigma > 0 else img
    flat = img - bg
    low_thr, high_thr = _percentile_bounds(img, p_low, p_high)
    low_mask = img < low_thr
    high_mask = img > high_thr

    gy, gx = np.gradient(bg)
    grad = np.hypot(gx, gy)

    ii_f = _integral(flat)
    ii_f2 = _integral(flat * flat)
    ii_g = _integral(grad)
    ii_low = _integral(low_mask.astype(np.float32))
    ii_high = _integral(high_mask.astype(np.float32))

    y0s = np.arange(0, max(1, h - req_h + 1), stride)
    x0s = np.arange(0, max(1, w - req_w + 1), stride)
    if y0s.size == 0 or x0s.size == 0:
        y0s = np.array([max(0, (h - req_h) // 2)])
        x0s = np.array([max(0, (w - req_w) // 2)])
    yy, xx = np.meshgrid(y0s, x0s, indexing="ij")
    area = float(req_w * req_h)

    sum_f = _window_sum(ii_f, yy, xx, req_h, req_w)
    sum_f2 = _window_sum(ii_f2, yy, xx, req_h, req_w)
    sum_g = _window_sum(ii_g, yy, xx, req_h, req_w)
    sum_low = _window_sum(ii_low, yy, xx, req_h, req_w)
    sum_high = _window_sum(ii_high, yy, xx, req_h, req_w)

    mean_f = sum_f / area
    var_f = np.maximum(0.0, sum_f2 / area - mean_f * mean_f)
    grad_mean = sum_g / area
    low_frac = sum_low / area
    high_frac = sum_high / area

    wts = {"var": 1.0, "grad": 1.0, "low": 2.0, "high": 2.0, "edge": 0.25}
    if weights:
        wts.update(weights)
    var_norm = var_f / (np.median(var_f) + 1e-6)
    grad_norm = grad_mean / (np.median(grad_mean) + 1e-6)
    cx = xx + req_w / 2.0
    cy = yy + req_h / 2.0
    norm = max(h, w)
    edge_penalty = np.hypot(cx - w / 2.0, cy - h / 2.0) / max(1.0, norm)
    score = (
        wts["var"] * var_norm
        + wts["grad"] * grad_norm
        + wts["low"] * low_frac
        + wts["high"] * high_frac
        + wts["edge"] * edge_penalty
    )
    best_idx = np.unravel_index(np.argmin(score), score.shape)
    y0 = int(y0s[best_idx[0]])
    x0 = int(x0s[best_idx[1]])

    if shape == "circle":
        radius = req_w // 2
        cx = x0 + radius
        cy = y0 + radius
        cx = int(np.clip(cx, radius, max(radius, w - radius)))
        cy = int(np.clip(cy, radius, max(radius, h - radius)))
        rect = (float(cx - radius), float(cy - radius), float(radius * 2), float(radius * 2))
        roi_shape = "circle"
    else:
        rect = (float(x0), float(y0), float(req_w), float(req_h))
        roi_shape = "box"

    spec = RoiSpec()
    spec.rect = rect
    spec.shape = roi_shape

    diagnostics = {
        "score": float(score[best_idx]),
        "var": float(var_f[best_idx]),
        "grad": float(grad_mean[best_idx]),
        "low_frac": float(low_frac[best_idx]),
        "high_frac": float(high_frac[best_idx]),
        "stride": float(stride),
        "x": float(x0),
        "y": float(y0),
        "w": float(req_w),
        "h": float(req_h),
    }
    return spec, diagnostics


def _percentile_bounds(image: np.ndarray, p_low: float, p_high: float) -> Tuple[float, float]:
    sample = image
    if image.size > 200_000:
        stride = int(np.sqrt(image.size / 200_000))
        stride = max(1, stride)
        sample = image[::stride, ::stride]
    low = float(np.nanpercentile(sample, p_low))
    high = float(np.nanpercentile(sample, p_high))
    return low, high


def _integral(image: np.ndarray) -> np.ndarray:
    padded = np.pad(image, ((1, 0), (1, 0)), mode="constant", constant_values=0.0)
    return padded.cumsum(axis=0).cumsum(axis=1)


def _window_sum(ii: np.ndarray, y0: np.ndarray, x0: np.ndarray, h: int, w: int) -> np.ndarray:
    y1 = y0 + h
    x1 = x0 + w
    return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]


def _gaussian_blur(image: np.ndarray, sigma: float) -> np.ndarray:
    try:
        from scipy.ndimage import gaussian_filter
    except Exception:
        return _gaussian_blur_np(image, sigma)
    return gaussian_filter(image, sigma=float(sigma), mode="reflect")


def _gaussian_blur_np(image: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return image
    radius = int(max(1, sigma * 3))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-(x**2) / (2 * sigma**2))
    kernel /= kernel.sum()
    padded = np.pad(image, ((radius, radius), (radius, radius)), mode="reflect")
    tmp = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="valid"), 0, padded)
    blurred = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="valid"), 1, tmp)
    return blurred.astype(np.float32, copy=False)
