"""Split definitions from test_disk_cache.py."""

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
