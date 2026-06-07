"""Compatibility exports for cache eviction strategy implementations."""

from __future__ import annotations

from phage_annotator.cache.eviction_base import EvictionStrategy
from phage_annotator.cache.fifo_strategy import FIFOEvictionStrategy
from phage_annotator.cache.lfu_strategy import LFUEvictionStrategy
from phage_annotator.cache.lru_strategy import LRUEvictionStrategy
from phage_annotator.cache.strategy_registry import CacheStrategies

__all__ = [
    "CacheStrategies",
    "EvictionStrategy",
    "FIFOEvictionStrategy",
    "LFUEvictionStrategy",
    "LRUEvictionStrategy",
]
