"""Split definitions from test_integration_large_stacks.py."""

from __future__ import annotations

import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Tuple

import numpy as np
import pytest
import tifffile as tif

from phage_annotator.config.performance import (
    DEFAULT_SLO,
    DOWNSAMPLE_FACTOR_FOR_PRESSURE,
    MEMORY_THRESHOLD_BYTES,
)
from phage_annotator.io import parse_axes_info
from phage_annotator.ui_qt.utils.image_io import load_array, read_metadata


class TestMixedCZTHandling:
    """Test conversion of mixed-axis data into canonical TZYX."""

    def test_czyx_to_tzyx_conversion(self) -> None:
        """CTZYX input should map to TZYX after channel selection."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ctzyx_test.tif"
            shape = (3, 20, 5, 64, 64)  # C, T, Z, Y, X
            data = np.random.default_rng(7).integers(0, 4096, size=shape, dtype="uint16")

            with tif.TiffWriter(str(path)) as writer:
                writer.write(data, metadata={"axes": "CTZYX"})

            arr, has_time, has_z = load_array(path, ome_axes="CTZYX", channel_idx=1)
            assert arr.shape == (20, 5, 64, 64)
            assert has_time is True
            assert has_z is True

    def test_heuristic_fallback_3d(self) -> None:
        """3D stack without metadata should use auto heuristic for T/Z inference."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "3d_no_meta.tif"
            data = np.random.default_rng(9).integers(0, 4096, size=(3, 128, 128), dtype="uint16")

            with tif.TiffWriter(str(path)) as writer:
                writer.write(data, photometric="minisblack")

            arr, has_time, has_z = load_array(path, interpret_3d_as="auto")
            assert arr.shape == (3, 1, 128, 128)
            assert has_time is True
            assert has_z is False
