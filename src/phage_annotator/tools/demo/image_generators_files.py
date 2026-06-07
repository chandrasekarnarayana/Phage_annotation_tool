"""Split definitions from demo_image_generators.py."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

import numpy as np

DummyMode = Literal["2d", "z", "t", "tz"]


from phage_annotator.tools.demo.image_generators_spots import _add_gaussian_spots, _add_realistic_noise

def generate_dummy_image(
    path: Path,
    mode: DummyMode = "tz",
    n_spots: int | None = None,
    seed: int | None = None,
    shot_noise_strength: float = 1.0,
    stray_pixel_fraction: float = 2e-5,
) -> "DummyImageArtifacts":  # type: ignore[name-defined]
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
    import csv
    import tifffile as tif
    from phage_annotator.tools.demo.artifacts import DummyImageArtifacts

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

    # Generate annotation CSV using the app's canonical import schema.
    # Required columns for keypoints_from_csv: image_name, t, z, y, x
    standardized_rows = []
    image_name = path.name
    for spot in all_spots:
        row_t = -1
        row_z = -1
        if mode == "t":
            row_t = int(spot.get("timepoint", -1))
        elif mode == "z":
            row_z = int(spot.get("timepoint", -1))
        elif mode == "tz":
            row_t = int(spot.get("t", -1))
            row_z = int(spot.get("z", -1))
        standardized_rows.append(
            {
                "image_name": image_name,
                "t": row_t,
                "z": row_z,
                "y": float(spot.get("y", -1)),
                "x": float(spot.get("x", -1)),
                "label": "phage",
                "source": "demo_ground_truth",
            }
        )

    csv_path = path.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        fieldnames = ["image_name", "t", "z", "y", "x", "label", "source"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(standardized_rows)

    return DummyImageArtifacts(path, csv_path)
