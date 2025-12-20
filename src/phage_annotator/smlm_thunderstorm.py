"""Classical SMLM localization pipeline inspired by ThunderSTORM.

This module provides pure, non-Qt helpers for ROI-scoped localization over
streamed frames. It implements a simple filter/detect/localize/post-filter
pipeline and reconstructs a super-resolution (SR) image.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter, convolve1d

from phage_annotator.analysis import fit_gaussian_2d, local_maxima, mad_sigma


@dataclass(frozen=True)
class SmlmParams:
    """Parameters for the ThunderSTORM-style localization pipeline."""

    sigma_px: float = 1.3
    fit_radius_px: int = 4
    filter_type: str = "wavelet_bspline"
    dog_sigma1: float = 1.0
    dog_sigma2: float = 2.0
    detection_thr_sigma: float = 3.0
    max_candidates_per_frame: int = 5000
    merge_radius_px: float = 1.0
    min_photons: float = 50.0
    max_uncertainty_nm: float = 30.0
    uncertainty_px: float = 0.25
    upsample: int = 8
    render_mode: str = "histogram"
    render_sigma_nm: float = 10.0


@dataclass(frozen=True)
class Localization:
    """Localization record for a single detection."""

    frame_index: int
    x_px: float
    y_px: float
    sigma_px: float
    photons: float
    background: float
    uncertainty_px: float
    label: Optional[str] = None


def filter_frame(frame: np.ndarray, params: SmlmParams) -> np.ndarray:
    """Apply a band-pass filter to enhance spots."""
    frame_f = frame.astype(np.float32, copy=False)
    if params.filter_type == "dog":
        return gaussian_filter(frame_f, params.dog_sigma1) - gaussian_filter(frame_f, params.dog_sigma2)
    smooth = _bspline_smooth(frame_f)
    return frame_f - smooth


def detect_candidates(filtered: np.ndarray, roi_mask: Optional[np.ndarray], params: SmlmParams) -> np.ndarray:
    """Detect candidate peaks using local maxima and robust thresholding."""
    masked = filtered
    if roi_mask is not None:
        masked = filtered.copy()
        masked[~roi_mask] = -np.inf
    finite = masked[np.isfinite(masked)]
    if finite.size == 0:
        return np.empty((0, 2), dtype=int)
    threshold = np.median(finite) + params.detection_thr_sigma * mad_sigma(finite)
    coords = local_maxima(masked, threshold, footprint=3)
    if coords.size == 0:
        return coords
    if coords.shape[0] > params.max_candidates_per_frame:
        values = masked[coords[:, 0], coords[:, 1]]
        order = np.argsort(values)[::-1][: params.max_candidates_per_frame]
        coords = coords[order]
    return coords


def localize_candidates(
    frame: np.ndarray, coords: np.ndarray, params: SmlmParams, offset: Tuple[int, int]
) -> List[Localization]:
    """Refine candidate locations using 2D Gaussian fitting."""
    locs: List[Localization] = []
    if coords.size == 0:
        return locs
    rad = int(max(1, params.fit_radius_px))
    h, w = frame.shape
    off_x, off_y = offset
    for y, x in coords:
        x0 = max(0, x - rad)
        x1 = min(w, x + rad + 1)
        y0 = max(0, y - rad)
        y1 = min(h, y + rad + 1)
        patch = frame[y0:y1, x0:x1]
        if patch.size < 9:
            continue
        try:
            amp, fx, fy, sigma, offset_bg, cov = fit_gaussian_2d(patch)
        except ValueError:
            continue
        if sigma <= 0:
            continue
        photons = float(max(0.0, amp) * 2.0 * np.pi * sigma ** 2)
        if photons <= 0:
            continue
        if cov is not None and cov.shape[0] >= 3:
            unc = float(np.sqrt(max(cov[1, 1], 0.0) + max(cov[2, 2], 0.0)) / 2.0)
        else:
            unc = float(sigma / np.sqrt(max(photons, 1.0)))
        locs.append(
            Localization(
                frame_index=-1,
                x_px=float(x0 + fx + off_x),
                y_px=float(y0 + fy + off_y),
                sigma_px=float(sigma),
                photons=float(photons),
                background=float(offset_bg),
                uncertainty_px=float(unc),
            )
        )
    return locs


def post_filter(
    locs: Sequence[Localization],
    params: SmlmParams,
    pixel_size_nm: Optional[float],
) -> List[Localization]:
    """Apply uncertainty/brightness filtering and merge close detections."""
    filtered: List[Localization] = []
    for loc in locs:
        if loc.photons < params.min_photons:
            continue
        if pixel_size_nm is not None:
            if loc.uncertainty_px * pixel_size_nm > params.max_uncertainty_nm:
                continue
        else:
            if loc.uncertainty_px > params.uncertainty_px:
                continue
        filtered.append(loc)
    return merge_localizations(filtered, params.merge_radius_px)


def merge_localizations(locs: Sequence[Localization], radius_px: float) -> List[Localization]:
    """Greedy merge of close localizations within the same frame."""
    if radius_px <= 0 or not locs:
        return list(locs)
    remaining = sorted(locs, key=lambda l: l.photons, reverse=True)
    merged: List[Localization] = []
    r2 = float(radius_px) ** 2
    while remaining:
        seed = remaining.pop(0)
        merged.append(seed)
        kept = []
        for loc in remaining:
            if (loc.x_px - seed.x_px) ** 2 + (loc.y_px - seed.y_px) ** 2 > r2:
                kept.append(loc)
        remaining = kept
    return merged


def render_sr_image(
    locs: Sequence[Localization],
    roi_rect: Tuple[float, float, float, float],
    upsample: int,
    pixel_size_nm: Optional[float],
    render_mode: str,
    render_sigma_nm: float,
) -> np.ndarray:
    """Render a super-resolution image for the ROI region."""
    rx, ry, rw, rh = roi_rect
    w = max(1, int(round(rw)))
    h = max(1, int(round(rh)))
    scale = max(1, int(upsample))
    sr = np.zeros((h * scale, w * scale), dtype=np.float32)
    if not locs:
        return sr
    if pixel_size_nm is None or pixel_size_nm <= 0:
        sigma_sr = render_sigma_nm
    else:
        sigma_sr = render_sigma_nm / pixel_size_nm
    sigma_sr *= scale
    radius = int(max(1, round(3 * sigma_sr)))
    for loc in locs:
        x = (loc.x_px - rx) * scale
        y = (loc.y_px - ry) * scale
        if x < 0 or y < 0 or x >= sr.shape[1] or y >= sr.shape[0]:
            continue
        if render_mode == "histogram":
            xi = int(round(x))
            yi = int(round(y))
            if 0 <= xi < sr.shape[1] and 0 <= yi < sr.shape[0]:
                sr[yi, xi] += 1.0
            continue
        x0 = int(max(0, x - radius))
        x1 = int(min(sr.shape[1], x + radius + 1))
        y0 = int(max(0, y - radius))
        y1 = int(min(sr.shape[0], y + radius + 1))
        yy, xx = np.mgrid[y0:y1, x0:x1]
        gauss = np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma_sr ** 2)))
        sr[y0:y1, x0:x1] += gauss.astype(np.float32, copy=False)
    return sr


def run_smlm_stream(
    frames: Iterable[Tuple[int, np.ndarray]],
    total_frames: int,
    roi_mask: Optional[np.ndarray],
    roi_rect: Tuple[float, float, float, float],
    crop_offset: Tuple[int, int],
    params: SmlmParams,
    pixel_size_nm: Optional[float] = None,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Tuple[List[Localization], np.ndarray]:
    """Run the SMLM pipeline over a frame stream."""
    all_locs: List[Localization] = []
    if total_frames <= 0:
        return all_locs, np.zeros((1, 1), dtype=np.float32)
    for idx, frame in frames:
        if is_cancelled is not None and is_cancelled():
            break
        filt = filter_frame(frame, params)
        coords = detect_candidates(filt, roi_mask, params)
        locs = localize_candidates(frame, coords, params, crop_offset)
        locs = [
            Localization(
                frame_index=idx,
                x_px=loc.x_px,
                y_px=loc.y_px,
                sigma_px=loc.sigma_px,
                photons=loc.photons,
                background=loc.background,
                uncertainty_px=loc.uncertainty_px,
                label=loc.label,
            )
            for loc in locs
        ]
        locs = post_filter(locs, params, pixel_size_nm)
        all_locs.extend(locs)
        if progress_cb is not None:
            progress = int((idx + 1) / total_frames * 100)
            progress_cb(progress, f"Frames {idx + 1}/{total_frames}")
    sr = render_sr_image(all_locs, roi_rect, params.upsample, pixel_size_nm, params.render_mode, params.render_sigma_nm)
    return all_locs, sr


def _bspline_smooth(frame: np.ndarray) -> np.ndarray:
    """Apply a separable B-spline-like smoothing kernel."""
    kernel = np.array([1, 4, 6, 4, 1], dtype=np.float32) / 16.0
    temp = convolve1d(frame, kernel, axis=0, mode="nearest")
    return convolve1d(temp, kernel, axis=1, mode="nearest")
