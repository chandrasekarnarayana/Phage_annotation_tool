"""Disk-cache eviction and statistics operations."""

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

class DiskCacheEvictionMixin:
    def _evict_until_space(self, needed_bytes: int) -> None:
        """Remove oldest items from disk until space available (thread-safe).
        
        Args:
            needed_bytes: Number of bytes needed for new entry.
        """
        with self._lock:
            while self.stats.current_size_bytes + needed_bytes > self.config.max_size_mb * 1024 * 1024:
                if not self._lru_order:
                    break
                
                # Remove oldest
                oldest = self._lru_order.pop(0)
                tile_path = self.config.cache_dir / oldest
                
                try:
                    if tile_path.exists():
                        size = tile_path.stat().st_size
                        tile_path.unlink()
                        
                        # Update stats
                        self.stats = DiskCacheStats(
                            saves=self.stats.saves,
                            loads=self.stats.loads,
                            hits=self.stats.hits,
                            misses=self.stats.misses,
                            bytes_saved=self.stats.bytes_saved,
                            bytes_loaded=self.stats.bytes_loaded,
                            current_size_bytes=max(0, self.stats.current_size_bytes - size),
                            async_pending=len(self._pending_saves),
                        )
                    
                    if oldest in self._index:
                        del self._index[oldest]
                
                except Exception as e:
                    logger.warning(f"Error evicting {oldest}: {e}")
    
    def clear(self) -> None:
        """Clear all items from disk cache (thread-safe)."""
        # Wait for pending saves first
        self._wait_pending_saves()
        
        try:
            with self._lock:
                for filepath in self.config.cache_dir.glob("*"):
                    if filepath.is_file() and filepath.name != "tiles.db":
                        filepath.unlink()
                
                self._index.clear()
                self._lru_order.clear()
                
                self.stats = DiskCacheStats(
                    saves=self.stats.saves,
                    loads=self.stats.loads,
                    hits=self.stats.hits,
                    misses=self.stats.misses,
                    bytes_saved=self.stats.bytes_saved,
                    bytes_loaded=self.stats.bytes_loaded,
                    current_size_bytes=0,
                    async_pending=0,
                )
        except Exception as e:
            logger.warning(f"Error clearing disk cache: {e}")
    
    def get_compression_ratio(self) -> float:
        """Calculate average compression ratio (thread-safe).
        
        Returns:
            Ratio of original size to compressed size. >1.0 means compression works.
        """
        with self._lock:
            if not self._index:
                return 1.0
            
            total_original = sum(orig for orig, _ in self._index.values())
            total_compressed = sum(comp for _, comp in self._index.values())
            
            if total_compressed == 0:
                return 1.0
            
            return total_original / total_compressed
    
    def hit_rate(self) -> float:
        """Calculate cache hit rate (thread-safe).
        
        Returns:
            Fraction of loads that were hits (0.0 to 1.0).
        """
        total = self.stats.hits + self.stats.misses
        if total == 0:
            return 0.0
        
        return self.stats.hits / total
