"""Thread-service interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class ThreadService(ABC):
    """Thread pool and async execution service."""

    @abstractmethod
    def run_async(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Any:
        """Run function in background thread."""

    @abstractmethod
    def wait_all(self, timeout: Optional[float] = None) -> bool:
        """Wait for all pending tasks to complete."""

    @abstractmethod
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown thread pool."""

    @abstractmethod
    def is_busy(self) -> bool:
        """Check if any tasks are pending."""
