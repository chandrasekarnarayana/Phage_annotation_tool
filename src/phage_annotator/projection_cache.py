"""Projection LRU cache with a memory budget.

This cache stores computed projection arrays keyed by image id, projection
type, crop rectangle, and current T/Z selection. It tracks approximate byte
usage and evicts least-recently-used items when over budget. Pyramid levels
are cached separately and evicted first to preserve primary projections.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

CacheKey = Tuple[int, str, Tuple[float, float, float, float], int, int]
PyramidKey = Tuple[int, str, int, int, Tuple[float, float, float, float], int]


@dataclass
class CacheItem:
    """Cached projection and its byte size."""

    data: np.ndarray
    nbytes: int


class ProjectionCache:
    """LRU cache for projection arrays keyed by image/projection/crop/selection.

    Notes
    -----
    - Items store numpy arrays only; no GUI state is retained.
    - Budget is defined in MB and enforced on insert.
    """

    def __init__(self, max_mb: int = 1024) -> None:
        self._items: "OrderedDict[CacheKey, CacheItem]" = OrderedDict()
        self._pyramid_items: "OrderedDict[PyramidKey, CacheItem]" = OrderedDict()
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._total_bytes = 0

    def set_budget_mb(self, max_mb: int) -> None:
        """Update the cache budget in MB and evict if needed."""
        self._max_bytes = int(max_mb) * 1024 * 1024
        self._evict_if_needed()

    def get(self, key: CacheKey) -> Optional[np.ndarray]:
        """Return a cached array and mark it as most-recently-used."""
        item = self._items.get(key)
        if item is None:
            return None
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

    def _evict_if_needed(self) -> None:
        """Evict least-recently-used items until within budget."""
        while self._total_bytes > self._max_bytes and (self._pyramid_items or self._items):
            if self._pyramid_items:
                _, item = self._pyramid_items.popitem(last=False)
                self._total_bytes -= item.nbytes
                continue
            if self._items:
                _, item = self._items.popitem(last=False)
                self._total_bytes -= item.nbytes
                continue
