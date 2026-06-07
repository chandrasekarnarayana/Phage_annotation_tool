"""First-in-first-out cache eviction strategy."""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from phage_annotator.cache.eviction_base import EvictionStrategy, K, V


class FIFOEvictionStrategy(EvictionStrategy[K, V]):
    """Evict the oldest entry regardless of access frequency."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize insertion-order tracking."""
        super().__init__(max_size)
        self._insertion_order: OrderedDict[K, None] = OrderedDict()

    def put(self, key: K, value: V) -> None:
        """Record that a key was added."""
        if key not in self._insertion_order:
            self._insertion_order[key] = None
            self._size += 1

    def get(self, key: K) -> None:
        """Ignore access because FIFO order only depends on insertion."""

    def should_evict(self) -> bool:
        """Check if cache is full."""
        return self._size >= self._max_size

    def evict(self) -> Optional[K]:
        """Evict the oldest entry."""
        if not self._insertion_order:
            return None
        key, _ = self._insertion_order.popitem(last=False)
        self._size -= 1
        return key

    def remove(self, key: K) -> None:
        """Remove a key from tracking."""
        if key in self._insertion_order:
            del self._insertion_order[key]
            self._size -= 1

    def clear(self) -> None:
        """Clear all state."""
        self._insertion_order.clear()
        self._size = 0
