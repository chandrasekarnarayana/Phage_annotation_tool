"""Unit tests for cache eviction strategy implementations."""

from __future__ import annotations

import pytest

from phage_annotator.cache.strategies import (
    CacheStrategies,
    EvictionStrategy,
    FIFOEvictionStrategy,
    LFUEvictionStrategy,
    LRUEvictionStrategy,
)


def test_lru_eviction_prefers_least_recently_used() -> None:
    """Verify lru eviction prefers least recently used for the current workflow."""
    strat = LRUEvictionStrategy(max_size=2)
    strat.put("a", 1)
    strat.put("b", 2)
    strat.get("a")

    assert strat.should_evict() is True
    assert strat.evict() == "b"


def test_lfu_eviction_prefers_least_frequent() -> None:
    """Verify lfu eviction prefers least frequent for the current workflow."""
    strat = LFUEvictionStrategy(max_size=2)
    strat.put("a", 1)
    strat.put("b", 2)
    strat.get("a")
    strat.get("a")

    assert strat.evict() == "b"


def test_fifo_eviction_preserves_insertion_order() -> None:
    """Verify fifo eviction preserves insertion order for the current workflow."""
    strat = FIFOEvictionStrategy(max_size=2)
    strat.put("a", 1)
    strat.put("b", 2)
    strat.get("a")

    assert strat.evict() == "a"


def test_cache_strategies_register_and_list_custom_strategy() -> None:
    """Verify cache strategies register and list custom strategy for the current workflow."""
    class _Dummy(EvictionStrategy[str, int]):
        def put(self, key: str, value: int) -> None:
            """Run the put workflow."""
            self._size += 1

        def get(self, key: str) -> None:
            """Return get for the current workflow."""
            return

        def should_evict(self) -> bool:
            """Run the should evict workflow."""
            return False

        def evict(self):
            """Run the evict workflow."""
            return None

        def remove(self, key: str) -> None:
            """Remove remove for the current workflow."""
            self._size = max(0, self._size - 1)

        def clear(self) -> None:
            """Clear clear for the current workflow."""
            self._size = 0

    CacheStrategies.register("dummy", _Dummy)
    try:
        assert "dummy" in CacheStrategies.list()
        strat = CacheStrategies.get("dummy", max_size=5)
        assert isinstance(strat, _Dummy)
        assert strat.max_size == 5
    finally:
        CacheStrategies._strategies.pop("dummy", None)


def test_cache_strategies_unknown_name_raises_helpful_error() -> None:
    """Verify cache strategies unknown name raises helpful error for the current workflow."""
    with pytest.raises(ValueError, match="Unknown strategy"):
        CacheStrategies.get("missing")
