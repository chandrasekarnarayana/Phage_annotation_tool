"""Least-frequently-used cache eviction strategy."""

from __future__ import annotations

from typing import Dict, Optional

from phage_annotator.cache.eviction_base import EvictionStrategy, K, V


class LFUEvictionStrategy(EvictionStrategy[K, V]):
    """Evict the entry with the lowest access frequency."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize frequency tracking."""
        super().__init__(max_size)
        self._frequency: Dict[K, int] = {}

    def put(self, key: K, value: V) -> None:
        """Record that a key was added."""
        if key not in self._frequency:
            self._frequency[key] = 1
            self._size += 1
        else:
            self._frequency[key] += 1

    def get(self, key: K) -> None:
        """Record that a key was accessed."""
        if key in self._frequency:
            self._frequency[key] += 1

    def should_evict(self) -> bool:
        """Check if cache is full."""
        return self._size >= self._max_size

    def evict(self) -> Optional[K]:
        """Evict the least frequently used entry."""
        if not self._frequency:
            return None
        min_key = min(self._frequency, key=self._frequency.get)
        del self._frequency[min_key]
        self._size -= 1
        return min_key

    def remove(self, key: K) -> None:
        """Remove a key from tracking."""
        if key in self._frequency:
            del self._frequency[key]
            self._size -= 1

    def clear(self) -> None:
        """Clear all state."""
        self._frequency.clear()
        self._size = 0
