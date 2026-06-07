"""Demo runner: generate a dummy image and open it in the GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

DummyMode = Literal["2d", "z", "t", "tz"]


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
    from phage_annotator.tools.demo.image_generators import generate_dummy_image

    tmp_path = Path.cwd() / f"phage_annotator_demo_{mode}.tif"
    img_path, csv_path = generate_dummy_image(
        tmp_path,
        mode=mode,
        n_spots=n_spots,
        seed=seed,
        shot_noise_strength=shot_noise_strength,
        stray_pixel_fraction=stray_pixel_fraction,
    )
    print(f"Generated demo image: {img_path}")
    print(f"Generated annotations: {csv_path}")
    print(f"  Annotation file contains spot coordinates and properties")
    run_gui([img_path])
