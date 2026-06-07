"""Cache-service interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class CacheService(ABC):
    """Cache coordination and telemetry."""

    @abstractmethod
    def get_cache(self, name: str) -> Any:
        """Get a named cache instance."""

    @abstractmethod
    def register_cache(self, name: str, cache: Any) -> None:
        """Register a cache for tracking."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics from all registered caches."""

    @abstractmethod
    def clear_all(self) -> None:
        """Clear all caches."""

    @abstractmethod
    def set_global_budget(self, max_mb: float) -> None:
        """Set total budget across all caches."""

    @abstractmethod
    def get_global_budget(self) -> float:
        """Get total memory budget in MB."""
