"""Framework service interfaces (UI-agnostic).

This module defines abstract base classes for core services that enable
decoupling between algorithm implementations and UI frameworks. All services
defined here are headless-compatible and contain no Qt/GUI dependencies.

Services defined:
- EventService: Publish/subscribe event bus
- LogService: Structured logging interface
- SettingsService: Configuration access
- ThreadService: Thread pool management
- CacheService: Cache coordination
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, List, Type, TypeVar


# Type variables for generic services
T = TypeVar("T")
ServiceType = TypeVar("ServiceType")


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


# ============================================================================
# EVENT SERVICE
# ============================================================================

@dataclass
class Event:
    """Base class for all events on the event bus."""
    source: Any = None
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class EventService(ABC):
    """Publish/subscribe event bus for loose coupling.

    Enables decoupled communication between components without
    exposing their internal dependencies. Used for:
    - Annotation changes
    - ROI modifications
    - Cache stats updates
    - Renderer state changes
    """

    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event instance to broadcast

        Raises:
            RuntimeError: If event publishing fails
        """

    @abstractmethod
    def subscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
    ) -> Callable[[], None]:
        """Subscribe to events of a specific type.

        Args:
            event_type: Class to match (e.g., AnnotationChangedEvent)
            callback: Function to call when event is published

        Returns:
            Unsubscribe function; call to remove subscription
        """

    @abstractmethod
    def unsubscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
    ) -> None:
        """Unsubscribe from a specific event type.

        Args:
            event_type: Event class to unsubscribe from
            callback: Function to remove
        """


# ============================================================================
# LOG SERVICE
# ============================================================================

class LogService(ABC):
    """Structured logging interface for headless operation.

    Allows core code to log without Qt dependencies.
    UI layer wraps this with QTextEdit display.
    """

    @abstractmethod
    def debug(self, message: str, **context) -> None:
        """Log debug message."""

    @abstractmethod
    def info(self, message: str, **context) -> None:
        """Log info message."""

    @abstractmethod
    def warning(self, message: str, **context) -> None:
        """Log warning message."""

    @abstractmethod
    def error(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        """Log error message."""

    @abstractmethod
    def critical(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        """Log critical message."""

    @abstractmethod
    def set_level(self, level: LogLevel) -> None:
        """Set minimum log level."""

    @abstractmethod
    def get_level(self) -> LogLevel:
        """Get current log level."""


# ============================================================================
# SETTINGS SERVICE
# ============================================================================

class SettingsService(ABC):
    """Configuration/preferences interface.

    Allows core code to access app settings without Qt dependencies.
    Default implementation uses in-memory dict.
    UI layer can provide QSettings-backed implementation.
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.

        Args:
            key: Setting key (e.g., 'cache.max_mb', 'prefetch.enabled')
            default: Value if key not found

        Returns:
            Setting value or default
        """

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set a setting value.

        Args:
            key: Setting key
            value: New value

        Raises:
            ValueError: If value type invalid
        """

    @abstractmethod
    def get_all(self) -> Dict[str, Any]:
        """Get all settings as dict."""

    @abstractmethod
    def load_defaults(self) -> None:
        """Reset to default values."""

    @abstractmethod
    def on_changed(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> Callable[[], None]:
        """Subscribe to changes for a specific setting.

        Args:
            key: Setting key to watch
            callback: Function(key, new_value) to call on change

        Returns:
            Unsubscribe function
        """


# ============================================================================
# THREAD SERVICE
# ============================================================================

class ThreadService(ABC):
    """Thread pool and async execution service.

    Coordinates background tasks without Qt dependencies.
    """

    @abstractmethod
    def run_async(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Any:
        """Run function in background thread.

        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            on_done: Callback when done, receives return value
            on_error: Callback on exception, receives Exception

        Returns:
            Future-like object or execution ID
        """

    @abstractmethod
    def wait_all(self, timeout: Optional[float] = None) -> bool:
        """Wait for all pending tasks to complete.

        Args:
            timeout: Seconds to wait (None = forever)

        Returns:
            True if all completed, False if timeout
        """

    @abstractmethod
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown thread pool.

        Args:
            wait: If True, wait for pending tasks before shutdown
        """

    @abstractmethod
    def is_busy(self) -> bool:
        """Check if any tasks are pending."""


# ============================================================================
# CACHE SERVICE
# ============================================================================

class CacheService(ABC):
    """Cache coordination and telemetry.

    Manages all caches in the system with unified statistics.
    """

    @abstractmethod
    def get_cache(self, name: str) -> Any:
        """Get a named cache instance.

        Args:
            name: Cache name (e.g., 'projection', 'pyramid', 'disk')

        Returns:
            Cache instance
        """

    @abstractmethod
    def register_cache(self, name: str, cache: Any) -> None:
        """Register a cache for tracking.

        Args:
            name: Unique cache identifier
            cache: Cache instance (must have .stats property)
        """

    @abstractmethod
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics from all registered caches.

        Returns:
            Dict keyed by cache name, values are stat dicts:
            {
                'projection': {'size_mb': 150, 'hits': 1000, 'misses': 50},
                'pyramid': {'size_mb': 300, 'hits': 500, 'misses': 20},
                ...
            }
        """

    @abstractmethod
    def clear_all(self) -> None:
        """Clear all caches."""

    @abstractmethod
    def set_global_budget(self, max_mb: float) -> None:
        """Set total budget across all caches."""

    @abstractmethod
    def get_global_budget(self) -> float:
        """Get total memory budget in MB."""


# ============================================================================
# SERVICE REGISTRY
# ============================================================================

class ServiceRegistry(ABC):
    """Registry for looking up services by type.

    Provides application-wide access to services without circular imports.
    """

    @abstractmethod
    def register(self, service_type: Type[ServiceType], implementation: ServiceType) -> None:
        """Register a service implementation.

        Args:
            service_type: Abstract type (e.g., EventService)
            implementation: Concrete implementation instance

        Raises:
            ValueError: If type already registered
        """

    @abstractmethod
    def get(self, service_type: Type[ServiceType]) -> ServiceType:
        """Get a registered service.

        Args:
            service_type: Service type to retrieve

        Returns:
            Service implementation

        Raises:
            KeyError: If service not registered
        """

    @abstractmethod
    def get_or_none(self, service_type: Type[ServiceType]) -> Optional[ServiceType]:
        """Get a service, or None if not registered."""

    @abstractmethod
    def unregister(self, service_type: Type) -> None:
        """Unregister a service."""

    @abstractmethod
    def list_services(self) -> Dict[str, Any]:
        """List all registered services."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all services."""
