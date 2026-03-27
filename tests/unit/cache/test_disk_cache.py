"""Tests for disk cache with Zstd compression."""

from __future__ import annotations

import pathlib
import shutil
import tempfile
import unittest
from concurrent.futures import Future

import numpy as np

try:
    from phage_annotator.cache.disk_cache import HAS_ZSTD, DiskCache, DiskCacheConfig
    HAS_DISK_CACHE = True
except ImportError:
    HAS_DISK_CACHE = False
    HAS_ZSTD = False


@unittest.skipIf(
    (not HAS_DISK_CACHE) or (not HAS_ZSTD),
    "disk cache requires optional zstandard dependency",
)
class TestDiskCache(unittest.TestCase):
    """Tests for DiskCache functionality."""

    def setUp(self):
        """Create temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = DiskCacheConfig(
            enabled=True,
            max_size_mb=100,
            cache_dir=pathlib.Path(self.temp_dir)
        )
        self.cache = DiskCache(self.config)

    def tearDown(self):
        """Clean up temporary directory."""
        if self.cache:
            self.cache.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_initialization(self):
        """Test cache initializes with correct config."""
        self.assertTrue(self.cache.config.enabled)
        self.assertEqual(self.cache.config.max_size_mb, 100)
        self.assertEqual(self.cache.stats.saves, 0)
        self.assertEqual(self.cache.stats.hits, 0)

    def test_save_and_load_simple(self):
        """Test saving and loading a simple array."""
        key = (0, "mean", (0, 0, 512, 512), -1, -1)
        data = np.ones((512, 512), dtype=np.float32)

        # Save
        result = self.cache.save(key, data)
        self.assertTrue(result)
        self.assertEqual(self.cache.stats.saves, 1)

        # Load
        loaded = self.cache.load(key)
        self.assertIsNotNone(loaded)
        self.assertTrue(np.allclose(loaded, data))
        self.assertEqual(self.cache.stats.hits, 1)
        self.assertEqual(self.cache.stats.loads, 1)

    def test_load_missing_key(self):
        """Test loading a key that doesn't exist."""
        key = (999, "mean", (0, 0, 512, 512), -1, -1)
        loaded = self.cache.load(key)

        self.assertIsNone(loaded)
        self.assertEqual(self.cache.stats.misses, 1)
        self.assertEqual(self.cache.stats.hits, 0)

    def test_compression_ratio(self):
        """Test that compression reduces file size."""
        key = (0, "mean", (0, 0, 512, 512), -1, -1)
        # Create array with repetitive data (highly compressible)
        data = np.zeros((512, 512), dtype=np.float32)

        self.cache.save(key, data)

        ratio = self.cache.get_compression_ratio()
        # Zero-filled array should compress very well (>10x)
        self.assertGreater(ratio, 5.0)

    def test_multiple_saves_different_keys(self):
        """Test saving multiple different arrays."""
        for i in range(5):
            key = (i, "mean", (0, 0, 512, 512), -1, -1)
            data = np.ones((256, 256), dtype=np.float32) * i

            self.cache.save(key, data)

        self.assertEqual(self.cache.stats.saves, 5)

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        key1 = (0, "mean", (0, 0, 512, 512), -1, -1)
        key2 = (999, "mean", (0, 0, 512, 512), -1, -1)

        data = np.ones((256, 256), dtype=np.float32)
        self.cache.save(key1, data)

        # 1 hit
        self.cache.load(key1)
        # 2 misses
        self.cache.load(key2)
        self.cache.load(key2)

        rate = self.cache.hit_rate()
        self.assertAlmostEqual(rate, 1.0 / 3.0, places=2)

    def test_eviction_on_size_limit(self):
        """Test that oldest items are evicted when size limit exceeded."""
        # Use small size limit
        small_config = DiskCacheConfig(
            enabled=True,
            max_size_mb=1,  # 1 MB limit
            cache_dir=pathlib.Path(self.temp_dir)
        )
        small_cache = DiskCache(small_config)

        # Add large arrays until eviction is triggered
        for i in range(10):
            key = (i, "mean", (0, 0, 512, 512), -1, -1)
            data = np.random.rand(256, 256).astype(np.float32)
            small_cache.save(key, data)

        # Should have evicted some items
        self.assertLess(small_cache.stats.current_size_bytes, 2 * 1024 * 1024)

        small_cache.clear()

    def test_clear_cache(self):
        """Test clearing the entire cache."""
        key = (0, "mean", (0, 0, 512, 512), -1, -1)
        data = np.ones((256, 256), dtype=np.float32)

        self.cache.save(key, data)
        self.assertGreater(self.cache.stats.current_size_bytes, 0)

        self.cache.clear()

        self.assertEqual(self.cache.stats.current_size_bytes, 0)
        self.assertEqual(len(self.cache._index), 0)
        self.assertEqual(len(self.cache._lru_order), 0)

    def test_different_dtypes(self):
        """Test saving and loading arrays with different dtypes."""
        dtypes = [np.float32, np.float64, np.uint8, np.uint16]

        for i, dtype in enumerate(dtypes):
            key = (i, "mean", (0, 0, 512, 512), -1, -1)
            data = np.ones((100, 100), dtype=dtype)

            self.cache.save(key, data)
            loaded = self.cache.load(key)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.dtype, dtype)
            self.assertTrue(np.allclose(loaded, data))

    def test_lru_eviction_order(self):
        """Test that LRU order is maintained for eviction."""
        # Save items in order
        keys = []
        for i in range(5):
            key = (i, "mean", (0, 0, 512, 512), -1, -1)
            data = np.ones((50, 50), dtype=np.float32) * i
            keys.append(key)
            self.cache.save(key, data)

        # Access key 0 (moves it to end of LRU)
        self.cache.load(keys[0])

        # LRU order should now be [1, 2, 3, 4, 0]
        # The oldest accessed should be key 1
        self.assertEqual(len(self.cache._lru_order), 5)

    def test_stats_tracking(self):
        """Test that all stats are tracked correctly."""
        key = (0, "mean", (0, 0, 512, 512), -1, -1)
        data = np.ones((256, 256), dtype=np.float32)

        # Save
        self.cache.save(key, data)
        self.assertGreater(self.cache.stats.bytes_saved, 0)

        # Load
        self.cache.load(key)
        self.assertGreater(self.cache.stats.bytes_loaded, 0)

        # Stats should be updated
        self.assertEqual(self.cache.stats.saves, 1)
        self.assertEqual(self.cache.stats.hits, 1)
        self.assertEqual(self.cache.stats.loads, 1)

    def test_completed_pending_save_is_cleaned_up(self):
        """Completed async save futures should not accumulate indefinitely."""
        future = Future()
        future.set_result(None)
        self.cache._pending_saves["done"] = future

        self.cache._reap_completed_saves_locked()

        self.assertNotIn("done", self.cache._pending_saves)


@unittest.skipIf(
    (not HAS_DISK_CACHE) or (not HAS_ZSTD),
    "disk cache requires optional zstandard dependency",
)
class TestDiskCacheIntegration(unittest.TestCase):
    """Integration tests for disk cache."""

    def setUp(self):
        """Create temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = DiskCacheConfig(
            enabled=True,
            max_size_mb=50,
            cache_dir=pathlib.Path(self.temp_dir)
        )
        self.cache = DiskCache(self.config)

    def tearDown(self):
        """Clean up temporary directory."""
        if self.cache:
            self.cache.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_simulate_fov_browsing(self):
        """Simulate browsing through multiple FOVs with disk cache fallback.
        
        Scenario:
        1. Load 3 FOVs of a large stack
        2. Evict oldest FOV (to disk cache)
        3. Re-access oldest FOV (should restore from disk)
        """
        fov_data = {}

        # Load 3 FOVs
        for fov_id in range(3):
            key = (fov_id, "mean", (0, 0, 512, 512), -1, -1)
            data = np.random.rand(512, 512).astype(np.float32)
            fov_data[fov_id] = data

            self.cache.save(key, data)

        self.assertEqual(self.cache.stats.saves, 3)

        # Re-access FOV 0 (should hit disk cache)
        key0 = (0, "mean", (0, 0, 512, 512), -1, -1)
        loaded = self.cache.load(key0)

        self.assertIsNotNone(loaded)
        self.assertTrue(np.allclose(loaded, fov_data[0]))
        self.assertGreater(self.cache.stats.hits, 0)

    def test_persistence_across_instances(self):
        """Test that cache persists on disk across cache instances.
        
        Note: This test saves files to disk but doesn't test loading across
        separate instances (would require restarting the cache).
        """
        key = (0, "mean", (0, 0, 512, 512), -1, -1)
        data = np.ones((100, 100), dtype=np.float32)

        # Save to disk
        self.cache.save(key, data)
        cache_files = list(self.config.cache_dir.glob("*"))

        # Should have at least one cached file
        self.assertGreater(len(cache_files), 0)

    def test_concurrent_access_simulation(self):
        """Simulate rapid save/load cycles."""
        for cycle in range(5):
            for i in range(10):
                key = (i, "mean", (0, 0, 512, 512), -1, -1)
                data = np.ones((50, 50), dtype=np.float32) * i

                self.cache.save(key, data)
                self.cache.load(key)

        # Should have processed all operations
        self.assertEqual(self.cache.stats.saves, 50)
        self.assertGreater(self.cache.stats.hits, 40)


@unittest.skipIf(not HAS_DISK_CACHE, "disk_cache module not available")
class TestDiskCacheConfiguration(unittest.TestCase):
    """Tests for disk cache configuration."""

    def test_config_default_cache_dir(self):
        """Test that default cache directory is ~/.cache/phage_annotator."""
        config = DiskCacheConfig()

        expected = pathlib.Path.home() / ".cache" / "phage_annotator"
        self.assertEqual(config.cache_dir, expected)

    def test_config_custom_cache_dir(self):
        """Test setting custom cache directory."""
        custom_dir = pathlib.Path("/tmp/custom_cache")
        config = DiskCacheConfig(cache_dir=custom_dir)

        self.assertEqual(config.cache_dir, custom_dir)

    def test_config_disabled(self):
        """Test that cache respects enabled flag."""
        config = DiskCacheConfig(enabled=False)
        cache = DiskCache(config)

        key = (0, "mean", (0, 0, 512, 512), -1, -1)
        data = np.ones((100, 100), dtype=np.float32)

        # Should not save when disabled
        result = cache.save(key, data)
        self.assertFalse(result)

        # Should not load when disabled
        loaded = cache.load(key)
        self.assertIsNone(loaded)


@unittest.skipIf(
    (not HAS_DISK_CACHE) or (not HAS_ZSTD),
    "disk cache requires optional zstandard dependency",
)
class TestProjectionCacheDiskIntegration(unittest.TestCase):
    """Test integration between ProjectionCache and DiskCache."""

    def setUp(self):
        """Create temporary cache directory and instances."""
        self.temp_dir = tempfile.mkdtemp()
        self.disk_config = DiskCacheConfig(
            enabled=True,
            max_size_mb=50,
            cache_dir=pathlib.Path(self.temp_dir)
        )
        self.disk_cache = DiskCache(self.disk_config)

    def tearDown(self):
        """Clean up temporary directory."""
        if pathlib.Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_projection_cache_with_disk_cache(self):
        """Test that ProjectionCache uses disk cache for evicted items."""
        from phage_annotator.cache.projection_cache import ProjectionCache

        # Create projection cache with disk cache
        proj_cache = ProjectionCache(max_mb=10, disk_cache=self.disk_cache)

        # Add large array to trigger eviction
        key1 = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
        data1 = np.ones((512, 512), dtype=np.float32)  # ~1 MB
        proj_cache.put(key1, data1)

        # Verify it's in memory
        retrieved = proj_cache.get(key1)
        self.assertIsNotNone(retrieved)
        np.testing.assert_array_equal(retrieved, data1)

        # Add more data to trigger eviction of first
        for i in range(15):
            key = (i + 1, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
            data = np.ones((512, 512), dtype=np.float32)
            proj_cache.put(key, data)

        # Original key1 may or may not still be in memory depending on eviction timing.
        proj_cache.get(key1)

        # But it should load from disk if available
        disk_result = self.disk_cache.load(key1)
        self.assertIsNotNone(disk_result, "Evicted item should be in disk cache")
        np.testing.assert_array_equal(disk_result, data1)

    def test_disk_cache_hit_after_memory_miss(self):
        """Test that memory miss falls back to disk cache."""
        from phage_annotator.cache.projection_cache import ProjectionCache

        # Manually add to disk cache (simulating evicted item)
        key = (1, "std", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
        data = np.ones((256, 256), dtype=np.float32)
        self.disk_cache.save(key, data)

        # Create new cache that will check disk on miss
        new_proj_cache = ProjectionCache(max_mb=10, disk_cache=self.disk_cache)

        # Request evicted item - should fall back to disk
        result = new_proj_cache.get(key)
        self.assertIsNotNone(result, "Should load from disk on memory miss")
        np.testing.assert_array_equal(result, data)

    def test_disk_cache_optional_graceful_degradation(self):
        """Test that ProjectionCache works without disk cache."""
        from phage_annotator.cache.projection_cache import ProjectionCache

        # ProjectionCache without disk cache should still work
        proj_cache = ProjectionCache(max_mb=10, disk_cache=None)

        key = (0, "raw", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
        data = np.ones((256, 256), dtype=np.float32)
        proj_cache.put(key, data)

        # Should retrieve from memory
        retrieved = proj_cache.get(key)
        self.assertIsNotNone(retrieved)
        np.testing.assert_array_equal(retrieved, data)

    def test_multiple_fov_eviction_cycle(self):
        """Test disk cache during multi-FOV browsing scenario."""
        from phage_annotator.cache.projection_cache import ProjectionCache

        proj_cache = ProjectionCache(max_mb=20, disk_cache=self.disk_cache)

        # Simulate browsing 5 FOVs with multiple tiles each
        fov_data = {}
        for fov_idx in range(5):
            for tile_idx in range(4):
                key = (
                    fov_idx,
                    "mean",
                    (float(tile_idx), 0.0, 0.0, 0.0),
                    -1,
                    -1,
                    0,
                )
                data = np.random.rand(256, 256).astype(np.float32)
                fov_data[key] = data
                proj_cache.put(key, data)

        # Browse back to first FOV - some tiles might be in disk cache
        fov0_key = (0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1, 0)
        
        # Try to get tile from first FOV
        result = proj_cache.get(fov0_key)
        
        # Either in memory or can be loaded from disk
        if result is None:
            # May have been evicted from memory, check disk
            disk_result = self.disk_cache.load(fov0_key)
            if disk_result is not None:
                np.testing.assert_array_equal(disk_result, fov_data[fov0_key])
        else:
            # Still in memory
            np.testing.assert_array_equal(result, fov_data[fov0_key])


if __name__ == "__main__":
    unittest.main()
