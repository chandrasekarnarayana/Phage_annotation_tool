"""Strategy patterns for swappable cache eviction policies.

This module implements the strategy pattern for cache eviction, enabling
different cache replacement algorithms to be swapped at runtime without
modifying cache implementation code.

Architecture
------------
- EvictionStrategy: Abstract base for all eviction policies
- LRUEvictionStrategy: Least-recently-used eviction
- LFUEvictionStrategy: Least-frequently-used eviction
- FIFOEvictionStrategy: First-in-first-out eviction
- CacheStrategies: Registry for available strategies

Usage
-----
```python
from phage_annotator.cache.strategies import LRUEvictionStrategy, CacheStrategies

# Use specific strategy
strategy = LRUEvictionStrategy(max_size=100)
cache = ProjectionCache(eviction_strategy=strategy)

# Or use registry
strategy = CacheStrategies.get("lru", max_size=100)
```

Benefits
--------
- Algorithms separated from cache implementation (SRP)
- Easy to add new strategies without modifying existing code (OCP)
- Testable in isolation
- Configurable at runtime
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Dict, Generic, Optional, TypeVar

K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


class EvictionStrategy(ABC, Generic[K, V]):
    """Abstract base class for cache eviction strategies.
    
    Eviction strategies decide which cache entry to remove when the cache
    is full and a new entry needs to be added.
    
    Parameters
    ----------
    max_size : int
        Maximum number of entries before eviction occurs
        
    Methods
    -------
    put(key, value)
        Called when a new entry is added
    get(key)
        Called when an entry is accessed
    should_evict()
        Returns True if cache is full and eviction is needed
    evict()
        Returns the key to evict
    remove(key)
        Called when an entry is explicitly removed
    clear()
        Called when cache is cleared
    """
    
    def __init__(self, max_size: int = 100) -> None:
        self._max_size = max_size
        self._size = 0
    
    @abstractmethod
    def put(self, key: K, value: V) -> None:
        """Record that a key-value pair was added to cache."""
        pass
    
    @abstractmethod
    def get(self, key: K) -> None:
        """Record that a key was accessed from cache."""
        pass
    
    @abstractmethod
    def should_evict(self) -> bool:
        """Return True if cache is full and eviction is needed."""
        pass
    
    @abstractmethod
    def evict(self) -> Optional[K]:
        """Return the key to evict, or None if cache is empty."""
        pass
    
    @abstractmethod
    def remove(self, key: K) -> None:
        """Record that a key was explicitly removed from cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all eviction strategy state."""
        pass
    
    @property
    def max_size(self) -> int:
        """Maximum cache size."""
        return self._max_size
    
    @property
    def size(self) -> int:
        """Current cache size."""
        return self._size


class LRUEvictionStrategy(EvictionStrategy[K, V]):
    """Least-Recently-Used (LRU) eviction strategy.
    
    Evicts the entry that was accessed longest ago. Good general-purpose
    strategy that adapts to access patterns.
    
    Implementation
    --------------
    Uses OrderedDict for O(1) access and eviction.
    """
    
    def __init__(self, max_size: int = 100) -> None:
        super().__init__(max_size)
        self._access_order: OrderedDict[K, None] = OrderedDict()
    
    def put(self, key: K, value: V) -> None:
        """Record that a key was added."""
        # Move to end (most recently used)
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
        # Pop from beginning (least recently used)
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


class LFUEvictionStrategy(EvictionStrategy[K, V]):
    """Least-Frequently-Used (LFU) eviction strategy.
    
    Evicts the entry that has been accessed the fewest times. Good for
    workloads where some entries are accessed repeatedly while others are
    accessed once.
    
    Implementation
    --------------
    Tracks access frequency for each key.
    """
    
    def __init__(self, max_size: int = 100) -> None:
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
        # Find key with minimum frequency
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


class FIFOEvictionStrategy(EvictionStrategy[K, V]):
    """First-In-First-Out (FIFO) eviction strategy.
    
    Evicts the oldest entry regardless of access patterns. Simplest
    strategy, good for sequential access patterns.
    
    Implementation
    --------------
    Maintains insertion order using OrderedDict.
    """
    
    def __init__(self, max_size: int = 100) -> None:
        super().__init__(max_size)
        self._insertion_order: OrderedDict[K, None] = OrderedDict()
    
    def put(self, key: K, value: V) -> None:
        """Record that a key was added."""
        if key not in self._insertion_order:
            self._insertion_order[key] = None
            self._size += 1
    
    def get(self, key: K) -> None:
        """Access doesn't affect FIFO order."""
        pass
    
    def should_evict(self) -> bool:
        """Check if cache is full."""
        return self._size >= self._max_size
    
    def evict(self) -> Optional[K]:
        """Evict the oldest entry."""
        if not self._insertion_order:
            return None
        # Pop from beginning (oldest)
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


class CacheStrategies:
    """Registry for cache eviction strategies.
    
    Provides centralized access to available strategies with factory methods.
    
    Usage
    -----
    ```python
    # Get strategy by name
    strategy = CacheStrategies.get("lru", max_size=100)
    
    # List available strategies
    print(CacheStrategies.list())  # ['lru', 'lfu', 'fifo']
    
    # Register custom strategy
    CacheStrategies.register("custom", MyCustomStrategy)
    ```
    """
    
    _strategies: Dict[str, type] = {
        "lru": LRUEvictionStrategy,
        "lfu": LFUEvictionStrategy,
        "fifo": FIFOEvictionStrategy,
    }
    
    @classmethod
    def get(cls, name: str, max_size: int = 100) -> EvictionStrategy:
        """Get a strategy instance by name.
        
        Parameters
        ----------
        name : str
            Strategy name ("lru", "lfu", "fifo")
        max_size : int
            Maximum cache size
            
        Returns
        -------
        EvictionStrategy
            Strategy instance
            
        Raises
        ------
        ValueError
            If strategy name is not registered
        """
        if name not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
        
        strategy_class = cls._strategies[name]
        return strategy_class(max_size=max_size)
    
    @classmethod
    def list(cls) -> list:
        """List available strategy names."""
        return list(cls._strategies.keys())
    
    @classmethod
    def register(cls, name: str, strategy_class: type) -> None:
        """Register a custom strategy.
        
        Parameters
        ----------
        name : str
            Strategy name
        strategy_class : type
            Strategy class (must inherit from EvictionStrategy)
        """
        if not issubclass(strategy_class, EvictionStrategy):
            raise TypeError(f"{strategy_class} must inherit from EvictionStrategy")
        cls._strategies[name] = strategy_class


__all__ = [
    "EvictionStrategy",
    "LRUEvictionStrategy",
    "LFUEvictionStrategy",
    "FIFOEvictionStrategy",
    "CacheStrategies",
]
