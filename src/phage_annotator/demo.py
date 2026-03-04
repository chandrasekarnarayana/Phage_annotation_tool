"""Utilities to generate dummy microscopy images and run a quick demo."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import tifffile as tif

DummyMode = Literal["2d", "z", "t", "tz"]


def _add_gaussian_spots(
    data: np.ndarray,
    rng: np.random.Generator,
    n_spots: int = 100,
    sigma_range: tuple[float, float] = (3.0, 6.0),
    intensity_factor_range: tuple[float, float] = (1.2, 3.0),
) -> np.ndarray:
    """Add Gaussian spots to image data to simulate microscopy features.
    
    Parameters
    ----------
    data : np.ndarray
        Image data (can be 2D, 3D, or 4D)
    rng : np.random.Generator
        Random number generator
    n_spots : int
        Number of Gaussian spots to add
    sigma_range : tuple[float, float]
        Range of Gaussian sigma values in pixels
    intensity_factor_range : tuple[float, float]
        Range of peak intensity as multiple of mean intensity
    
    Returns
    -------
    np.ndarray
        Image data with Gaussian spots added
    """
    data = data.astype(np.float32)
    mean_intensity = np.mean(data)
    
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
        return data
    
    # Generate spot parameters
    n_frames = len(frames)
    for _ in range(n_spots):
        # Random position (with margin to avoid edges)
        margin = 20
        y = rng.integers(margin, h - margin)
        x = rng.integers(margin, w - margin)
        
        # Random sigma (width of Gaussian)
        sigma = rng.uniform(*sigma_range)
        
        # Random intensity factor
        intensity_factor = rng.uniform(*intensity_factor_range)
        peak_intensity = mean_intensity * intensity_factor
        
        # Randomly assign to a subset of frames (simulate moving or appearing particles)
        if n_frames > 1:
            # Spot appears in 20-80% of frames
            n_visible_frames = rng.integers(max(1, n_frames // 5), max(2, 4 * n_frames // 5))
            start_frame = rng.integers(0, max(1, n_frames - n_visible_frames))
            visible_frames = range(start_frame, start_frame + n_visible_frames)
        else:
            visible_frames = [0]
        
        # Create 2D Gaussian kernel
        kernel_size = int(sigma * 6)  # 6 sigma covers ~99.7% of Gaussian
        if kernel_size % 2 == 0:
            kernel_size += 1
        half = kernel_size // 2
        
        ky, kx = np.ogrid[-half:half+1, -half:half+1]
        gaussian = np.exp(-(kx**2 + ky**2) / (2 * sigma**2))
        gaussian = gaussian / gaussian.max() * peak_intensity
        
        # Add to frames
        for frame_idx in visible_frames:
            # Calculate region bounds
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
    
    return result


def generate_dummy_image(path: Path, mode: DummyMode = "tz") -> Path:
    """Create a dummy TIFF/OME-TIFF image on disk for testing or demo.

    The "t" mode produces a larger 20-frame 1200x1200 time stack with Gaussian spots
    simulating microscopy features (e.g., phage particles, fluorescent markers).
    """
    rng = np.random.default_rng(42)
    metadata = None
    if mode == "2d":
        data = rng.random((64, 64), dtype=np.float32)
        data = _add_gaussian_spots(data, rng, n_spots=10)
        metadata = {"axes": "YX"}
    elif mode == "z":
        data = rng.random((4, 64, 64), dtype=np.float32)  # (Z, Y, X)
        data = _add_gaussian_spots(data, rng, n_spots=20)
        metadata = {"axes": "ZYX"}
    elif mode == "t":
        # 16-bit-like range with offset: intensities in [100, 300].
        data = rng.integers(100, 301, size=(20, 1200, 1200), dtype=np.uint16).astype(np.float32)
        # Add Gaussian spots simulating phage particles or fluorescent features
        data = _add_gaussian_spots(data, rng, n_spots=100, sigma_range=(3.0, 6.0), intensity_factor_range=(1.2, 3.0))
        # Clip to valid range and convert back to uint16
        data = np.clip(data, 0, 65535).astype(np.uint16)
        metadata = {"axes": "TYX"}
    elif mode == "tz":
        data = rng.random((2, 3, 64, 64), dtype=np.float32)  # (T, Z, Y, X)
        data = _add_gaussian_spots(data, rng, n_spots=30)
        metadata = {"axes": "TZYX"}
    else:
        raise ValueError(f"Unknown dummy mode: {mode}")

    tif.imwrite(path, data, photometric="minisblack", metadata=metadata)
    return path


def run_demo(mode: DummyMode = "t") -> None:
    """Generate a dummy image and open it in the GUI."""
    from phage_annotator.ui_qt.main_window import run_gui
    
    tmp_path = Path.cwd() / f"phage_annotator_demo_{mode}.tif"
    path = generate_dummy_image(tmp_path, mode=mode)
    run_gui([path])
