"""Command-line interface for the phage-annotator microscopy GUI."""

from __future__ import annotations

import pathlib
from typing import List

import click

from phage_annotator import __version__
from phage_annotator.demo import generate_dummy_image
from phage_annotator.gui_mpl import run_gui


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="phage-annotator")
@click.option(
    "-i",
    "--input",
    "inputs",
    type=click.Path(path_type=pathlib.Path, exists=True, readable=True),
    multiple=True,
    required=False,
    help="One or more TIFF/OME-TIFF image paths.",
)
@click.option(
    "--demo",
    is_flag=True,
    default=False,
    help="Launch a short demo with a generated dummy TIFF instead of real inputs.",
)
def main(inputs: List[pathlib.Path], demo: bool) -> None:
    """Launch the Matplotlib+Qt keypoint annotation GUI for microscopy stacks."""
    if demo:
        dummy = generate_dummy_image(pathlib.Path.cwd() / "phage_annotator_demo.tif", mode="t")
        run_gui([dummy])
        return

    if not inputs:
        raise click.UsageError("Please provide at least one TIFF/OME-TIFF file (or use --demo).")
    run_gui(list(inputs))


if __name__ == "__main__":
    main()
