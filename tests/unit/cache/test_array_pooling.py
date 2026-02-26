"""Array pooling and reuse tests."""

from __future__ import annotations

import unittest

import numpy as np

from phage_annotator.cache.array_pool import ArrayPool, PoolConfig
import phage_annotator.algorithms.density_infer as density_infer
import phage_annotator.algorithms.deepstorm_infer as deepstorm_infer


class TestArrayPool(unittest.TestCase):
    """Tests for ArrayPool behavior."""

    def test_acquire_release_reuse(self):
        """Test that released arrays can be reused."""
        pool = ArrayPool(PoolConfig(max_entries_per_key=1, max_entry_bytes=1024 * 1024))
        arr1 = pool.acquire((32, 32), np.float32, fill=1.0)
        pool.release(arr1)
        arr2 = pool.acquire((32, 32), np.float32, fill=0.0)
        self.assertIs(arr1, arr2)
        self.assertTrue(np.all(arr2 == 0.0))

    def test_release_oversize_ignored(self):
        """Test that oversized arrays are not pooled."""
        pool = ArrayPool(PoolConfig(max_entries_per_key=1, max_entry_bytes=16))
        arr = pool.acquire((32, 32), np.float32, fill=0.0)
        pool.release(arr)
        key = (arr.shape, arr.dtype)
        self.assertTrue(key not in pool._pool or len(pool._pool[key]) == 0)

    def test_clear_pool(self):
        """Test that clear removes cached arrays."""
        pool = ArrayPool(PoolConfig(max_entries_per_key=2, max_entry_bytes=1024 * 1024))
        arr1 = pool.acquire((16, 16), np.float32, fill=1.0)
        arr2 = pool.acquire((16, 16), np.float32, fill=2.0)
        pool.release(arr1)
        pool.release(arr2)
        pool.clear()
        self.assertEqual(pool._pool, {})

    def test_pool_stats_counts(self):
        """Test that pool stats track hits and misses."""
        pool = ArrayPool(PoolConfig(max_entries_per_key=1, max_entry_bytes=1024 * 1024))
        arr = pool.acquire((8, 8), np.float32, fill=0.0)
        pool.release(arr)
        pool.acquire((8, 8), np.float32, fill=0.0)
        stats = pool.stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)


class TestWeightWindowCaching(unittest.TestCase):
    """Tests for cached weight windows and masks."""

    def test_density_weight_window_cache(self):
        """Ensure density weight window is cached by tile/mode."""
        w1 = density_infer._weight_window(64, "weighted")
        w2 = density_infer._weight_window(64, "weighted")
        self.assertIs(w1, w2)

    def test_deepstorm_weight_mask_cache(self):
        """Ensure DeepStorm weight mask is cached by size."""
        m1 = deepstorm_infer._weight_mask(32, 32)
        m2 = deepstorm_infer._weight_mask(32, 32)
        self.assertIs(m1, m2)


if __name__ == "__main__":
    unittest.main()
