"""Projection LRU cache with a memory budget and eviction telemetry.

This cache stores computed projection arrays keyed by image id, projection
type, crop rectangle, and current T/Z selection. It tracks approximate byte
usage and evicts least-recently-used items when over budget. Pyramid levels
are cached separately and evicted first to preserve primary projections.

P4.3 Enhancement: Cache eviction telemetry tracks:
  - Hit/miss ratios per image and projection type
  - 90% budget warnings logged and notified via toast
  - Eviction counts and reclaimed memory
  - Performance metrics for diagnostic logging

P6: Disk cache integration:
  - Evicted items saved to compressed disk cache (Zstd)
  - On cache miss, check disk cache before returning None
  - Enables fast re-browsing of distant FOVs without reloading
"""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phage_annotator.cache.disk_cache import CompressedBuffer, DiskCache
    from phage_annotator.config.settings import ComponentMemoryBudget

logger = logging.getLogger(__name__)

from phage_annotator.cache.projection_cache_fov import ProjectionCacheFovMixin
from phage_annotator.cache.projection_cache_eviction import ProjectionCacheEvictionMixin
from phage_annotator.cache.projection_cache_types import CacheItem, CacheTelemetry

CacheKey = Tuple[int, str, Tuple[float, float, float, float], int, int, int]
PyramidKey = Tuple[int, str, int, int, Tuple[float, float, float, float], int, int]


@dataclass





class ProjectionCache(ProjectionCacheFovMixin, ProjectionCacheEvictionMixin):
    """LRU cache for projection arrays keyed by image/projection/crop/selection.

    Notes
    -----
    - Items store numpy arrays only; no GUI state is retained.
    - Budget is defined in MB and enforced on insert.
    - P4.3: Tracks hit/miss ratios and 90% budget warnings for telemetry.
    - P6: Optional disk cache for fast re-browsing of evicted tiles.
    """

    def __init__(self, max_mb: int = 1024, disk_cache: Optional[DiskCache] = None,
                 component_budget: Optional[ComponentMemoryBudget] = None) -> None:
        """Document the init flow."""
        self._items: "OrderedDict[CacheKey, CacheItem]" = OrderedDict()
        self._pyramid_items: "OrderedDict[PyramidKey, CacheItem]" = OrderedDict()
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._total_bytes = 0
        self._telemetry = CacheTelemetry()
        self._warning_callback: Optional[Callable[[str], None]] = None  # For toast notifications
        self._disk_cache = disk_cache  # Optional disk cache (P6)
        self._component_budget = component_budget  # P7e: Per-component memory tracking
        
        # P7e: Component-level tracking
        self._component_bytes = {
            'projection_main': 0,  # Primary projections
            'projection_pyramid': 0,  # LOD pyramid levels
        }
        # Phase η: Per-modality cache tracking
        self._modality_bytes_main: dict[int, int] = {}
        self._modality_bytes_pyramid: dict[int, int] = {}
        self._modality_count = 1

    def set_budget_mb(self, max_mb: int) -> None:
        """Update the cache budget in MB and evict if needed."""
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._telemetry.warning_at_90_percent_issued = False  # Reset warning
        self._evict_if_needed()

    def set_modality_count(self, count: int) -> None:
        """Set the number of modalities for per-modality cache budgets."""
        self._modality_count = max(1, int(count))
        self._evict_if_needed()

    def set_warning_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """Set callback for 90% budget warnings (e.g., toast notification)."""
        self._warning_callback = callback

    def set_disk_cache(self, disk_cache: Optional[DiskCache]) -> None:
        """Set or update the disk cache instance (P6)."""
        self._disk_cache = disk_cache

    def get(self, key: CacheKey) -> Optional[np.ndarray]:
        """Return a cached array and mark it as most-recently-used.
        
        P6: Falls back to disk cache if memory cache miss.
        """
        item = self._items.get(key)
        if item is None:
            # Check disk cache on miss (P6)
            if self._disk_cache:
                disk_data = self._disk_cache.load(key)
                if disk_data is not None:
                    # Disk hit: reload to memory for fast access
                    self.put(key, disk_data)
                    self._telemetry.hits += 1
                    self._telemetry.hits_this_cycle += 1
                    logger.debug(f"[P6] Disk cache hit for {key}")
                    return disk_data
            
            self._telemetry.misses += 1
            self._telemetry.misses_this_cycle += 1
            return None
        
        self._telemetry.hits += 1
        self._telemetry.hits_this_cycle += 1
        self._items.move_to_end(key)
        return item.data
    
    def get_lazy(self, key: CacheKey) -> Optional[CompressedBuffer]:
        """Return a lazy-decompression buffer from disk cache (P7b).
        
        P7b: Returns CompressedBuffer for region-aware lazy decompression.
        If not in disk cache, returns None (doesn't fall back to full decompression).
        
        Returns:
            CompressedBuffer with compressed data, or None if not found.
        """
        if self._disk_cache is None:
            return None
        
        # Try to get compressed buffer from disk cache (P7b)
        buffer = self._disk_cache.load(key, lazy=True)
        if buffer is not None:
            self._telemetry.hits += 1
            self._telemetry.hits_this_cycle += 1
            logger.debug(f"[P7b] Lazy disk cache hit for {key}, ratio={buffer.get_compression_ratio():.2f}×")
            return buffer
        
        self._telemetry.misses += 1
        self._telemetry.misses_this_cycle += 1
        return None

    def put(self, key: CacheKey, data: np.ndarray) -> None:
        """Insert/update a cached array and enforce the memory budget."""
        nbytes = int(data.nbytes)
        modality_idx = int(key[-1])
        existing = self._items.pop(key, None)
        if existing is not None:
            self._total_bytes -= existing.nbytes
            self._component_bytes['projection_main'] -= existing.nbytes
            self._modality_bytes_main[modality_idx] = (
                self._modality_bytes_main.get(modality_idx, 0) - existing.nbytes
            )
        self._items[key] = CacheItem(data=data, nbytes=nbytes)
        self._total_bytes += nbytes
        self._component_bytes['projection_main'] += nbytes  # P7e: Track component usage
        self._modality_bytes_main[modality_idx] = (
            self._modality_bytes_main.get(modality_idx, 0) + nbytes
        )
        self._evict_if_needed()

    def get_pyramid(self, key: PyramidKey) -> Optional[np.ndarray]:
        """Return a cached pyramid level and mark it as most-recently-used."""
        item = self._pyramid_items.get(key)
        if item is None:
            return None
        self._pyramid_items.move_to_end(key)
        return item.data

    def put_pyramid(self, key: PyramidKey, data: np.ndarray) -> None:
        """Insert/update a cached pyramid level with lower eviction priority."""
        nbytes = int(data.nbytes)
        modality_idx = int(key[-1])
        existing = self._pyramid_items.pop(key, None)
        if existing is not None:
            self._total_bytes -= existing.nbytes
            self._component_bytes['projection_pyramid'] -= existing.nbytes
            self._modality_bytes_pyramid[modality_idx] = (
                self._modality_bytes_pyramid.get(modality_idx, 0) - existing.nbytes
            )
        self._pyramid_items[key] = CacheItem(data=data, nbytes=nbytes)
        self._total_bytes += nbytes
        self._component_bytes['projection_pyramid'] += nbytes  # P7e: Track component usage
        self._modality_bytes_pyramid[modality_idx] = (
            self._modality_bytes_pyramid.get(modality_idx, 0) + nbytes
        )
        self._evict_if_needed()

    def invalidate_image(self, image_id: int) -> None:
        """Remove all cached entries for a given image id."""
        for cache_key in [k for k in self._items.keys() if k[0] == image_id]:
            item = self._items.pop(cache_key, None)
            if item is not None:
                self._total_bytes -= item.nbytes
                self._component_bytes['projection_main'] -= item.nbytes
                modality_idx = int(cache_key[-1])
                self._modality_bytes_main[modality_idx] = (
                    self._modality_bytes_main.get(modality_idx, 0) - item.nbytes
                )
        for pyramid_key in [k for k in self._pyramid_items.keys() if k[0] == image_id]:
            item = self._pyramid_items.pop(pyramid_key, None)
            if item is not None:
                self._total_bytes -= item.nbytes
                self._component_bytes['projection_pyramid'] -= item.nbytes
                modality_idx = int(pyramid_key[-1])
                self._modality_bytes_pyramid[modality_idx] = (
                    self._modality_bytes_pyramid.get(modality_idx, 0) - item.nbytes
                )

    def clear(self) -> None:
        """Clear all cached items and reset byte tracking."""
        self._items.clear()
        self._pyramid_items.clear()
        self._total_bytes = 0
        self._component_bytes['projection_main'] = 0
        self._component_bytes['projection_pyramid'] = 0
        self._modality_bytes_main.clear()
        self._modality_bytes_pyramid.clear()

    def stats(self) -> Tuple[int, int]:
        """Return (mb_used, item_count) for UI/status display."""
        mb = int(math.ceil(self._total_bytes / (1024 * 1024))) if self._total_bytes else 0
        return mb, len(self._items) + len(self._pyramid_items)

    def telemetry(self) -> CacheTelemetry:
        """Return telemetry data for diagnostics."""
        return self._telemetry
