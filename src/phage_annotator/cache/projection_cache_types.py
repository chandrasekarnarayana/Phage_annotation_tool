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

CacheKey = Tuple[int, str, Tuple[float, float, float, float], int, int, int]
PyramidKey = Tuple[int, str, int, int, Tuple[float, float, float, float], int, int]


@dataclass



class CacheItem:
    """Cached projection and its byte size."""

    data: np.ndarray
    nbytes: int

class CacheTelemetry:
    """Telemetry tracking for cache performance."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    bytes_evicted: int = 0
    pyramid_evictions: int = 0
    warning_at_90_percent_issued: bool = False
    hits_this_cycle: int = 0
    misses_this_cycle: int = 0
    evictions_this_cycle: int = 0
    
    def hit_ratio(self) -> float:
        """Return cache hit ratio (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def is_thrashing(self) -> bool:
        """Detect cache thrashing: evictions > 2x hits in current cycle."""
        if self.hits_this_cycle == 0:
            return False
        return self.evictions_this_cycle > 2 * self.hits_this_cycle
    
    def reset_cycle(self) -> None:
        """Reset per-cycle counters (called each monitoring tick)."""
        self.hits_this_cycle = 0
        self.misses_this_cycle = 0
        self.evictions_this_cycle = 0
    
    def reset(self) -> None:
        """Reset all telemetry counters."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.bytes_evicted = 0
        self.pyramid_evictions = 0
        self.warning_at_90_percent_issued = False
        self.reset_cycle()
