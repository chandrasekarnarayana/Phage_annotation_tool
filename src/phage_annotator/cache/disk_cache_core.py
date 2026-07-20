"""Disk-based cache for evicted projection tiles."""

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
    HAS_ZSTD = False

logger = logging.getLogger(__name__)

from phage_annotator.cache.disk_cache_types import DiskCacheConfig, DiskCacheStats
from phage_annotator.cache.disk_cache_io import DiskCacheIOMixin
from phage_annotator.cache.disk_cache_eviction import DiskCacheEvictionMixin


class DiskCache(DiskCacheIOMixin, DiskCacheEvictionMixin):
    """Disk-based LRU cache for projection tiles with async I/O.
    
    When tiles are evicted from memory cache, they are compressed and
    stored on disk asynchronously (P7a). On cache miss, we check disk 
    before recomputing.
    
    P7a: Async saves prevent blocking during memory eviction.
    P7b: Supports lazy decompression for region-aware loading.
    P7d: Configurable compression level for compression/speed trade-offs.
    
    Attributes:
        config: DiskCacheConfig with size limits and location
        stats: DiskCacheStats tracking performance metrics
    """
    
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
