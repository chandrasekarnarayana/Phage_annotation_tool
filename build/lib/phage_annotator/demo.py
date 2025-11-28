"""Utilities to generate dummy microscopy images and run a quick demo."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import tifffile as tif

from phage_annotator.gui_mpl import run_gui

DummyMode = Literal["2d", "z", "t", "tz"]


def generate_dummy_image(path: Path, mode: DummyMode = "tz") -> Path:
    """Create a dummy TIFF/OME-TIFF image on disk for testing or demo.

    The "t" mode produces a larger 20-frame 1200x1200 time stack; other modes stay small.
    """
    rng = np.random.default_rng(42)
    if mode == "2d":
        data = rng.random((64, 64), dtype=np.float32)
    elif mode == "z":
        data = rng.random((4, 64, 64), dtype=np.float32)  # (Z, Y, X)
    elif mode == "t":
        # 16-bit-like range with offset: intensities in [100, 300].
        data = (rng.random((20, 1200, 1200), dtype=np.float32) * 200.0 + 100.0).astype(np.uint16)
    elif mode == "tz":
        data = rng.random((2, 3, 64, 64), dtype=np.float32)  # (T, Z, Y, X)
    else:
        raise ValueError(f"Unknown dummy mode: {mode}")

    tif.imwrite(path, data)
    return path


def run_demo(mode: DummyMode = "t") -> None:
    """Generate a dummy image and open it in the GUI."""
    tmp_path = Path.cwd() / f"phage_annotator_demo_{mode}.tif"
    path = generate_dummy_image(tmp_path, mode=mode)
    run_gui([path])
