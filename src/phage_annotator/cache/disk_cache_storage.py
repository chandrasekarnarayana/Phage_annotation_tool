"""Extracted method group 1 for DiskCache."""

from __future__ import annotations

import hashlib
import logging
import pathlib
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import NamedTuple, Optional

import numpy as np

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    zstd = None
    HAS_ZSTD = False

logger = logging.getLogger(__name__)


class DiskCacheStats(NamedTuple):
    """Statistics for disk cache performance."""

    saves: int = 0
    loads: int = 0
    hits: int = 0
    misses: int = 0
    bytes_saved: int = 0
    bytes_loaded: int = 0
    current_size_bytes: int = 0
    async_pending: int = 0


@dataclass
class DiskCacheConfig:
    """Configuration for disk cache."""

    enabled: bool = True
    max_size_mb: int = 500
    cache_dir: Optional[pathlib.Path] = None
    zstd_level: int = 10
    async_workers: int = 2
    zstd_level_mean: int = 10
    zstd_level_std: int = 8
    zstd_level_float32: int = 10
    zstd_level_uint8: int = 6
    max_pending_saves: int = 8

    def __post_init__(self):
        """Fill in the default cache directory when not provided."""
        if self.cache_dir is None:
            self.cache_dir = pathlib.Path.home() / ".cache" / "phage_annotator"

    def get_zstd_level_for_key(self, key: tuple) -> int:
        """Return a compression level tuned for the cache key kind."""
        if len(key) < 2:
            return self.zstd_level
        kind = str(key[1]).lower()
        if "mean" in kind:
            return self.zstd_level_mean
        if "std" in kind:
            return self.zstd_level_std
        return self.zstd_level


class CompressedBuffer:
    """Wrapper for compressed data with lazy decompression."""

    def __init__(self, compressed_data: bytes, original_shape: tuple, dtype: np.dtype, serialized_size: int):
        """Store compressed data and metadata for later decompression."""
        self.compressed_data = compressed_data
        self.original_shape = original_shape
        self.dtype = dtype
        self.serialized_size = serialized_size
        self.compressed_size = len(compressed_data)

    def decompress_full(self) -> np.ndarray:
        """Decompress and deserialize the full array."""
        if not HAS_ZSTD:
            return pickle.loads(self.compressed_data)
        dctx = zstd.ZstdDecompressor()
        serialized = dctx.decompress(self.compressed_data)
        return pickle.loads(serialized)

    def decompress_region(self, row_slice: Optional[slice] = None, col_slice: Optional[slice] = None) -> np.ndarray:
        """Decompress the full array and return the requested row/column region."""
        full_array = self.decompress_full()
        if row_slice is not None or col_slice is not None:
            rows = row_slice if row_slice is not None else slice(None)
            cols = col_slice if col_slice is not None else slice(None)
            if len(full_array.shape) == 2:
                return full_array[rows, cols]
            if len(full_array.shape) == 3:
                return full_array[:, rows, cols]
        return full_array

    def get_compression_ratio(self) -> float:
        """Return the uncompressed/compressed size ratio."""
        if self.compressed_size == 0:
            return 1.0
        return self.serialized_size / self.compressed_size




class DiskCacheStorageMixin:
    """Method group 1 extracted from DiskCache."""

    def __init__(self, config: Optional[DiskCacheConfig] = None):
        """Initialize disk cache.
        
        Args:
            config: DiskCacheConfig instance. If None, uses defaults.
        """
        self.config = config or DiskCacheConfig()
        self.stats = DiskCacheStats()
        self._index: dict[str, tuple[int, int]] = {}  # key -> (original_size, compressed_size)
        self._lru_order: list[str] = []  # Track access order for eviction
        self._lock = threading.RLock()  # P7a: Thread-safe stats/index updates
        
        # P7a: Async I/O with ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=self.config.async_workers, thread_name_prefix="disk_cache")
        self._pending_saves: dict[str, Future] = {}  # Track pending async saves
        
        if not HAS_ZSTD:
            if self.config.enabled:
                logger.warning("zstandard not installed; disk cache disabled")
            self.config.enabled = False
        
        # Create cache directory if enabled
        if self.config.enabled:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Disk cache initialized: {self.config.cache_dir} (level={self.config.zstd_level})")
    def __del__(self):
        """Graceful shutdown of executor."""
        try:
            self.shutdown(wait=True)
        except:
            pass
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the async executor (P7a).
        
        Args:
            wait: If True, wait for pending saves to complete.
        """
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=wait)
            if wait:
                logger.debug(f"Disk cache executor shutdown complete")
    def _wait_pending_saves(self, timeout: float = 5.0) -> int:
        """Wait for all pending async saves to complete (P7a).
        
        Args:
            timeout: Maximum time to wait per save.
        
        Returns:
            Number of saves waited for.
        """
        with self._lock:
            completed = 0
            failed_keys = []
            
            for filename, future in list(self._pending_saves.items()):
                try:
                    future.result(timeout=timeout)
                    completed += 1
                except Exception as e:
                    logger.warning(f"Pending save failed for {filename}: {e}")
                    failed_keys.append(filename)
            
            # Clean up failed entries
            for filename in failed_keys:
                self._pending_saves.pop(filename, None)
            
            return completed
    def _key_to_filename(self, key: tuple) -> str:
        """Convert cache key to hex filename.
        
        Args:
            key: Tuple-based cache key (img_id, kind, bounds, etc.)
        
        Returns:
            Hex string suitable for filesystem.
        """
        key_str = str(key)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return key_hash
    def save(self, key: tuple, data: np.ndarray, wait: bool = False) -> bool:
        """Save array to disk cache asynchronously with compression (P7a).
        
        Args:
            key: Cache key (img_id, kind, bounds, etc.)
            data: Numpy array to save
            wait: If True, wait for async save to complete before returning.
        
        Returns:
            True if save queued/completed successfully, False if size exceeded or error.
        """
        if not self.config.enabled:
            return False
        
        try:
            with self._lock:
                self._reap_completed_saves_locked()
                if len(self._pending_saves) >= max(1, int(self.config.max_pending_saves)):
                    logger.debug("Disk cache save skipped: pending queue saturated")
                    self.stats = DiskCacheStats(
                        saves=self.stats.saves,
                        loads=self.stats.loads,
                        hits=self.stats.hits,
                        misses=self.stats.misses,
                        bytes_saved=self.stats.bytes_saved,
                        bytes_loaded=self.stats.bytes_loaded,
                        current_size_bytes=self.stats.current_size_bytes,
                        async_pending=len(self._pending_saves),
                    )
                    return False

            # Serialize array
            serialized = pickle.dumps(data)
            
            # Compress with P7d: per-key tuning for different data types
            if HAS_ZSTD:
                zstd_level = self.config.get_zstd_level_for_key(key)
                cctx = zstd.ZstdCompressor(level=zstd_level)
                compressed = cctx.compress(serialized)
            else:
                compressed = serialized
            
            # Check if adding this would exceed budget
            new_size = self.stats.current_size_bytes + len(compressed)
            if new_size > self.config.max_size_mb * 1024 * 1024:
                # Evict oldest items until we have space
                self._evict_until_space(len(compressed))
            
            filename = self._key_to_filename(key)
            
            # P7a: Queue async save (non-blocking)
            future = self._executor.submit(
                self._async_save_impl,
                filename, key, compressed, len(serialized), len(compressed)
            )
            future.add_done_callback(lambda _future, fname=filename: self._on_save_done(fname))
            
            with self._lock:
                self._pending_saves[filename] = future
                # Update stats immediately (before actual write)
                self.stats = DiskCacheStats(
                    saves=self.stats.saves + 1,
                    loads=self.stats.loads,
                    hits=self.stats.hits,
                    misses=self.stats.misses,
                    bytes_saved=self.stats.bytes_saved + len(serialized),
                    bytes_loaded=self.stats.bytes_loaded,
                    current_size_bytes=self.stats.current_size_bytes + len(compressed),
                    async_pending=len(self._pending_saves),
                )
                
                # Track in index
                self._index[filename] = (len(serialized), len(compressed))
                self._lru_order.append(filename)
            
            # Optionally wait for save to complete
            if wait:
                future.result(timeout=5.0)
                with self._lock:
                    self._pending_saves.pop(filename, None)
            
            return True
        
        except Exception as e:
            logger.warning(f"Disk cache save error: {e}")
            return False
