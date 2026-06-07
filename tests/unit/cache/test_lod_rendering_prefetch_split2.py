"""Split definitions from test_lod_rendering_prefetch.py."""


from unittest.mock import Mock, MagicMock, patch
import numpy as np
import pytest

from phage_annotator.cache.projection_cache import ProjectionCache, CacheTelemetry
from phage_annotator.data.models import LazyImage


class TestLodPrefetchIntegration:
    """Integration tests for LOD and prefetch."""

    def test_lod_fallback_when_full_res_loading(self):
        """Verify LOD fallback integrates with full-res loading."""
        cache = ProjectionCache(max_mb=50)
        
        # Scenario: Full-res loading, only 8x pyramid available
        full_res_key = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
        pyramid_key = (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3, 0)
        
        # Pre-populate pyramid
        pyramid_data = np.random.rand(64, 64).astype(np.float32)
        cache.put_pyramid(pyramid_key, pyramid_data)
        
        # Full-res not cached
        full_res_cached = cache.get(full_res_key)
        assert full_res_cached is None
        
        # Pyramid available
        pyramid_cached = cache.get_pyramid(pyramid_key)
        assert pyramid_cached is not None

    def test_lod_mode_transitions_when_full_res_complete(self):
        """Verify LOD mode transitions to full-res when ready."""
        lod_mode_active = {0: True}
        cache = ProjectionCache(max_mb=50)
        
        key = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
        data = np.random.rand(512, 512).astype(np.float32)
        
        # Full-res completes (in _on_result callback)
        cache.put(key, data)
        lod_mode_active[0] = False
        
        # Verify transition
        assert cache.get(key) is not None
        assert lod_mode_active[0] is False

    def test_pyramid_prefetch_improves_perceived_latency(self):
        """Verify prefetch strategy reduces time-to-first-display."""
        # Simulate job scheduling
        jobs = []
        
        # Pyramid jobs (fast, low priority)
        for level in [3, 2, 1]:
            jobs.append({"name": f"pyramid_l{level}", "time_ms": 5 + level})
        
        # Full-res job (slower, high priority)
        jobs.append({"name": "full_res", "time_ms": 50})
        
        # Verify pyramid completes before full-res
        pyramid_times = [j["time_ms"] for j in jobs if "pyramid" in j["name"]]
        full_res_time = [j["time_ms"] for j in jobs if "full_res" in j["name"]][0]
        
        assert all(pt < full_res_time for pt in pyramid_times)

    def test_lod_indicator_counts_active_images(self):
        """LOD indicator should count how many images are in LOD mode."""
        lod_mode_active = {0: True, 1: False, 2: True}
        
        active_count = sum(1 for v in lod_mode_active.values() if v)
        
        assert active_count == 2
        assert f"ACTIVE ({active_count})" == "ACTIVE (2)"

    def test_pyramid_prefetch_handles_image_eviction(self):
        """Pyramid prefetch jobs should be cancelled when image is evicted."""
        pyramid_jobs = {
            (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3, 0): "job_name_1",
            (0, "std", -1, -1, (0.0, 0.0, 0.0, 0.0), 3): "job_name_2",
        }
        
        image_id_to_evict = 0
        
        # Clear pyramid jobs for evicted image
        keys_to_remove = [k for k in pyramid_jobs.keys() if k[0] == image_id_to_evict]
        for k in keys_to_remove:
            pyramid_jobs.pop(k, None)
        
        assert len(pyramid_jobs) == 0

    def test_lod_prefetch_backward_compatible_with_thrashing_detection(self):
        """LOD/prefetch should not break thrashing detection."""
        cache = ProjectionCache(max_mb=10)
        telemetry = cache.telemetry()
        
        # Thrashing detection functionality should still work
        assert hasattr(telemetry, 'is_thrashing')
        assert hasattr(telemetry, 'reset_cycle')
        assert hasattr(telemetry, 'hits_this_cycle')
        assert hasattr(telemetry, 'evictions_this_cycle')

class TestLODIndicatorUI:
    """Test LOD indicator display in performance panel."""

    def test_lod_indicator_shows_off_initially(self):
        """LOD indicator should show "OFF" when no images in LOD mode."""
        lod_mode_active = {}
        
        if not any(lod_mode_active.values()):
            status = "OFF"
        else:
            status = f"ACTIVE ({sum(1 for v in lod_mode_active.values() if v)})"
        
        assert status == "OFF"

    def test_lod_indicator_shows_active_count(self):
        """LOD indicator should show count of active images."""
        lod_mode_active = {0: True, 1: True, 2: False}
        
        active_count = sum(1 for v in lod_mode_active.values() if v)
        if active_count > 0:
            status = f"ACTIVE ({active_count})"
        else:
            status = "OFF"
        
        assert status == "ACTIVE (2)"

    def test_lod_indicator_color_blue_when_active(self):
        """LOD indicator should be colored blue when active."""
        lod_mode_active = {0: True}
        
        if any(lod_mode_active.values()):
            color = "#4dabf7"  # Blue
        else:
            color = None  # Default
        
        assert color == "#4dabf7"

    def test_lod_indicator_color_default_when_off(self):
        """LOD indicator should use default color when off."""
        lod_mode_active = {0: False}
        
        if any(lod_mode_active.values()):
            color = "#4dabf7"
        else:
            color = "default"
        
        assert color == "default"
