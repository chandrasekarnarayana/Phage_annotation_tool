"""Command-line interface for the phage-annotator microscopy GUI."""

from __future__ import annotations

import pathlib

import click

from phage_annotator import __version__
from phage_annotator.demo import generate_dummy_image


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="phage-annotator")
@click.option(
    "-i",
    "--input",
    "inputs",
    type=click.Path(path_type=pathlib.Path, exists=True, readable=True),
    multiple=True,
    required=False,
    help="One or more TIFF/OME-TIFF image paths. If not provided, launches with a demo image.",
)
@click.option(
    "-n",
    "--spots",
    "n_spots",
    type=int,
    default=None,
    required=False,
    help="Number of spots to generate in demo image (50-300, random if not specified).",
)
@click.option(
    "-s",
    "--seed",
    "seed",
    type=int,
    default=None,
    required=False,
    help="Random seed for reproducibility. Uses current time if not specified.",
)
@click.option(
    "--shot-noise-strength",
    "shot_noise_strength",
    type=float,
    default=1.0,
    required=False,
    help="Shot noise strength for auto-generated demo images (0 disables, 1 default).",
)
@click.option(
    "--stray-pixel-fraction",
    "stray_pixel_fraction",
    type=float,
    default=2e-5,
    required=False,
    help="Sparse hot-pixel fraction for demo images (default 2e-5).",
)
def main(
    inputs: list[pathlib.Path],
    n_spots: int | None,
    seed: int | None,
    shot_noise_strength: float,
    stray_pixel_fraction: float,
) -> None:
    """Launch the Matplotlib+Qt keypoint annotation GUI for microscopy stacks.
    
    If no input files are specified, a demo image is automatically generated
    for exploration and testing.
    """
    # Initialize application context (services) before GUI
    from phage_annotator.framework import ApplicationContext
    
    context = ApplicationContext.create_default()
    ApplicationContext.set_global(context)

    # Import GUI lazily to avoid initializing Qt during module import or non-GUI tests.
    from phage_annotator.ui_qt.main_window import run_gui

    if not inputs:
        # Auto-generate a demo image if no inputs provided
        dummy, annotations = generate_dummy_image(
            pathlib.Path.cwd() / "phage_annotator_demo.tif",
            mode="t",
            n_spots=n_spots,
            seed=seed,
            shot_noise_strength=max(0.0, float(shot_noise_strength)),
            stray_pixel_fraction=max(0.0, float(stray_pixel_fraction)),
        )
        print(f"✓ Generated demo image: {dummy}")
        print(f"✓ Generated annotations: {annotations}")
        run_gui([dummy])
        return

    run_gui(list(inputs))


if __name__ == "__main__":
    main()
