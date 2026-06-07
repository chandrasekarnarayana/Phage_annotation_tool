"""Split definitions from demo_image_generators.py."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

import numpy as np

DummyMode = Literal["2d", "z", "t", "tz"]


def _add_gaussian_spots(
    data: np.ndarray,
    rng: np.random.Generator,
    n_spots: int = 100,
    sigma_range: tuple[float, float] = (3.0, 6.0),
    intensity_factor_range: tuple[float, float] = (1.2, 3.0),
    min_spot_distance: float = 3.0,
    min_frames: int = 10,
) -> tuple[np.ndarray, list[dict]]:
    """Add Gaussian spots to image data to simulate microscopy features.

    Each spot is a unique location that persists for at least min_frames consecutive frames,
    with slightly varying coordinates and sigma across frames to simulate real microscopy data.

    Parameters
    ----------
    data : np.ndarray
        Image data (can be 2D, 3D, or 4D)
    rng : np.random.Generator
        Random number generator
    n_spots : int
        Number of unique spot locations to add (not total annotations)
    sigma_range : tuple[float, float]
        Range of Gaussian sigma values in pixels
    intensity_factor_range : tuple[float, float]
        Range of peak intensity as multiple of mean intensity
    min_spot_distance : float
        Minimum distance between spot locations in pixels (default 3.0)
    min_frames : int
        Minimum number of consecutive frames each spot persists in (default 10)

    Returns
    -------
    tuple[np.ndarray, list[dict]]
        Image data with Gaussian spots added, and list of spot annotations
        Each annotation includes spot_id to identify the unique location
    """
    data = data.astype(np.float32)
    mean_intensity = np.mean(data)
    spots = []

    # Handle different dimensionalities
    if data.ndim == 2:
        # 2D image
        frames = [data]
        h, w = data.shape
    elif data.ndim == 3:
        # 3D stack (T or Z, Y, X)
        frames = [data[i] for i in range(data.shape[0])]
        h, w = data.shape[1], data.shape[2]
    elif data.ndim == 4:
        # 4D stack (T, Z, Y, X)
        frames = [data[t, z] for t in range(data.shape[0]) for z in range(data.shape[1])]
        h, w = data.shape[2], data.shape[3]
    else:
        return data, []

    n_frames = len(frames)
    margin = 20

    # Step 1: Generate unique spot locations with minimum distance constraint
    spot_locations = []
    attempts = 0
    max_attempts = n_spots * 100

    while len(spot_locations) < n_spots and attempts < max_attempts:
        attempts += 1
        y = rng.integers(margin, h - margin)
        x = rng.integers(margin, w - margin)

        # Check if this location is far enough from existing spots
        too_close = False
        for existing_y, existing_x in spot_locations:
            dist = np.sqrt((y - existing_y)**2 + (x - existing_x)**2)
            if dist < min_spot_distance:
                too_close = True
                break

        if not too_close:
            spot_locations.append((y, x))

    # Step 2: For each unique location, add it to frames with variations
    for spot_idx, (base_y, base_x) in enumerate(spot_locations):
        # Generate fixed parameters for this spot
        base_sigma = rng.uniform(*sigma_range)
        intensity_factor = rng.uniform(*intensity_factor_range)
        peak_intensity = mean_intensity * intensity_factor

        # Determine how many consecutive frames (minimum min_frames, variable up to n_frames)
        if n_frames >= min_frames:
            # Pick random number of frames: at least min_frames, up to n_frames
            n_visible_frames = rng.integers(min_frames, n_frames + 1)
            # Pick random start frame where n_visible_frames fit within total frames
            max_start = n_frames - n_visible_frames
            start_frame = rng.integers(0, max(1, max_start + 1))
            visible_frames = range(start_frame, start_frame + n_visible_frames)
        else:
            # If fewer total frames than min_frames, use all frames
            visible_frames = range(0, n_frames)

        # Add spot to each frame with slight variations in position and sigma
        for frame_idx in visible_frames:
            # Vary position slightly (Brownian motion-like drift)
            y = base_y + rng.normal(0, 0.5)
            x = base_x + rng.normal(0, 0.5)
            y = int(np.clip(y, margin, h - margin - 1))
            x = int(np.clip(x, margin, w - margin - 1))

            # Vary sigma slightly
            sigma = base_sigma + rng.normal(0, 0.2)
            sigma = max(1.0, sigma)

            # Create 2D Gaussian kernel
            kernel_size = int(sigma * 6)  # 6 sigma covers ~99.7% of Gaussian
            if kernel_size % 2 == 0:
                kernel_size += 1
            half = kernel_size // 2

            ky, kx = np.ogrid[-half:half+1, -half:half+1]
            gaussian = np.exp(-(kx**2 + ky**2) / (2 * sigma**2))
            gaussian = gaussian / gaussian.max() * peak_intensity

            # Add to frame with boundary checking
            y_start = max(0, y - half)
            y_end = min(h, y + half + 1)
            x_start = max(0, x - half)
            x_end = min(w, x + half + 1)

            # Calculate kernel bounds (in case spot is near edge)
            ky_start = half - (y - y_start)
            ky_end = half + (y_end - y)
            kx_start = half - (x - x_start)
            kx_end = half + (x_end - x)

            # Add Gaussian spot
            frames[frame_idx][y_start:y_end, x_start:x_end] += gaussian[ky_start:ky_end, kx_start:kx_end]

            # Record spot annotation with spot_id to link to unique location
            if data.ndim == 4:
                t = frame_idx // data.shape[1]
                z = frame_idx % data.shape[1]
                spots.append({
                    't': int(t),
                    'z': int(z),
                    'y': int(y),
                    'x': int(x),
                    'sigma': float(sigma),
                    'intensity': float(peak_intensity),
                    'spot_id': int(spot_idx),
                })
            elif data.ndim == 3:
                spots.append({
                    'timepoint': int(frame_idx),
                    'y': int(y),
                    'x': int(x),
                    'sigma': float(sigma),
                    'intensity': float(peak_intensity),
                    'spot_id': int(spot_idx),
                })
            else:
                spots.append({
                    'y': int(y),
                    'x': int(x),
                    'sigma': float(sigma),
                    'intensity': float(peak_intensity),
                    'spot_id': int(spot_idx),
                })

    # Reconstruct data array
    if data.ndim == 2:
        result = frames[0]
    elif data.ndim == 3:
        result = np.stack(frames, axis=0)
    elif data.ndim == 4:
        result = np.zeros_like(data)
        idx = 0
        for t in range(data.shape[0]):
            for z in range(data.shape[1]):
                result[t, z] = frames[idx]
                idx += 1
    else:
        result = data

    return result, spots

def _add_realistic_noise(
    data: np.ndarray,
    rng: np.random.Generator,
    *,
    shot_noise_strength: float = 1.0,
    stray_pixel_fraction: float = 2e-5,
    stray_intensity_factor_range: tuple[float, float] = (3.0, 8.0),
) -> np.ndarray:
    """Add microscopy-like shot noise and sparse hot pixels.

    Parameters
    ----------
    data : np.ndarray
        Input image stack.
    rng : np.random.Generator
        Random generator.
    shot_noise_strength : float
        0 disables shot noise; 1.0 applies full Poisson perturbation.
    stray_pixel_fraction : float
        Fraction of all pixels turned into sparse hot pixels.
    stray_intensity_factor_range : tuple[float, float]
        Multiplicative range (relative to robust local scale) for hot pixels.
    """
    arr = data.astype(np.float32, copy=True)

    if shot_noise_strength > 0:
        lam = np.clip(arr, 0.0, None)
        poisson = rng.poisson(lam).astype(np.float32)
        mix = float(np.clip(shot_noise_strength, 0.0, 1.0))
        arr = (1.0 - mix) * arr + mix * poisson

    if stray_pixel_fraction > 0:
        total = int(arr.size)
        n_hot = int(max(1, round(total * float(stray_pixel_fraction))))
        robust_scale = float(np.percentile(arr, 99.5) - np.percentile(arr, 50.0))
        robust_scale = max(1.0, robust_scale)

        flat = arr.reshape(-1)
        idx = rng.choice(flat.size, size=min(n_hot, flat.size), replace=False)
        hot_amp = rng.uniform(
            stray_intensity_factor_range[0] * robust_scale,
            stray_intensity_factor_range[1] * robust_scale,
            size=idx.size,
        ).astype(np.float32)
        flat[idx] += hot_amp

    return arr
