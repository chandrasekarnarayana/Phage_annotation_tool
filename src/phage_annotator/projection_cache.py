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
"""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

CacheKey = Tuple[int, str, Tuple[float, float, float, float], int, int]
PyramidKey = Tuple[int, str, int, int, Tuple[float, float, float, float], int]


@dataclass
class CacheItem:
    """Cached projection and its byte size."""

    data: np.ndarray
    nbytes: int


@dataclass
class CacheTelemetry:
    """Telemetry tracking for cache performance."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    bytes_evicted: int = 0
    pyramid_evictions: int = 0
    warning_at_90_percent_issued: bool = False
    
    def hit_ratio(self) -> float:
        """Return cache hit ratio (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def reset(self) -> None:
        """Reset telemetry counters."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.bytes_evicted = 0
        self.pyramid_evictions = 0
        self.warning_at_90_percent_issued = False


class ProjectionCache:
    """LRU cache for projection arrays keyed by image/projection/crop/selection.

    Notes
    -----
    - Items store numpy arrays only; no GUI state is retained.
    - Budget is defined in MB and enforced on insert.
    - P4.3: Tracks hit/miss ratios and 90% budget warnings for telemetry.
    """

    def __init__(self, max_mb: int = 1024) -> None:
        self._items: "OrderedDict[CacheKey, CacheItem]" = OrderedDict()
        self._pyramid_items: "OrderedDict[PyramidKey, CacheItem]" = OrderedDict()
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._total_bytes = 0
        self._telemetry = CacheTelemetry()
        self._warning_callback: Optional[callable] = None  # For toast notifications

    def set_budget_mb(self, max_mb: int) -> None:
        """Update the cache budget in MB and evict if needed."""
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._telemetry.warning_at_90_percent_issued = False  # Reset warning
        self._evict_if_needed()

    def set_warning_callback(self, callback: Optional[callable]) -> None:
        """Set callback for 90% budget warnings (e.g., toast notification)."""
        self._warning_callback = callback

    def get(self, key: CacheKey) -> Optional[np.ndarray]:
        """Return a cached array and mark it as most-recently-used."""
        item = self._items.get(key)
        if item is None:
            self._telemetry.misses += 1
            return None
        
        self._telemetry.hits += 1
        self._items.move_to_end(key)
        return item.data

    def put(self, key: CacheKey, data: np.ndarray) -> None:
        """Insert/update a cached array and enforce the memory budget."""
        nbytes = int(data.nbytes)
        existing = self._items.pop(key, None)
        if existing is not None:
            self._total_bytes -= existing.nbytes
        self._items[key] = CacheItem(data=data, nbytes=nbytes)
        self._total_bytes += nbytes
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
        existing = self._pyramid_items.pop(key, None)
        if existing is not None:
            self._total_bytes -= existing.nbytes
        self._pyramid_items[key] = CacheItem(data=data, nbytes=nbytes)
        self._total_bytes += nbytes
        self._evict_if_needed()

    def invalidate_image(self, image_id: int) -> None:
        """Remove all cached entries for a given image id."""
        for cache_key in [k for k in self._items.keys() if k[0] == image_id]:
            item = self._items.pop(cache_key, None)
            if item is not None:
                self._total_bytes -= item.nbytes
        for pyramid_key in [k for k in self._pyramid_items.keys() if k[0] == image_id]:
            item = self._pyramid_items.pop(pyramid_key, None)
            if item is not None:
                self._total_bytes -= item.nbytes

    def clear(self) -> None:
        """Clear all cached items and reset byte tracking."""
        self._items.clear()
        self._pyramid_items.clear()
        self._total_bytes = 0

    def stats(self) -> Tuple[int, int]:
        """Return (mb_used, item_count) for UI/status display."""
        mb = int(math.ceil(self._total_bytes / (1024 * 1024))) if self._total_bytes else 0
        return mb, len(self._items) + len(self._pyramid_items)

    def telemetry(self) -> CacheTelemetry:
        """Return telemetry data for diagnostics."""
        return self._telemetry

    def _evict_if_needed(self) -> None:
        """Evict least-recently-used items until within budget."""
        # Check for 90% budget threshold and warn
        if not self._telemetry.warning_at_90_percent_issued:
            percent = (self._total_bytes / self._max_bytes * 100) if self._max_bytes > 0 else 0
            if percent >= 90:
                self._telemetry.warning_at_90_percent_issued = True
                mb_used = int(math.ceil(self._total_bytes / (1024 * 1024)))
                mb_budget = int(self._max_bytes / (1024 * 1024))
                
                msg = f"Cache at {percent:.1f}% of budget ({mb_used}/{mb_budget} MB)"
                logger.warning(f"Cache eviction telemetry: {msg}")
                
                # Trigger toast notification if callback is set
                if self._warning_callback:
                    try:
                        self._warning_callback(msg)
                    except Exception as e:
                        logger.debug(f"Warning callback error: {e}")
        
        # Evict until within budget
        while self._total_bytes > self._max_bytes and (self._pyramid_items or self._items):
            if self._pyramid_items:
                _, item = self._pyramid_items.popitem(last=False)
                self._total_bytes -= item.nbytes
                self._telemetry.pyramid_evictions += 1
                self._telemetry.bytes_evicted += item.nbytes
                continue
            if self._items:
                _, item = self._items.popitem(last=False)
                self._total_bytes -= item.nbytes
                self._telemetry.evictions += 1
                self._telemetry.bytes_evicted += item.nbytes
                continue
        
        # Log eviction summary if needed
        if self._telemetry.evictions > 0 or self._telemetry.pyramid_evictions > 0:
            mb_reclaimed = int(math.ceil(self._telemetry.bytes_evicted / (1024 * 1024)))
            logger.debug(
                f"Cache evicted {self._telemetry.evictions} items + "
                f"{self._telemetry.pyramid_evictions} pyramid levels, "
                f"reclaimed {mb_reclaimed} MB"
            )

