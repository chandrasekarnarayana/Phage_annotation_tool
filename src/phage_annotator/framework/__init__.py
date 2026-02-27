"""Framework and service infrastructure (Layer 5).

This package implements the Framework Layer,
providing service interfaces and dependency injection for all application
components. It is the wiring that enables loose coupling throughout.

**Layer 5 Responsibilities**:
- Service interfaces: EventService, LogService, SettingsService, etc.
- Service implementations: Default, headless-friendly implementations
- Application context: Central service registry and lifecycle management
- Event bus: Pub/sub for decoupled communication
- Configuration: Global settings access
- Threading: Background task execution with callbacks

**Key Concepts**:
1. **ApplicationContext**: Central registry for all services
2. **Service interfaces**: Abstract base classes (never concrete)
3. **Event bus**: Losely-coupled pub/sub communication
4. **Headless compatibility**: No Qt in framework layer
5. **Plugin architecture**: Services can be swapped at startup

**Dependencies**:
- None on application code (pure infrastructure)
- Only on Python stdlib + dataclasses
- Can be used standalone for CLI apps

**Design Patterns**:
- Service locator: get_event_service(), get_log_service(), etc.
- Dependency injection: ApplicationContext.set_service()
- Factory pattern: Default implementations created on demand
- Pub/sub pattern: EventService.publish/subscribe

**Usage - Application Startup**:
    from phage_annotator.framework.context import ApplicationContext
    
    # Create and initialize context
    context = ApplicationContext.create_default()
    ApplicationContext.set_global(context)
    
    # Now services available anywhere via getters
    from phage_annotator.framework import get_event_service
    event_service = get_event_service()

**Usage - Service Access**:
    from phage_annotator.framework import (
        get_event_service,
        get_log_service,
        get_settings_service,
    )
    
    # Publish events (decoupled communication)
    event_service = get_event_service()
    event_service.publish(AnnotationChangedEvent(...))
    
    # Structured logging
    logger = get_log_service().get_logger(__name__)
    logger.info("Application started")

**Usage - Testing**:
    from phage_annotator.framework import ApplicationContext
    
    # Create test context with mocks
    context = ApplicationContext.create_test()
    context.set_service(LogService, MockLogService())
    ApplicationContext.set_global(context)

**Architecture Evolution**:
- Initial service architecture
- Event system refinement and integration
- Full documentation and GUI integration complete
"""

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
from phage_annotator.framework.services import (
    DefaultEventService,
    DefaultLogService,
    DefaultSettingsService,
    DefaultThreadService,
    DefaultCacheService,
    DefaultServiceRegistry,
)
from phage_annotator.framework.context import (
    ApplicationContext,
    ContextConfig,
    get_event_service,
    get_log_service,
    get_settings_service,
    get_thread_service,
    get_cache_service,
)
from phage_annotator.framework.command import (
    Command,
    CommandRegistry,
    get_registry,
    set_registry,
)
from phage_annotator.framework.plugin import (
    Plugin,
    PluginManager,
    get_plugin_manager,
    set_plugin_manager,
)

__all__ = [
    # Interfaces
    "Event",
    "EventService",
    "LogLevel",
    "LogService",
    "SettingsService",
    "ThreadService",
    "CacheService",
    "ServiceRegistry",
    # Implementations
    "DefaultEventService",
    "DefaultLogService",
    "DefaultSettingsService",
    "DefaultThreadService",
    "DefaultCacheService",
    "DefaultServiceRegistry",
    # Context
    "ApplicationContext",
    "ContextConfig",
    "get_event_service",
    "get_log_service",
    "get_settings_service",
    "get_thread_service",
    "get_cache_service",
    # Command system
    "Command",
    "CommandRegistry",
    "get_registry",
    "set_registry",
    # Plugin system
    "Plugin",
    "PluginManager",
    "get_plugin_manager",
    "set_plugin_manager",
]
