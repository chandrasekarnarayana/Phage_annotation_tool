"""Least-recently-used cache eviction strategy."""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from phage_annotator.cache.eviction_base import EvictionStrategy, K, V


class LRUEvictionStrategy(EvictionStrategy[K, V]):
    """Evict the entry that was accessed longest ago."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize access-order tracking."""
        super().__init__(max_size)
        self._access_order: OrderedDict[K, None] = OrderedDict()

    def put(self, key: K, value: V) -> None:
        """Record that a key was added."""
        if key in self._access_order:
            self._access_order.move_to_end(key)
        else:
            self._access_order[key] = None
            self._size += 1

    def get(self, key: K) -> None:
        """Record that a key was accessed."""
        if key in self._access_order:
            self._access_order.move_to_end(key)

    def should_evict(self) -> bool:
        """Check if cache is full."""
        return self._size >= self._max_size

    def evict(self) -> Optional[K]:
        """Evict the least recently used entry."""
        if not self._access_order:
            return None
        key, _ = self._access_order.popitem(last=False)
        self._size -= 1
        return key

    def remove(self, key: K) -> None:
        """Remove a key from tracking."""
        if key in self._access_order:
            del self._access_order[key]
            self._size -= 1

    def clear(self) -> None:
        """Clear all state."""
        self._access_order.clear()
        self._size = 0
