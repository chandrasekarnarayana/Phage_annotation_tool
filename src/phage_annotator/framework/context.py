"""Application context - central service container.

The ApplicationContext is the single point where all services are created,
configured, and made available to the application. This is inspired by
SciJava's Context and enables true dependency injection without circular imports.

Usage:

    # Create and configure context
    context = ApplicationContext.create_default()

    # Access services from anywhere
    event_service = context.get_service(EventService)
    event_service.publish(MyEvent())

    # In tests, override services
    test_context = ApplicationContext.create_default()
    test_context.set_service(CacheService, TestCacheService())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type, TypeVar

from phage_annotator.framework.base import (
    EventService,
    LogService,
    SettingsService,
    ThreadService,
    CacheService,
    ServiceRegistry,
)
from phage_annotator.framework.services import (
    DefaultEventService,
    DefaultLogService,
    DefaultSettingsService,
    DefaultThreadService,
    DefaultCacheService,
    DefaultServiceRegistry,
)


ServiceType = TypeVar("ServiceType")

# Global context instance - can be overridden for testing
_global_context: Optional[ApplicationContext] = None


@dataclass
class ContextConfig:
    """Configuration for ApplicationContext initialization."""

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Threading
    max_worker_threads: int = 4

    # Cache
    global_cache_budget_mb: float = 1024.0

    # Settings
    settings_defaults: Optional[Dict[str, Any]] = None

    # Custom service implementations (for testing/override)
    event_service: Optional[EventService] = None
    log_service: Optional[LogService] = None
    settings_service: Optional[SettingsService] = None
    thread_service: Optional[ThreadService] = None
    cache_service: Optional[CacheService] = None


class ApplicationContext:
    """Central service container for the application.

    All services are created here and made available throughout the
    application without circular imports. This decouples:
    - Algorithm code from GUI frameworks
    - Individual services from each other
    - Test code from production implementations

    Thread-safe. Suitable for headless, CLI, server, and UI usage.
    """

    def __init__(self, config: ContextConfig):
        """Initialize application context.

        Args:
            config: ContextConfig with service choices
        """
        self.config = config
        self._registry = DefaultServiceRegistry()
        self._logger: Optional[LogService] = None
        self._initialize_services()

    def _initialize_services(self) -> None:
        """Create and register all services."""
        # LogService first (needed by other services)
        if self.config.log_service:
            log_service = self.config.log_service
        else:
            log_service = self._create_log_service()
        self._logger = log_service
        self._registry.register(LogService, log_service)

        # EventService
        event_service = (
            self.config.event_service or DefaultEventService()
        )
        self._registry.register(EventService, event_service)

        # SettingsService
        settings_service = (
            self.config.settings_service
            or DefaultSettingsService(self.config.settings_defaults)
        )
        self._registry.register(SettingsService, settings_service)

        # ThreadService
        thread_service = (
            self.config.thread_service
            or DefaultThreadService(max_workers=self.config.max_worker_threads)
        )
        self._registry.register(ThreadService, thread_service)

        # CacheService
        cache_service = (
            self.config.cache_service or DefaultCacheService(self.config.global_cache_budget_mb)
        )
        self._registry.register(CacheService, cache_service)

        # ServiceRegistry itself
        self._registry.register(ServiceRegistry, self._registry)

    def _create_log_service(self) -> LogService:
        """Create default log service."""
        from phage_annotator.framework.base import LogLevel

        log_level_map = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
            "CRITICAL": LogLevel.CRITICAL,
        }
        level = log_level_map.get(self.config.log_level.upper(), LogLevel.INFO)
        return DefaultLogService(level=level)

    def get_service(self, service_type: Type[ServiceType]) -> ServiceType:
        """Get a service by type.

        Args:
            service_type: Service interface class (e.g., EventService)

        Returns:
            Service implementation instance

        Raises:
            KeyError: If service not registered
        """
        return self._registry.get(service_type)

    def get_service_or_none(self, service_type: Type[ServiceType]) -> Optional[ServiceType]:
        """Get a service, or None if not registered."""
        return self._registry.get_or_none(service_type)

    def set_service(self, service_type: Type[ServiceType], implementation: ServiceType) -> None:
        """Override a service (useful for testing).

        Args:
            service_type: Service interface class
            implementation: New implementation to use

        Raises:
            ValueError: If service already registered (unregister first)
        """
        self._registry.unregister(service_type)
        self._registry.register(service_type, implementation)

    def list_services(self) -> Dict[str, Any]:
        """Get all registered services."""
        return self._registry.list_services()

    def shutdown(self) -> None:
        """Shutdown all services gracefully."""
        try:
            thread_service = self.get_service_or_none(ThreadService)
            if thread_service:
                thread_service.shutdown(wait=True)
        except Exception as exc:
            if self._logger:
                self._logger.error("Error shutting down thread service", exc_info=exc)

    @classmethod
    def create_default(cls, config: Optional[ContextConfig] = None) -> ApplicationContext:
        """Create context with default configuration.

        Suitable for normal operation, CLI, and servers.

        Args:
            config: Optional overrides (None = use all defaults)

        Returns:
            Configured ApplicationContext
        """
        if config is None:
            config = ContextConfig()
        return cls(config)

    @classmethod
    def create_test(cls) -> ApplicationContext:
        """Create context for testing.

        Uses minimal services, appropriate for unit tests.

        Returns:
            Test ApplicationContext
        """
        from phage_annotator.framework.base import LogLevel

        config = ContextConfig(
            log_level="DEBUG",
            log_file=None,
            max_worker_threads=2,
            global_cache_budget_mb=128.0,  # Smaller for tests
        )
        return cls(config)

    @classmethod
    def create_headless(cls, log_level: str = "WARNING") -> ApplicationContext:
        """Create context for headless/batch processing.

        Disables non-essential services for speed.

        Args:
            log_level: Minimum log level to emit

        Returns:
            Optimized headless ApplicationContext
        """
        config = ContextConfig(
            log_level=log_level,
            max_worker_threads=8,  # More parallelism
            global_cache_budget_mb=2048.0,  # More memory available
        )
        return cls(config)

    @classmethod
    def get_global(cls) -> ApplicationContext:
        """Get the global context instance.

        Returns:
            Global context (creates default if not set)

        Raises:
            RuntimeError: If no global context configured
        """
        global _global_context
        if _global_context is None:
            raise RuntimeError(
                "No global context configured. Call "
                "ApplicationContext.set_global() first."
            )
        return _global_context

    @classmethod
    def set_global(cls, context: ApplicationContext) -> None:
        """Set the global context instance (usually in app startup).

        Args:
            context: Context to use for application
        """
        global _global_context
        _global_context = context

    @classmethod
    def create_and_set_global(cls, config: Optional[ContextConfig] = None) -> ApplicationContext:
        """Create default context and set as global instance.

        Convenience method for app initialization.

        Args:
            config: Optional configuration overrides

        Returns:
            New global context
        """
        context = cls.create_default(config)
        cls.set_global(context)
        return context


# ============================================================================
# HELPER FUNCTIONS FOR COMMON SERVICE ACCESS
# ============================================================================

def get_event_service() -> EventService:
    """Get the global event service."""
    return ApplicationContext.get_global().get_service(EventService)


def get_log_service() -> LogService:
    """Get the global log service."""
    return ApplicationContext.get_global().get_service(LogService)


def get_settings_service() -> SettingsService:
    """Get the global settings service."""
    return ApplicationContext.get_global().get_service(SettingsService)


def get_thread_service() -> ThreadService:
    """Get the global thread service."""
    return ApplicationContext.get_global().get_service(ThreadService)


def get_cache_service() -> CacheService:
    """Get the global cache service."""
    return ApplicationContext.get_global().get_service(CacheService)
