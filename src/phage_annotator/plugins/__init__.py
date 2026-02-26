"""Plugin space for extending the application (FIJI Layer 7).

This package implements the Plugin Layer in the FIJI architecture,
providing extension points for third-party functionality without
modifying core code.

**Layer 7 Responsibilities**:
- Plugin discovery: Load plugins from entry_points
- Plugin API: Interfaces for custom commands, tools, and widgets
- Registration: Plugins register with command registry and service bus
- Lifecycle: Plugin initialization, activation, and teardown
- Isolation: Plugins run in separate namespace

**Key Concepts**:
1. **Entry points**: setuptools mechanism for plugin discovery
2. **Service bus**: Plugins publish/subscribe via EventService
3. **Command registry**: Plugins register custom commands
4. **Widget extension**: Plugins can add UI panels
5. **Graceful failure**: Failed plugins don't crash application

**Plugin Architecture**:
    Plugin loads at startup
    → Calls plugin.load_plugin(context)
    → Plugin registers commands
       via context.register_command("my_command", my_handler)
    → Plugin subscribes to events
       via context.get_event_service().subscribe(MyEvent, callback)
    → Plugin adds UI
       via context.get_ui_service().add_panel(MyPanel)

**Plugin Entry Points**:
    [phage_annotator.plugins]
    my_plugin = my_plugin.plugin:load_plugin
    
    # Called when application starts
    def load_plugin(context: ApplicationContext):
        context.register_command("my_plugin.action", my_action_handler)
        context.get_event_service().subscribe(
            AnnotationChangedEvent,
            on_annotation_changed
        )

**From Plugin Code**:
    from phage_annotator.framework import get_event_service, get_log_service
    
    def on_annotation_changed(event):
        logger = get_log_service().get_logger("my_plugin")
        logger.info(f"Annotations changed: {event.image_id}")
        # Custom analysis or workflow

**Dependency Guidelines for Plugin Developers**:
- ✅ OK to depend on: core, data, algorithms, cache, framework
- ✅ OK to depend on: ui_qt (if writing GUI extensions)
- ❌ Don't depend on: other plugins (circular)
- ❌ Don't import main/__main__ (circular)

**Plugin Best Practices**:
1. Keep plugins focused (one feature per plugin)
2. Use event bus for communication (not direct imports)
3. Handle all exceptions gracefully
4. Clean up resources in shutdown hooks
5. Test plugins with mocked services
6. Document plugin commands and events

**Phase Progress**:
- Phase 1-2: Initial plugin architecture
- Phase 8: Plugin infrastructure refinement
- Phase 9: Full FIJI documentation and integration complete
"""

__all__ = []
