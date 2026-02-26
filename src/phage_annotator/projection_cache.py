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
from typing import Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phage_annotator.disk_cache import DiskCache, CompressedBuffer
    from phage_annotator.config import ComponentMemoryBudget

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


class ProjectionCache:
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
        self._items: "OrderedDict[CacheKey, CacheItem]" = OrderedDict()
        self._pyramid_items: "OrderedDict[PyramidKey, CacheItem]" = OrderedDict()
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._total_bytes = 0
        self._telemetry = CacheTelemetry()
        self._warning_callback: Optional[callable] = None  # For toast notifications
        self._disk_cache = disk_cache  # Optional disk cache (P6)
        self._component_budget = component_budget  # P7e: Per-component memory tracking
        
        # P7e: Component-level tracking
        self._component_bytes = {
            'projection_main': 0,  # Primary projections
            'projection_pyramid': 0,  # LOD pyramid levels
        }

    def set_budget_mb(self, max_mb: int) -> None:
        """Update the cache budget in MB and evict if needed."""
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._telemetry.warning_at_90_percent_issued = False  # Reset warning
        self._evict_if_needed()

    def set_warning_callback(self, callback: Optional[callable]) -> None:
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
        existing = self._items.pop(key, None)
        if existing is not None:
            self._total_bytes -= existing.nbytes
            self._component_bytes['projection_main'] -= existing.nbytes
        self._items[key] = CacheItem(data=data, nbytes=nbytes)
        self._total_bytes += nbytes
        self._component_bytes['projection_main'] += nbytes  # P7e: Track component usage
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
            self._component_bytes['projection_pyramid'] -= existing.nbytes
        self._pyramid_items[key] = CacheItem(data=data, nbytes=nbytes)
        self._total_bytes += nbytes
        self._component_bytes['projection_pyramid'] += nbytes  # P7e: Track component usage
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
    
    def get_adjacent_fov_ids(self, current_image_id: int, fov_grid_cols: int,
                            fov_grid_rows: int) -> list[int]:
        """Detect adjacent FOVs in grid for predictive prefetch (P7c).
        
        Given a current FOV index in a grid layout, returns indices of adjacent
        FOVs (up, down, left, right) that are candidates for low-priority prefetch.
        
        Args:
            current_image_id: Index of current FOV (0-indexed)
            fov_grid_cols: Number of columns in FOV grid
            fov_grid_rows: Number of rows in FOV grid
        
        Returns:
            List of adjacent FOV indices (max 4 for cardinal directions).
        """
        if fov_grid_cols <= 0 or fov_grid_rows <= 0:
            return []  # Grid not configured
        
        total_fovs = fov_grid_cols * fov_grid_rows
        if current_image_id < 0 or current_image_id >= total_fovs:
            return []  # Invalid FOV index
        
        # Convert linear index to (row, col)
        row = current_image_id // fov_grid_cols
        col = current_image_id % fov_grid_cols
        
        adjacent = []
        
        # Check all 4 cardinal directions
        directions = [
            (row - 1, col, "up"),      # Up
            (row + 1, col, "down"),    # Down
            (row, col - 1, "left"),    # Left
            (row, col + 1, "right"),   # Right
        ]
        
        for adj_row, adj_col, direction in directions:
            if 0 <= adj_row < fov_grid_rows and 0 <= adj_col < fov_grid_cols:
                adj_id = adj_row * fov_grid_cols + adj_col
                adjacent.append(adj_id)
                logger.debug(f"Adjacent FOV {direction}: {adj_id}")
        
        return adjacent
    
    def should_prefetch_adjacent(self, current_image_id: int) -> bool:
        """Check if we should prefetch adjacent FOVs (P7c).
        
        Prefetch is enabled if:
        - Current cache usage is below 70% of budget (has room)
        - Not in memory pressure situation
        
        Args:
            current_image_id: Index of current FOV  
        
        Returns:
            True if prefetch is recommended, False if budget constrained.
        """
        cache_usage = self._total_bytes / self._max_bytes if self._max_bytes > 0 else 0.0
        
        # Disable prefetch if cache near capacity
        if cache_usage > 0.70:
            logger.debug(f"Prefetch disabled: cache at {cache_usage * 100:.1f}%")
            return False
        
        # Disable if currently thrashing
        if self._telemetry.is_thrashing():
            logger.debug("Prefetch disabled: cache thrashing detected")
            return False
        
        return True
    
    def get_component_usage(self, component: str) -> Tuple[int, int]:
        """Get memory usage for specific component (P7e).
        
        Args:
            component: One of 'projection_main', 'projection_pyramid'
        
        Returns:
            Tuple of (bytes_used, mb_used)
        """
        bytes_used = self._component_bytes.get(component, 0)
        mb_used = bytes_used // (1024 * 1024)
        return bytes_used, mb_used
    
    def get_component_budget_mb(self, component: str) -> int:
        """Get allocated memory budget for component (P7e).
        
        Args:
            component: One of 'projection_main', 'projection_pyramid'
        
        Returns:
            Memory budget in MB, or total cache budget if not configured per-component.
        """
        if self._component_budget is None:
            return int(self._max_bytes // (1024 * 1024))
        
        if component == 'projection_main':
            return self._component_budget.projection_cache_mb
        elif component == 'projection_pyramid':
            # Pyramid uses part of main budget (default 1/4)
            return self._component_budget.projection_cache_mb // 4
        
        return 0

    def _evict_if_needed(self) -> None:
        """Evict least-recently-used items until within budget.
        
        P6: Save evicted items to disk cache before discarding.
        """
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
        
        # Evict until within budget, tracking per-cycle evictions
        while self._total_bytes > self._max_bytes and (self._pyramid_items or self._items):
            if self._pyramid_items:
                key, item = self._pyramid_items.popitem(last=False)
                self._total_bytes -= item.nbytes
                self._telemetry.pyramid_evictions += 1
                self._telemetry.evictions_this_cycle += 1
                self._telemetry.bytes_evicted += item.nbytes
                # P6: Save to disk cache before discarding pyramid
                if self._disk_cache:
                    self._disk_cache.save(key, item.data)
                continue
            if self._items:
                key, item = self._items.popitem(last=False)
                self._total_bytes -= item.nbytes
                self._telemetry.evictions += 1
                self._telemetry.evictions_this_cycle += 1
                self._telemetry.bytes_evicted += item.nbytes
                # P6: Save to disk cache before discarding
                if self._disk_cache:
                    self._disk_cache.save(key, item.data)
                continue
        
        # Log eviction summary if needed
        if self._telemetry.evictions > 0 or self._telemetry.pyramid_evictions > 0:
            mb_reclaimed = int(math.ceil(self._telemetry.bytes_evicted / (1024 * 1024)))
            logger.debug(
                f"Cache evicted {self._telemetry.evictions} items + "
                f"{self._telemetry.pyramid_evictions} pyramid levels, "
                f"reclaimed {mb_reclaimed} MB"
            )

