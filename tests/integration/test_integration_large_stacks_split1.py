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


def _dtype_for_name(dtype: str) -> np.dtype:
    """Resolve a dtype name to ``np.dtype`` once for test fixture generation."""
    return np.dtype(dtype)

def _mock_memory_pressure(monkeypatch: pytest.MonkeyPatch, shape: Tuple[int, ...], dtype: str) -> None:
    """Lower loader threshold so a modest test stack triggers downsampling."""
    dtype_obj = _dtype_for_name(dtype)
    nbytes = int(np.prod(shape) * dtype_obj.itemsize)
    forced_threshold = float(max(1, nbytes // 3))
    monkeypatch.setattr(
        "phage_annotator.ui_qt.utils.image_io.MEMORY_THRESHOLD_BYTES",
        forced_threshold,
    )

class TestLargeStackLoading:
    """Test loading of multi-channel and memory-pressured stacks."""

    @staticmethod
    def create_synthetic_3d_stack(
        path: Path,
        shape: Tuple[int, int, int, int],
        dtype: str = "uint16",
        bit_depth: int = 12,
        channels: int = 1,
        ome_axes: str = "TZYX",
    ) -> None:
        """Create a synthetic OME-TIFF stack with deterministic channel contrast.

        Parameters
        ----------
        path : Path
            Output file path.
        shape : Tuple[int, int, int, int]
            Canonical ``(T, Z, Y, X)`` shape.
        dtype : str
            NumPy dtype name.
        bit_depth : int
            Effective bit depth used to bound generated values.
        channels : int
            Number of channels. ``channels > 1`` produces ``CTZYX`` data.
        ome_axes : str
            Axes for the non-channel portion. Defaults to ``TZYX``.
        """
        dtype_obj = _dtype_for_name(dtype)
        rng = np.random.default_rng(42)
        max_val = min((2**bit_depth) - 1, np.iinfo(dtype_obj).max)

        if channels > 1:
            full_shape = (channels, *shape)
            full_axes = f"C{ome_axes}"
            data = np.empty(full_shape, dtype=dtype_obj)
            for channel_idx in range(channels):
                offset = int(max_val * (channel_idx + 1) / (channels + 1))
                noise = rng.integers(
                    0,
                    max(2, max_val // 20),
                    size=shape,
                    dtype=dtype_obj,
                )
                data[channel_idx] = np.clip(offset + noise, 0, max_val).astype(dtype_obj)
        else:
            full_shape = shape
            full_axes = ome_axes
            data = rng.integers(0, max_val, size=full_shape, dtype=dtype_obj)

        with tif.TiffWriter(str(path)) as writer:
            writer.write(
                data,
                metadata={"axes": full_axes},
                photometric="minisblack",
            )

    def test_multi_channel_stack_loading(self) -> None:
        """Load CTZYX and verify channel-aware extraction and axis flags."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_ctzyx_c3.tif"
            shape = (20, 5, 128, 128)
            channels = 3

            self.create_synthetic_3d_stack(
                path,
                shape=shape,
                channels=channels,
                ome_axes="TZYX",
            )

            lazy = read_metadata(path)
            assert lazy.channel_count == channels
            assert lazy.has_time is True
            assert lazy.has_z is True
            assert lazy.axis_info["tzyx"] == shape

            arr, has_time, has_z = load_array(path, ome_axes="CTZYX", channel_idx=0)
            assert arr.shape == shape
            assert has_time is True
            assert has_z is True

            arr_c1, _, _ = load_array(path, ome_axes="CTZYX", channel_idx=1)
            arr_c2, _, _ = load_array(path, ome_axes="CTZYX", channel_idx=2)
            assert arr_c1.shape == shape
            assert arr_c2.shape == shape
            assert not np.allclose(arr_c1, arr_c2)

    def test_large_stack_memory_pressure_detection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Memory pressure triggers spatial downsampling and diagnostics."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_large.tif"
            shape = (12, 4, 192, 192)
            self.create_synthetic_3d_stack(path, shape=shape, dtype="uint16", bit_depth=16)
            _mock_memory_pressure(monkeypatch, shape, "uint16")

            arr, _, _ = load_array(path, ome_axes="TZYX")
            assert hasattr(arr, "_diagnostics")
            diagnostics = arr._diagnostics

            assert diagnostics.get("downsampled") is True
            assert diagnostics.get("downsample_factor") == DOWNSAMPLE_FACTOR_FOR_PRESSURE
            assert "Memory pressure" in diagnostics.get("downsampling_reason", "")
            assert arr.shape == (shape[0], shape[1], shape[2] // 2, shape[3] // 2)

    def test_reference_dataset_simulation(self) -> None:
        """Scaled-down reference dataset still validates contract and metadata."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reference_dataset_small.tif"
            shape = (24, 6, 256, 256)

            self.create_synthetic_3d_stack(
                path,
                shape=shape,
                dtype="uint16",
                bit_depth=16,
                ome_axes="TZYX",
            )

            lazy = read_metadata(path)
            axis_info = lazy.axis_info
            assert axis_info["tzyx"] == shape
            assert axis_info["has_time"] is True
            assert axis_info["has_z"] is True
            assert axis_info["source"] in {"ome", "heuristic"}
            assert axis_info["channel_count"] == 1

            arr, has_time, has_z = load_array(path, ome_axes="TZYX")
            assert arr.shape == shape
            assert has_time is True
            assert has_z is True
            assert arr.nbytes < MEMORY_THRESHOLD_BYTES
            assert arr._diagnostics["downsampled"] is False

class TestChannelAwareLoading:
    """Test channel parsing and channel index behavior."""

    def test_parse_axes_info_multi_channel(self) -> None:
        """Axes parser reports channel count and C/Z/T flags for CTZYX."""
        shape_tzyx = (20, 5, 128, 128)
        channels = 3
        info = parse_axes_info((channels, *shape_tzyx), ome_axes="CTZYX")
        assert info["channel_count"] == channels
        assert info["has_time"] is True
        assert info["has_z"] is True
        assert info["source"] == "ome"

    def test_channel_idx_validation(self) -> None:
        """Out-of-range channel index should fall back to channel 0."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_channel.tif"
            TestLargeStackLoading.create_synthetic_3d_stack(
                path,
                shape=(20, 5, 128, 128),
                channels=2,
                ome_axes="TZYX",
            )

            arr_c0, _, _ = load_array(path, ome_axes="CTZYX", channel_idx=0)
            arr_invalid, _, _ = load_array(path, ome_axes="CTZYX", channel_idx=999)
            assert np.allclose(arr_invalid, arr_c0)

class TestPerformanceAgainstSLO:
    """Test lightweight latency bounds against the declared SLOs."""

    def test_frame_stepping_latency(self) -> None:
        """Frame access should remain comfortably under relaxed CI margin."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "perf_test.tif"
            shape = (40, 8, 256, 256)
            TestLargeStackLoading.create_synthetic_3d_stack(path, shape=shape, ome_axes="TZYX")
            arr, _, _ = load_array(path, ome_axes="TZYX")

            latencies_ms = []
            for t_idx in range(0, arr.shape[0], 4):
                start = time.perf_counter()
                _ = arr[t_idx, 0, :, :]
                latencies_ms.append((time.perf_counter() - start) * 1000)

            latencies_sorted = sorted(latencies_ms)
            p50 = latencies_sorted[int(len(latencies_sorted) * 0.5)]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            assert p50 < DEFAULT_SLO.frame_step_p50_ms * 10
            assert p95 < DEFAULT_SLO.frame_step_p95_ms * 10

    def test_projection_computation_latency(self) -> None:
        """Mean projection should remain under a practical integration bound."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "proj_test.tif"
            shape = (30, 6, 256, 256)
            TestLargeStackLoading.create_synthetic_3d_stack(path, shape=shape, ome_axes="TZYX")
            arr, _, _ = load_array(path, ome_axes="TZYX")

            start = time.perf_counter()
            _ = np.mean(arr, axis=(0, 1))
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < DEFAULT_SLO.overlay_p95_ms * 4

class TestDownsamplingCorrectness:
    """Test shape/value correctness for spatial downsampling behavior."""

    def test_downsampling_preserves_content(self) -> None:
        """2x downsampling should preserve block means."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "downsample_test.tif"
            shape = (10, 5, 128, 128)
            TestLargeStackLoading.create_synthetic_3d_stack(path, shape=shape, ome_axes="TZYX")
            arr, _, _ = load_array(path, ome_axes="TZYX")

            from phage_annotator.data.pyramid import downsample_mean_pool

            downsampled = downsample_mean_pool(arr[0, 0], 2)
            assert downsampled.shape == (64, 64)

            original_mean = arr[0, 0, 0:2, 0:2].mean()
            downsampled_val = downsampled[0, 0]
            assert np.isclose(original_mean, downsampled_val, rtol=0.05)

    def test_diagnostic_metadata_attached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Downsampled arrays expose full diagnostics payload."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "diag_test.tif"
            shape = (12, 4, 192, 192)
            TestLargeStackLoading.create_synthetic_3d_stack(path, shape=shape, ome_axes="TZYX")
            _mock_memory_pressure(monkeypatch, shape, "uint16")

            arr, _, _ = load_array(path, ome_axes="TZYX")
            assert hasattr(arr, "_diagnostics")
            diagnostics = arr._diagnostics

            assert diagnostics["downsampled"] is True
            assert diagnostics["downsample_factor"] > 0
            assert "Memory pressure" in diagnostics["downsampling_reason"]
