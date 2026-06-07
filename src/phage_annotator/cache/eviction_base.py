"""Base protocol for cache eviction strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class EvictionStrategy(ABC, Generic[K, V]):
    """Abstract base class for cache eviction strategies."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize strategy state with a maximum tracked size."""
        self._max_size = max_size
        self._size = 0

    @abstractmethod
    def put(self, key: K, value: V) -> None:
        """Record that a key-value pair was added to cache."""

    @abstractmethod
    def get(self, key: K) -> None:
        """Record that a key was accessed from cache."""

    @abstractmethod
    def should_evict(self) -> bool:
        """Return True if cache is full and eviction is needed."""

    @abstractmethod
    def evict(self) -> Optional[K]:
        """Return the key to evict, or None if cache is empty."""

    @abstractmethod
    def remove(self, key: K) -> None:
        """Record that a key was explicitly removed from cache."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all eviction strategy state."""

    @property
    def max_size(self) -> int:
        """Maximum cache size."""
        return self._max_size

    @property
    def size(self) -> int:
        """Current cache size."""
        return self._size
