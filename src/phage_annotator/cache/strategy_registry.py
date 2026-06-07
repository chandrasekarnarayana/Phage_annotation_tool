"""Registry for cache eviction strategy factories."""

from __future__ import annotations

from phage_annotator.cache.eviction_base import EvictionStrategy
from phage_annotator.cache.fifo_strategy import FIFOEvictionStrategy
from phage_annotator.cache.lfu_strategy import LFUEvictionStrategy
from phage_annotator.cache.lru_strategy import LRUEvictionStrategy


class CacheStrategies:
    """Registry for cache eviction strategies."""

    _strategies: dict[str, type] = {
        "lru": LRUEvictionStrategy,
        "lfu": LFUEvictionStrategy,
        "fifo": FIFOEvictionStrategy,
    }

    @classmethod
    def get(cls, name: str, max_size: int = 100) -> EvictionStrategy:
        """Get a strategy instance by name."""
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
        """Register a custom strategy class."""
        if not issubclass(strategy_class, EvictionStrategy):
            raise TypeError(f"{strategy_class} must inherit from EvictionStrategy")
        cls._strategies[name] = strategy_class
