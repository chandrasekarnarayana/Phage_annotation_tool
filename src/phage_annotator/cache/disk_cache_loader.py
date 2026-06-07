"""Async save completion and load methods for disk cache."""

from __future__ import annotations

import logging
import pickle
from typing import Optional

import numpy as np
from phage_annotator.cache.disk_cache_eviction import DiskCacheEvictionMixin
from phage_annotator.cache.disk_cache_storage import DiskCacheStorageMixin
from phage_annotator.cache.projection_cache_base import ProjectionCacheBase
from phage_annotator.cache.projection_cache_data import ProjectionCacheDataMixin


logger = logging.getLogger(__name__)


class DiskCacheLoader:
    """Load and async-save completion methods for disk cache."""

    def _async_save_impl(self, filename: str, key: tuple, compressed: bytes, original_size: int, compressed_size: int) -> None:
        """Write compressed cache data in a background worker."""
        try:
            tile_path = self.config.cache_dir / filename
            with open(tile_path, "wb") as f:
                f.write(compressed)
            logger.debug(f"Async disk save completed: {filename}")
        except Exception as e:
            logger.error(f"Async save failed for {filename}: {e}")
            with self._lock:
                self._index.pop(filename, None)
                if filename in self._lru_order:
                    self._lru_order.remove(filename)

    def _on_save_done(self, filename: str) -> None:
        """Release completed future bookkeeping for async disk saves."""
        with self._lock:
            self._pending_saves.pop(filename, None)
            self.stats = DiskCacheStats(
                saves=self.stats.saves,
                loads=self.stats.loads,
                hits=self.stats.hits,
                misses=self.stats.misses,
                bytes_saved=self.stats.bytes_saved,
                bytes_loaded=self.stats.bytes_loaded,
                current_size_bytes=self.stats.current_size_bytes,
                async_pending=len(self._pending_saves))

    def _reap_completed_saves_locked(self) -> None:
        """Remove completed save futures while holding the cache lock."""
        for filename, future in list(self._pending_saves.items()):
            if future.done():
                self._pending_saves.pop(filename, None)

    def load(self, key: tuple, lazy: bool = False) -> Optional[np.ndarray]:
        """Load an array or lazy compressed buffer from disk cache."""
        if not self.config.enabled:
            return None
        try:
            filename = self._key_to_filename(key)
            if filename in self._pending_saves:
                try:
                    self._pending_saves[filename].result(timeout=5.0)
                    with self._lock:
                        self._pending_saves.pop(filename, None)
                except Exception as e:
                    logger.warning(f"Pending save failed for {filename}: {e}")
                    return None
            with self._lock:
                if filename not in self._index:
                    self.stats = DiskCacheStats(
                        saves=self.stats.saves,
                        loads=self.stats.loads,
                        hits=self.stats.hits,
                        misses=self.stats.misses + 1,
                        bytes_saved=self.stats.bytes_saved,
                        bytes_loaded=self.stats.bytes_loaded,
                        current_size_bytes=self.stats.current_size_bytes,
                        async_pending=len(self._pending_saves))
                    return None
            tile_path = self.config.cache_dir / filename
            with open(tile_path, "rb") as f:
                compressed = f.read()
            original_size, _ = self._index.get(filename, (0, 0))
            if lazy:
                buffer = (compressed, (0, 0), np.float32, original_size)
                self._record_load_hit(original_size)
                logger.debug(f"Lazy load for {filename}: {buffer.get_compression_ratio():.2f}x ratio")
                return buffer
            serialized = zstd.ZstdDecompressor().decompress(compressed) if HAS_ZSTD else compressed
            data = pickle.loads(serialized)
            self._record_load_hit(original_size)
            with self._lock:
                if filename in self._lru_order:
                    self._lru_order.remove(filename)
                self._lru_order.append(filename)
            return data
        except Exception as e:
            logger.warning(f"Disk cache load error: {e}")
            return None

    def _record_load_hit(self, original_size: int) -> None:
        """Update stats after a successful disk-cache load."""
        with self._lock:
            self.stats = DiskCacheStats(
                saves=self.stats.saves,
                loads=self.stats.loads + 1,
                hits=self.stats.hits + 1,
                misses=self.stats.misses,
                bytes_saved=self.stats.bytes_saved,
                bytes_loaded=self.stats.bytes_loaded + original_size,
                current_size_bytes=self.stats.current_size_bytes,
                async_pending=len(self._pending_saves))
