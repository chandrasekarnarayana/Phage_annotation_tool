"""Utilities to generate dummy microscopy images and run a quick demo."""

from __future__ import annotations

import csv
import time
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


def generate_dummy_image(
    path: Path, 
    mode: DummyMode = "tz",
    n_spots: int | None = None,
    seed: int | None = None,
    shot_noise_strength: float = 1.0,
    stray_pixel_fraction: float = 2e-5,
) -> DummyImageArtifacts:
    """Create a dummy TIFF/OME-TIFF image on disk for testing or demo.

    The "t" mode produces a larger 20-frame 1200x1200 time stack with Gaussian spots
    simulating microscopy features (e.g., phage particles, fluorescent markers).
    
    Parameters
    ----------
    path : Path
        Output path for the TIFF image
    mode : DummyMode
        Image dimensionality: "2d", "z", "t", or "tz"
    n_spots : int | None
        Number of spots to generate. If None, randomly chooses between 50-300.
    seed : int | None
        Random seed for reproducibility. If None, uses current system time.
    shot_noise_strength : float
        Strength of Poisson shot noise. 0 disables; 1 applies full noise.
    stray_pixel_fraction : float
        Fraction of sparse stray/hot pixels to inject for realism.
    
    Returns
    -------
    DummyImageArtifacts
        Tuple-like wrapper of (image_path, annotation_csv_path) that also acts
        like the image path for backward compatibility.
    """
    # Use system time as seed if not provided
    if seed is None:
        seed = int(time.time() * 1000000) % (2**31)
    
    # Random spot count if not provided
    if n_spots is None:
        rng_count = np.random.default_rng(seed)
        n_spots = rng_count.integers(50, 301)
    else:
        n_spots = max(1, min(n_spots, 1000))  # Clamp to reasonable range
    
    rng = np.random.default_rng(seed)
    metadata = None
    all_spots = []
    
    if mode == "2d":
        data = rng.random((64, 64), dtype=np.float32)
        data, spots = _add_gaussian_spots(data, rng, n_spots=n_spots)
        data = _add_realistic_noise(
            data,
            rng,
            shot_noise_strength=shot_noise_strength,
            stray_pixel_fraction=stray_pixel_fraction,
        )
        metadata = {"axes": "YX"}
        all_spots = spots
    elif mode == "z":
        data = rng.random((4, 64, 64), dtype=np.float32)  # (Z, Y, X)
        data, spots = _add_gaussian_spots(data, rng, n_spots=n_spots)
        data = _add_realistic_noise(
            data,
            rng,
            shot_noise_strength=shot_noise_strength,
            stray_pixel_fraction=stray_pixel_fraction,
        )
        metadata = {"axes": "ZYX"}
        all_spots = spots
    elif mode == "t":
        # 16-bit-like range with offset: intensities in [100, 300].
        data = rng.integers(100, 301, size=(20, 1200, 1200), dtype=np.uint16).astype(np.float32)
        # Add Gaussian spots simulating phage particles or fluorescent features
        data, spots = _add_gaussian_spots(data, rng, n_spots=n_spots, sigma_range=(3.0, 6.0), intensity_factor_range=(1.2, 3.0))
        data = _add_realistic_noise(
            data,
            rng,
            shot_noise_strength=shot_noise_strength,
            stray_pixel_fraction=stray_pixel_fraction,
        )
        # Clip to valid range and convert back to uint16
        data = np.clip(data, 0, 65535).astype(np.uint16)
        metadata = {"axes": "TYX"}
        all_spots = spots
    elif mode == "tz":
        data = rng.random((2, 3, 64, 64), dtype=np.float32)  # (T, Z, Y, X)
        data, spots = _add_gaussian_spots(data, rng, n_spots=n_spots)
        data = _add_realistic_noise(
            data,
            rng,
            shot_noise_strength=shot_noise_strength,
            stray_pixel_fraction=stray_pixel_fraction,
        )
        metadata = {"axes": "TZYX"}
        all_spots = spots
    else:
        raise ValueError(f"Unknown dummy mode: {mode}")

    tif.imwrite(path, data, photometric="minisblack", metadata=metadata)
    
    # Generate annotation CSV
    csv_path = path.with_suffix('.csv')
    with open(csv_path, 'w', newline='') as f:
        if all_spots:
            fieldnames = list(all_spots[0].keys())
        else:
            fieldnames = ['y', 'x', 'sigma', 'intensity']
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_spots)
    
    return DummyImageArtifacts(path, csv_path)


def run_demo(
    mode: DummyMode = "t",
    n_spots: int | None = None,
    seed: int | None = None,
    shot_noise_strength: float = 1.0,
    stray_pixel_fraction: float = 2e-5,
) -> None:
    """Generate a dummy image and open it in the GUI.
    
    Parameters
    ----------
    mode : DummyMode
        Image dimensionality: "2d", "z", "t", or "tz"
    n_spots : int | None
        Number of spots to generate. If None, randomly chooses between 50-300.
    seed : int | None
        Random seed for reproducibility. If None, uses current system time.
    shot_noise_strength : float
        Strength of Poisson shot noise (0..1+).
    stray_pixel_fraction : float
        Fraction of sparse hot pixels to inject.
    """
    from phage_annotator.ui_qt.main_window import run_gui
    
    tmp_path = Path.cwd() / f"phage_annotator_demo_{mode}.tif"
    img_path, csv_path = generate_dummy_image(
        tmp_path,
        mode=mode,
        n_spots=n_spots,
        seed=seed,
        shot_noise_strength=shot_noise_strength,
        stray_pixel_fraction=stray_pixel_fraction,
    )
    print(f"✓ Generated demo image: {img_path}")
    print(f"✓ Generated annotations: {csv_path}")
    print(f"  Annotation file contains spot coordinates and properties")
    run_gui([img_path])
class DummyImageArtifacts(tuple):
    """Backward-compatible return wrapper for generated demo assets.

    Acts like ``(image_path, annotation_csv_path)`` for unpacking while also
    behaving like the image path for older callers that pass the return value
    directly into loaders.
    """

    def __new__(cls, image_path: Path, annotation_csv_path: Path):
        return super().__new__(cls, (image_path, annotation_csv_path))

    @property
    def image_path(self) -> Path:
        return self[0]

    @property
    def annotation_csv_path(self) -> Path:
        return self[1]

    @property
    def name(self) -> str:
        return self.image_path.name

    def __fspath__(self) -> str:
        return str(self.image_path)

    def __str__(self) -> str:
        return str(self.image_path)

    def __getattr__(self, attr: str):
        return getattr(self.image_path, attr)
