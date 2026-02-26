"""Cache thrashing detection and overlay dtype normalization tests.

Thrashing detection:
    - verify is_thrashing() returns False initially
    - simulate thrashing (many evictions, few hits)
    - verify is_thrashing() returns True under threshold

Overlay dtype normalization:
    - verify _normalize_overlay_to_uint8() converts float to uint8
    - verify uint8 is preserved
    - verify bool is converted to uint8 (0 or 255)
"""

from __future__ import annotations

import numpy as np
import pytest

from phage_annotator.projection_cache import CacheTelemetry, ProjectionCache
from phage_annotator.render_mpl import _normalize_overlay_to_uint8


class TestThrashingDetection:
    """Test cache thrashing detection."""

    def test_telemetry_no_thrashing_initially(self):
        """Verify thrashing is False when no activity."""
        tel = CacheTelemetry()
        assert tel.is_thrashing() is False

    def test_telemetry_no_thrashing_with_hits(self):
        """Verify thrashing is False when hits > evictions/2."""
        tel = CacheTelemetry()
        tel.hits_this_cycle = 10
        tel.evictions_this_cycle = 5
        assert tel.is_thrashing() is False

    def test_telemetry_thrashing_detected(self):
        """Verify thrashing is True when evictions > 2 * hits."""
        tel = CacheTelemetry()
        tel.hits_this_cycle = 2
        tel.evictions_this_cycle = 5  # 5 > 2*2
        assert tel.is_thrashing() is True

    def test_telemetry_reset_cycle(self):
        """Verify reset_cycle() clears per-cycle counters."""
        tel = CacheTelemetry()
        tel.hits_this_cycle = 10
        tel.misses_this_cycle = 5
        tel.evictions_this_cycle = 3
        tel.reset_cycle()
        assert tel.hits_this_cycle == 0
        assert tel.misses_this_cycle == 0
        assert tel.evictions_this_cycle == 0

    def test_cache_tracks_cycle_counters(self):
        """Verify cache increments per-cycle counters correctly."""
        cache = ProjectionCache(max_mb=2)  # Small budget to trigger evictions
        
        # Add items (512x512 float32 = 1MB each)
        key1 = (0, "mean", (0.0, 0.0, 100.0, 100.0), -1, -1)
        data1 = np.ones((512, 512), dtype=np.float32)
        cache.put(key1, data1)
        
        # Force eviction by adding more data
        for i in range(5):
            key = (i + 1, "mean", (0.0, 0.0, 100.0, 100.0), -1, -1)
            cache.put(key, data1)
        
        # Check telemetry
        tel = cache.telemetry()
        assert tel.evictions_this_cycle > 0, "Should have evictions"
        
        # Reset and verify
        tel.reset_cycle()
        assert tel.evictions_this_cycle == 0

    def test_cache_hit_increments_this_cycle(self):
        """Verify cache.get() increments hits_this_cycle."""
        cache = ProjectionCache(max_mb=100)
        key = (0, "mean", (0.0, 0.0, 100.0, 100.0), -1, -1)
        data = np.ones((256, 256), dtype=np.float32)
        cache.put(key, data)
        
        # Hit
        result = cache.get(key)
        assert result is not None
        assert cache.telemetry().hits_this_cycle == 1
        
        # Miss
        result = cache.get((999, "mean", (0.0, 0.0, 100.0, 100.0), -1, -1))
        assert result is None
        assert cache.telemetry().misses_this_cycle == 1


class TestDtypeOptimization:
    """Test overlay dtype normalization."""

    def test_normalize_uint8_preserved(self):
        """Verify uint8 is preserved as-is."""
        data = np.array([[0, 100, 200, 255]], dtype=np.uint8)
        result = _normalize_overlay_to_uint8(data)
        assert result.dtype == np.uint8
        assert np.array_equal(result, data)

    def test_normalize_bool_to_uint8(self):
        """Verify bool -> uint8 (True=255, False=0)."""
        data = np.array([[True, False, True]], dtype=bool)
        result = _normalize_overlay_to_uint8(data)
        assert result.dtype == np.uint8
        assert result[0, 0] == 255  # True -> 255
        assert result[0, 1] == 0    # False -> 0
        assert result[0, 2] == 255  # True -> 255

    def test_normalize_float32_to_uint8(self):
        """Verify float32 -> uint8 with min/max normalization."""
        data = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
        result = _normalize_overlay_to_uint8(data)
        assert result.dtype == np.uint8
        assert result[0, 0] == 0    # min -> 0
        assert result[0, 1] == 127  # mid -> ~127
        assert result[0, 2] == 255  # max -> 255

    def test_normalize_float64_to_uint8(self):
        """Verify float64 -> uint8 with normalization."""
        data = np.array([[10.0, 50.0, 100.0]], dtype=np.float64)
        result = _normalize_overlay_to_uint8(data)
        assert result.dtype == np.uint8
        assert result[0, 0] == 0    # min -> 0
        assert result[0, 2] == 255  # max -> 255

    def test_normalize_constant_array(self):
        """Verify constant array (min == max) -> all zeros."""
        data = np.ones((5, 5), dtype=np.float32) * 0.5
        result = _normalize_overlay_to_uint8(data)
        assert result.dtype == np.uint8
        assert np.all(result == 0), "Constant array should normalize to zeros"

    def test_normalize_preserves_shape(self):
        """Verify shape is preserved during normalization."""
        data = np.random.rand(100, 50).astype(np.float32)
        result = _normalize_overlay_to_uint8(data)
        assert result.shape == data.shape

    def test_normalize_memory_savings(self):
        """Verify uint8 uses 4x less memory than float32 for overlays."""
        data_f32 = np.ones((1000, 1000), dtype=np.float32)
        data_u8 = _normalize_overlay_to_uint8(data_f32)
        
        nbytes_f32 = data_f32.nbytes
        nbytes_u8 = data_u8.nbytes
        
        assert nbytes_u8 < nbytes_f32
        assert nbytes_f32 / nbytes_u8 >= 4.0, "uint8 should use ~75% less memory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
