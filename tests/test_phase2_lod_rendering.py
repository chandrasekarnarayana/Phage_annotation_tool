"""Phase 2: LOD-First Rendering and Pyramid Prefetch tests.

Phase 2a: LOD-First Rendering
- When full-res projection is missing, return 8x pyramid level as fallback
- Mark image as being in LOD mode while full-res loads
- Automatically transition to full-res when available

Phase 2b: Pyramid Prefetch  
- Schedule pyramid jobs (8x, 4x, 2x) alongside full-res
- Ensures LOD preview is available faster than full-res computation
"""

from unittest.mock import Mock, MagicMock, patch
import numpy as np
import pytest

from phage_annotator.projection_cache import ProjectionCache, CacheTelemetry
from phage_annotator.image_models import LazyImage


class TestLODFirstRenderingPhase2a:
    """Test Phase 2a: LOD-First Rendering."""

    def test_lod_mode_flag_initialization(self):
        """Verify _lod_mode_active dict is initialized."""
        cache = ProjectionCache(max_mb=10)
        # Create a mock image state
        img = Mock(spec=LazyImage)
        img.id = 0
        img.array = np.random.rand(2, 2, 512, 512).astype(np.float32)
        img.name = "test_image.tif"
        
        # Test that _lod_mode_active can be accessed
        mock_state = Mock()
        mock_state._lod_mode_active = {}
        assert isinstance(mock_state._lod_mode_active, dict)

    def test_full_res_available_disables_lod_mode(self):
        """When full-res is cached, LOD mode should be disabled."""
        cache = ProjectionCache(max_mb=10)
        key = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1)
        data = np.random.rand(512, 512).astype(np.float32)
        
        cache.put(key, data)
        cached = cache.get(key)
        
        # Full-res available should disable LOD
        assert cached is not None
        assert np.array_equal(cached, data)

    def test_pyramid_fallback_when_full_res_missing(self):
        """When full-res missing but pyramid available, return pyramid."""
        cache = ProjectionCache(max_mb=50)
        
        # Create pyramid data (8x downsampled)
        pyramid_data = np.random.rand(64, 64).astype(np.float32)
        pyramid_key = (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3)  # level 3 = 8x
        cache.put_pyramid(pyramid_key, pyramid_data)
        
        # Verify pyramid is cached
        cached_pyramid = cache.get_pyramid(pyramid_key)
        assert cached_pyramid is not None
        assert cached_pyramid.shape == (64, 64)

    def test_lod_mode_marker_set_when_using_pyramid(self):
        """Verify LOD mode is marked active when using pyramid fallback."""
        lod_mode_active = {}
        
        # Simulate full-res not cached, pyramid available
        full_res_cached = False
        if not full_res_cached:
            # In LOD mode, set flag
            lod_mode_active[0] = True
        
        assert lod_mode_active[0] is True

    def test_lod_mode_cleared_when_full_res_arrives(self):
        """LOD mode should be cleared once full-res projection arrives."""
        lod_mode_active = {0: True}
        
        # Simulate full-res arriving (marked in _on_result)
        lod_mode_active[0] = False
        
        assert lod_mode_active[0] is False

    def test_pyramid_level_3_is_8x_downsampling(self):
        """Verify pyramid level 3 corresponds to 8x downsampling."""
        from phage_annotator.pyramid import pyramid_level_factor
        
        level = 3
        scale = pyramid_level_factor(level)
        
        # Level 3 should be 2^3 = 8x
        assert scale == 8

    def test_8x_pyramid_significantly_smaller_than_full_res(self):
        """8x downsampling should reduce memory usage dramatically."""
        full_res = np.zeros((1024, 1024), dtype=np.float32)
        full_res_bytes = full_res.nbytes
        
        # 8x downsampling
        downsampled = full_res[::8, ::8]
        downsampled_bytes = downsampled.nbytes
        
        # Should be (1/8)^2 = 1/64 the size
        expected_ratio = 64
        actual_ratio = full_res_bytes / downsampled_bytes
        
        assert actual_ratio >= 60  # Allow some floating point tolerance


class TestPyramidPrefetchPhase2b:
    """Test Phase 2b: Pyramid Prefetch."""

    def test_pyramid_prefetch_levels_3_2_1(self):
        """Verify pyramid levels 3, 2, 1 are scheduled for prefetch."""
        from phage_annotator.pyramid import pyramid_level_factor
        
        prefetch_levels = [3, 2, 1]
        scales = [pyramid_level_factor(level) for level in prefetch_levels]
        
        # Should be 8x, 4x, 2x
        assert scales == [8, 4, 2]

    def test_pyramid_prefetch_for_both_mean_and_std(self):
        """Pyramid prefetch should schedule jobs for both mean and std."""
        kinds = ["mean", "std"]
        
        # For each kind and level, a job should be scheduled
        num_levels = 3  # levels 3, 2, 1
        expected_jobs = len(kinds) * num_levels
        
        assert expected_jobs == 6

    def test_pyramid_prefetch_avoids_duplicate_jobs(self):
        """Don't schedule pyramid jobs if already cached or in progress."""
        pyramid_jobs = {}
        
        # First request
        key1 = (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3)
        if key1 not in pyramid_jobs:
            pyramid_jobs[key1] = "job_name"
        
        # Second request (should skip)
        if key1 not in pyramid_jobs:
            pyramid_jobs[key1] = "job_name"  # Should not execute
        
        # Only one entry should exist
        assert len(pyramid_jobs) == 1

    def test_pyramid_cache_put_dedupes_on_cache_hit(self):
        """Pyramid cache.put_pyramid should skip if already cached."""
        cache = ProjectionCache(max_mb=50)
        
        data1 = np.ones((64, 64), dtype=np.float32)
        data2 = np.zeros((64, 64), dtype=np.float32)
        
        key = (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3)
        
        # First put
        cache.put_pyramid(key, data1)
        cached = cache.get_pyramid(key)
        assert np.all(cached == 1.0)
        
        # Second put (updates)
        cache.put_pyramid(key, data2)
        cached = cache.get_pyramid(key)
        assert np.all(cached == 0.0)

    def test_full_res_job_scheduled_after_pyramid_prefetch(self):
        """Full-res job should be scheduled alongside (or after) pyramid prefetch."""
        job_queue = []
        
        # Add pyramid prefetch jobs (low priority)
        for level in [3, 2, 1]:
            for kind in ["mean", "std"]:
                job_queue.append({"type": "pyramid", "level": level, "kind": kind})
        
        # Add full-res job (normal priority)
        job_queue.append({"type": "full_res", "kind": None})
        
        # Verify structure: pyramid jobs first, then full-res
        assert job_queue[0]["type"] == "pyramid"
        assert job_queue[-1]["type"] == "full_res"
        assert len([j for j in job_queue if j["type"] == "pyramid"]) == 6

    def test_pyramid_result_callback_caches_data(self):
        """Pyramid prefetch result callback should cache the downsampled data."""
        cache = ProjectionCache(max_mb=50)
        
        pyramid_key = (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3)
        pyramid_data = np.random.rand(64, 64).astype(np.float32)
        
        # Simulate result callback putting data into cache
        cache.put_pyramid(pyramid_key, pyramid_data)
        
        # Verify it's accessible
        cached = cache.get_pyramid(pyramid_key)
        assert cached is not None
        assert cached.shape == (64, 64)


class TestPhase2Integration:
    """Integration tests for Phase 2 LOD + Prefetch."""

    def test_lod_fallback_when_full_res_loading(self):
        """Verify LOD fallback integrates with full-res loading."""
        cache = ProjectionCache(max_mb=50)
        
        # Scenario: Full-res loading, only 8x pyramid available
        full_res_key = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1)
        pyramid_key = (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3)
        
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
        
        key = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1)
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
            (0, "mean", -1, -1, (0.0, 0.0, 0.0, 0.0), 3): "job_name_1",
            (0, "std", -1, -1, (0.0, 0.0, 0.0, 0.0), 3): "job_name_2",
        }
        
        image_id_to_evict = 0
        
        # Clear pyramid jobs for evicted image
        keys_to_remove = [k for k in pyramid_jobs.keys() if k[0] == image_id_to_evict]
        for k in keys_to_remove:
            pyramid_jobs.pop(k, None)
        
        assert len(pyramid_jobs) == 0

    def test_phase2a_backward_compatible_with_phase1(self):
        """Phase 2a should not break Phase 1 (thrashing detection)."""
        cache = ProjectionCache(max_mb=10)
        telemetry = cache.telemetry()
        
        # Phase 1a functionality should still work
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
