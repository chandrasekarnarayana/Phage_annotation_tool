"""Default implementations of framework services.

These are headless-compatible implementations suitable for:
- Command-line usage
- Automated/batch processing
- Server-side analysis
- Unit testing

The UI layer can override these with Qt-aware versions.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import asdict, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List, Type, TypeVar

from phage_annotator.framework.base import (
    Event,
    EventService,
    LogLevel,
    LogService,
    SettingsService,
    ThreadService,
    CacheService,
    ServiceRegistry,
)


ServiceType = TypeVar("ServiceType")


# ============================================================================
# DEFAULT EVENT SERVICE
# ============================================================================

class DefaultEventService(EventService):
    """Simple in-memory pub/sub implementation.

    Thread-safe. Delivers events synchronously in publishing thread.
    UI layer can provide asynchronous Qt signal-based version.
    """

    def __init__(self):
        """Initialize event bus."""
        self._subscribers: Dict[Type, List[Callable]] = {}
        self._lock = threading.RLock()

    def publish(self, event: Event) -> None:
        """Publish event to all matching subscribers."""
        event_type = type(event)
        if event.timestamp is None:
            event.timestamp = time.time()

        with self._lock:
            callbacks = self._subscribers.get(event_type, [])
            for callback in list(callbacks):  # Copy to allow unsubscribe during iteration
                try:
                    callback(event)
                except Exception as exc:
                    # Don't crash on subscription callback error
                    logger = logging.getLogger(__name__)
                    logger.exception(f"Error in {event_type.__name__} subscriber: {exc}")

    def subscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
    ) -> Callable[[], None]:
        """Subscribe to an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

        # Return unsubscribe function
        def unsubscribe():
            self.unsubscribe(event_type, callback)

        return unsubscribe

    def unsubscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
    ) -> None:
        """Unsubscribe from an event type."""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass  # Not subscribed


# ============================================================================
# DEFAULT LOG SERVICE
# ============================================================================

class DefaultLogService(LogService):
    """Simple logging service using Python's logging module.

    Sends to stdout/file. UI layer can route to QTextEdit.
    """

    def __init__(self, name: str = "phage.core", level: LogLevel = LogLevel.INFO):
        """Initialize logger.

        Args:
            name: Logger name
            level: Minimum log level
        """
        self._logger = logging.getLogger(name)
        self._level = level
        self._logger.setLevel(level.value * 10)  # Convert enum to logging level

        # Setup default handler if not already configured
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(levelname)s] %(name)s: %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def debug(self, message: str, **context) -> None:
        self._log(LogLevel.DEBUG, message, context)

    def info(self, message: str, **context) -> None:
        self._log(LogLevel.INFO, message, context)

    def warning(self, message: str, **context) -> None:
        self._log(LogLevel.WARNING, message, context)

    def error(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        self._log(LogLevel.ERROR, message, context, exc_info)

    def critical(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        self._log(LogLevel.CRITICAL, message, context, exc_info)

    def set_level(self, level: LogLevel) -> None:
        self._level = level
        self._logger.setLevel(level.value * 10)

    def get_level(self) -> LogLevel:
        return self._level

    def _log(
        self,
        level: LogLevel,
        message: str,
        context: Dict[str, Any],
        exc_info: Optional[Exception] = None,
    ) -> None:
        """Internal logging method."""
        if context:
            # Append context to message
            context_str = " | " + ", ".join(f"{k}={v}" for k, v in context.items())
            message = message + context_str

        if level == LogLevel.DEBUG:
            self._logger.debug(message)
        elif level == LogLevel.INFO:
            self._logger.info(message)
        elif level == LogLevel.WARNING:
            self._logger.warning(message)
        elif level == LogLevel.ERROR:
            self._logger.error(message, exc_info=exc_info)
        elif level == LogLevel.CRITICAL:
            self._logger.critical(message, exc_info=exc_info)


# ============================================================================
# DEFAULT SETTINGS SERVICE
# ============================================================================

class DefaultSettingsService(SettingsService):
    """In-memory settings with optional file backing.

    Suitable for headless/CLI usage. UI layer wraps QSettings.
    """

    def __init__(self, defaults: Optional[Dict[str, Any]] = None):
        """Initialize settings.

        Args:
            defaults: Default settings dict
        """
        self._settings = defaults.copy() if defaults else {}
        self._observers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            old_value = self._settings.get(key)
            self._settings[key] = value

            # Notify observers if value changed
            if key in self._observers and old_value != value:
                for callback in list(self._observers[key]):
                    try:
                        callback(key, value)
                    except Exception:
                        pass  # Ignore observer errors

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return self._settings.copy()

    def load_defaults(self) -> None:
        """Reset to defaults (clear current settings)."""
        with self._lock:
            self._settings.clear()

    def on_changed(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> Callable[[], None]:
        """Subscribe to setting changes."""
        with self._lock:
            if key not in self._observers:
                self._observers[key] = []
            self._observers[key].append(callback)

        def unsubscribe():
            with self._lock:
                if key in self._observers:
                    try:
                        self._observers[key].remove(callback)
                    except ValueError:
                        pass

        return unsubscribe


# ============================================================================
# DEFAULT THREAD SERVICE
# ============================================================================

class DefaultThreadService(ThreadService):
    """Thread pool service using concurrent.futures.ThreadPoolExecutor."""

    def __init__(self, max_workers: int = 4):
        """Initialize thread pool.

        Args:
            max_workers: Maximum concurrent threads
        """
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
        """Run function asynchronously."""
        if kwargs is None:
            kwargs = {}

        def wrapped_func():
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
        """Wait for all pending tasks."""
        with self._lock:
            futures = list(self._futures)

        for future in futures:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass  # Ignore errors during wait

        return all(f.done() for f in futures)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown thread pool."""
        self._executor.shutdown(wait=wait)

    def is_busy(self) -> bool:
        """Check if any tasks are pending."""
        with self._lock:
            return any(not f.done() for f in self._futures)


# ============================================================================
# DEFAULT CACHE SERVICE
# ============================================================================

class DefaultCacheService(CacheService):
    """Simple cache registry and statistics collector."""

    def __init__(self, global_budget_mb: float = 1024.0):
        """Initialize cache service.

        Args:
            global_budget_mb: Total memory budget in MB
        """
        self._caches: Dict[str, Any] = {}
        self._global_budget_mb = global_budget_mb
        self._lock = threading.RLock()

    def get_cache(self, name: str) -> Any:
        with self._lock:
            return self._caches.get(name)

    def register_cache(self, name: str, cache: Any) -> None:
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
        """Clear all caches."""
        with self._lock:
            for cache in self._caches.values():
                if hasattr(cache, "clear"):
                    try:
                        cache.clear()
                    except Exception:
                        pass

    def set_global_budget(self, max_mb: float) -> None:
        self._global_budget_mb = max_mb

    def get_global_budget(self) -> float:
        return self._global_budget_mb


# ============================================================================
# DEFAULT SERVICE REGISTRY
# ============================================================================

class DefaultServiceRegistry(ServiceRegistry):
    """Simple service registry backed by dict."""

    def __init__(self):
        """Initialize empty registry."""
        self._services: Dict[Type, Any] = {}
        self._lock = threading.RLock()

    def register(self, service_type: Type[ServiceType], implementation: ServiceType) -> None:
        with self._lock:
            if service_type in self._services:
                raise ValueError(f"Service {service_type.__name__} already registered")
            self._services[service_type] = implementation

    def get(self, service_type: Type[ServiceType]) -> ServiceType:
        with self._lock:
            if service_type not in self._services:
                raise KeyError(f"Service {service_type.__name__} not registered")
            return self._services[service_type]

    def get_or_none(self, service_type: Type[ServiceType]) -> Optional[ServiceType]:
        with self._lock:
            return self._services.get(service_type)

    def unregister(self, service_type: Type) -> None:
        with self._lock:
            self._services.pop(service_type, None)

    def list_services(self) -> Dict[str, Any]:
        with self._lock:
            return {
                svc_type.__name__: svc
                for svc_type, svc in self._services.items()
            }

    def clear(self) -> None:
        with self._lock:
            self._services.clear()
