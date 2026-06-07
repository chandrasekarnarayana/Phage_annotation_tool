"""Utilities to generate dummy microscopy images and run a quick demo."""

from __future__ import annotations

from typing import Literal

DummyMode = Literal["2d", "z", "t", "tz"]


from phage_annotator.tools.demo.artifacts import DummyImageArtifacts
from phage_annotator.tools.demo.image_generators import (
    _add_gaussian_spots,
    _add_realistic_noise,
    generate_dummy_image,
)

def run_demo(*args, **kwargs) -> None:
    """Launch the Qt demo runner after generating demo artifacts."""
    from phage_annotator.ui_qt.demo_runner import run_demo as _run_demo

    _run_demo(*args, **kwargs)
