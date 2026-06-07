"""Default background thread service implementation."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from phage_annotator.framework.base import ThreadService


class DefaultThreadService(ThreadService):
    """Thread pool service using concurrent.futures.ThreadPoolExecutor."""

    def __init__(self, max_workers: int = 4):
        """Initialize thread pool."""
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: List[Future] = []
        self._lock = threading.RLock()

    def run_async(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Any:
        """Run a function asynchronously and optionally notify callbacks."""
        if kwargs is None:
            kwargs = {}

        def wrapped_func():
            """Execute the submitted function and dispatch completion callbacks."""
            try:
                result = func(*args, **kwargs)
                if on_done:
                    on_done(result)
                return result
            except Exception as exc:
                if on_error:
                    on_error(exc)
                else:
                    raise

        future = self._executor.submit(wrapped_func)
        with self._lock:
            self._futures.append(future)

        return future

    def wait_all(self, timeout: Optional[float] = None) -> bool:
        """Wait for all pending tasks to complete."""
        with self._lock:
            futures = list(self._futures)

        for future in futures:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass

        return all(future.done() for future in futures)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown thread pool."""
        self._executor.shutdown(wait=wait)

    def is_busy(self) -> bool:
        """Return whether any tasks are still pending."""
        with self._lock:
            return any(not future.done() for future in self._futures)
