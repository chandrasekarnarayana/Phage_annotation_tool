"""Default cache registry service implementation."""

from __future__ import annotations

import threading
from typing import Any, Dict

from phage_annotator.framework.base import CacheService


class DefaultCacheService(CacheService):
    """Simple cache registry and statistics collector."""

    def __init__(self, global_budget_mb: float = 1024.0):
        """Initialize cache service with a global memory budget."""
        self._caches: Dict[str, Any] = {}
        self._global_budget_mb = global_budget_mb
        self._lock = threading.RLock()

    def get_cache(self, name: str) -> Any:
        """Return a registered cache by name, if present."""
        with self._lock:
            return self._caches.get(name)

    def register_cache(self, name: str, cache: Any) -> None:
        """Register a cache object under a stable name."""
        with self._lock:
            self._caches[name] = cache

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Collect stats from all caches."""
        stats = {}
        with self._lock:
            for name, cache in self._caches.items():
                if hasattr(cache, "stats"):
                    try:
                        cache_stats = cache.stats()
                        stats[name] = cache_stats if isinstance(cache_stats, dict) else {}
                    except Exception:
                        stats[name] = {}
                else:
                    stats[name] = {}
        return stats

    def clear_all(self) -> None:
        """Clear all registered caches that expose a clear method."""
        with self._lock:
            for cache in self._caches.values():
                if hasattr(cache, "clear"):
                    try:
                        cache.clear()
                    except Exception:
                        pass

    def set_global_budget(self, max_mb: float) -> None:
        """Set the shared cache budget in megabytes."""
        self._global_budget_mb = max_mb

    def get_global_budget(self) -> float:
        """Return the shared cache budget in megabytes."""
        return self._global_budget_mb
