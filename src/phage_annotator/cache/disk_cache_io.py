"""Disk-cache save/load I/O operations."""

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

from phage_annotator.cache.disk_cache_types import CompressedBuffer, DiskCacheStats


class DiskCacheIOMixin:
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
    
    def _async_save_impl(self, filename: str, key: tuple, compressed: bytes,
                         original_size: int, compressed_size: int) -> None:
        """Background worker for async saves (P7a).
        
        Args:
            filename: Hashed filename for tile
            key: Original cache key
            compressed: Compressed bytes
            original_size: Size before compression
            compressed_size: Size after compression
        """
        try:
            tile_path = self.config.cache_dir / filename
            
            # Write compressed data to disk
            with open(tile_path, "wb") as f:
                f.write(compressed)
            
            logger.debug(f"Async disk save completed: {filename}")
        
        except Exception as e:
            logger.error(f"Async save failed for {filename}: {e}")
            # Remove from index on failure
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
                async_pending=len(self._pending_saves),
            )

    def _reap_completed_saves_locked(self) -> None:
        """Remove completed save futures while holding the cache lock."""
        for filename, future in list(self._pending_saves.items()):
            if not future.done():
                continue
            self._pending_saves.pop(filename, None)
    
    def load(self, key: tuple, lazy: bool = False) -> Optional[np.ndarray | CompressedBuffer]:
        """Load array from disk cache with decompression (P7b).
        
        Args:
            key: Cache key (img_id, kind, bounds, etc.)
            lazy: If True, return CompressedBuffer for lazy decompression.
                  If False, return decompressed numpy array.
        
        Returns:
            Numpy array if lazy=False, CompressedBuffer if lazy=True,
            or None if not found.
        """
        if not self.config.enabled:
            return None
        
        try:
            filename = self._key_to_filename(key)
            
            # P7a: Wait for pending save of this specific key before loading
            if filename in self._pending_saves:
                try:
                    self._pending_saves[filename].result(timeout=5.0)
                    with self._lock:
                        self._pending_saves.pop(filename, None)
                except Exception as e:
                    logger.warning(f"Pending save failed for {filename}: {e}")
                    return None
            
            with self._lock:
                # Check if tile exists on disk
                if filename not in self._index:
                    self.stats = DiskCacheStats(
                        saves=self.stats.saves,
                        loads=self.stats.loads,
                        hits=self.stats.hits,
                        misses=self.stats.misses + 1,
                        bytes_saved=self.stats.bytes_saved,
                        bytes_loaded=self.stats.bytes_loaded,
                        current_size_bytes=self.stats.current_size_bytes,
                        async_pending=len(self._pending_saves),
                    )
                    return None
            
            tile_path = self.config.cache_dir / filename
            
            # Read compressed data
            with open(tile_path, "rb") as f:
                compressed = f.read()
            
            original_size, _ = self._index.get(filename, (0, 0))
            
            # P7b: Return CompressedBuffer if lazy decompression requested
            if lazy:
                # Infer shape/dtype from metadata (approximate)
                buffer = CompressedBuffer(
                    compressed_data=compressed,
                    original_shape=(0, 0),  # Unknown without full decompression
                    dtype=np.float32,
                    serialized_size=original_size
                )
                
                with self._lock:
                    self.stats = DiskCacheStats(
                        saves=self.stats.saves,
                        loads=self.stats.loads + 1,
                        hits=self.stats.hits + 1,
                        misses=self.stats.misses,
                        bytes_saved=self.stats.bytes_saved,
                        bytes_loaded=self.stats.bytes_loaded + original_size,
                        current_size_bytes=self.stats.current_size_bytes,
                        async_pending=len(self._pending_saves),
                    )
                
                logger.debug(f"Lazy load for {filename}: {buffer.get_compression_ratio():.2f}× ratio")
                return buffer
            
            # Full decompression (default path)
            if HAS_ZSTD:
                dctx = zstd.ZstdDecompressor()
                serialized = dctx.decompress(compressed)
            else:
                serialized = compressed
            
            # Deserialize
            data = pickle.loads(serialized)
            
            # Update stats and LRU order (thread-safe)
            with self._lock:
                self.stats = DiskCacheStats(
                    saves=self.stats.saves,
                    loads=self.stats.loads + 1,
                    hits=self.stats.hits + 1,
                    misses=self.stats.misses,
                    bytes_saved=self.stats.bytes_saved,
                    bytes_loaded=self.stats.bytes_loaded + original_size,
                    current_size_bytes=self.stats.current_size_bytes,
                    async_pending=len(self._pending_saves),
                )
                
                # Update LRU order
                if filename in self._lru_order:
                    self._lru_order.remove(filename)
                self._lru_order.append(filename)
            
            return data
        
        except Exception as e:
            logger.warning(f"Disk cache load error: {e}")
            return None
