"""Split definitions from test_framework_integration.py."""

from __future__ import annotations

import pytest
import time
import threading
from typing import Any

from phage_annotator.framework import (
    ApplicationContext,
    ContextConfig,
    Event,
    EventService,
    LogLevel,
    LogService,
    SettingsService,
    ThreadService,
    CacheService,
    get_event_service,
    get_log_service,
    get_settings_service,
    get_thread_service,
    get_cache_service,
)


# ============================================================================
# TEST EVENTS
# ============================================================================

class CustomTestEvent(Event):
    """Test event for pub/sub testing."""
    pass

class AnotherCustomEvent(Event):
    """Another test event."""
    pass

class TestEventService:
    """Tests for event service."""

    def test_publish_subscribe(self):
        """Test basic publish/subscribe."""
        context = ApplicationContext.create_test()
        event_service = context.get_service(EventService)

        received = []

        def handler(event: CustomTestEvent):
            """Run the handler workflow."""
            received.append(event)

        unsub = event_service.subscribe(CustomTestEvent, handler)

        # Publish event
        test_event = CustomTestEvent()
        event_service.publish(test_event)

        assert len(received) == 1
        assert received[0].timestamp is not None

    def test_unsubscribe(self):
        """Test unsubscribe."""
        context = ApplicationContext.create_test()
        event_service = context.get_service(EventService)

        received = []

        def handler(event: CustomTestEvent):
            """Run the handler workflow."""
            received.append(event)

        unsub = event_service.subscribe(CustomTestEvent, handler)
        unsub()  # Unsubscribe

        event_service.publish(CustomTestEvent())

        assert len(received) == 0

    def test_multiple_subscribers(self):
        """Test multiple subscribers for same event."""
        context = ApplicationContext.create_test()
        event_service = context.get_service(EventService)

        received1 = []
        received2 = []

        event_service.subscribe(CustomTestEvent, lambda e: received1.append(e))
        event_service.subscribe(CustomTestEvent, lambda e: received2.append(e))

        event_service.publish(CustomTestEvent())

        assert len(received1) == 1
        assert len(received2) == 1

    def test_event_type_filtering(self):
        """Test that events are only delivered to matching types."""
        context = ApplicationContext.create_test()
        event_service = context.get_service(EventService)

        received_test = []
        received_another = []

        event_service.subscribe(CustomTestEvent, lambda e: received_test.append(e))
        event_service.subscribe(AnotherCustomEvent, lambda e: received_another.append(e))

        event_service.publish(CustomTestEvent())
        event_service.publish(AnotherCustomEvent())

        assert len(received_test) == 1
        assert len(received_another) == 1

    def test_subscriber_exception_doesnt_crash_bus(self):
        """Test that exception in one subscriber doesn't block others."""
        context = ApplicationContext.create_test()
        event_service = context.get_service(EventService)

        received = []

        def failing_handler(e: CustomTestEvent):
            """Run the failing handler workflow."""
            raise RuntimeError("Intentional error")

        def working_handler(e: CustomTestEvent):
            """Run the working handler workflow."""
            received.append(e)

        event_service.subscribe(CustomTestEvent, failing_handler)
        event_service.subscribe(CustomTestEvent, working_handler)

        # This should not raise
        event_service.publish(CustomTestEvent())

        # Working handler should still receive
        assert len(received) == 1

class TestLogService:
    """Tests for log service."""

    def test_log_levels(self):
        """Test log level filtering."""
        context = ApplicationContext.create_test()
        log_service = context.get_service(LogService)

        # Starting at DEBUG level, all should work
        log_service.set_level(LogLevel.DEBUG)
        assert log_service.get_level() == LogLevel.DEBUG

        log_service.debug("debug msg")
        log_service.info("info msg")
        log_service.warning("warning msg")

        # Switch to WARNING level
        log_service.set_level(LogLevel.WARNING)
        assert log_service.get_level() == LogLevel.WARNING

        log_service.debug("debug msg (should not appear)")
        log_service.warning("warning msg")

    def test_log_with_context(self):
        """Test logging with context data."""
        context = ApplicationContext.create_test()
        log_service = context.get_service(LogService)

        # Should not raise
        log_service.info("Processing", file="test.tif", size_mb=150)

    def test_log_exception(self):
        """Test logging exceptions."""
        context = ApplicationContext.create_test()
        log_service = context.get_service(LogService)

        try:
            raise ValueError("test error")
        except ValueError as exc:
            # Should not raise
            log_service.error("Failed to process", exc_info=exc)

class TestSettingsService:
    """Tests for settings service."""

    def test_get_set(self):
        """Test basic get/set."""
        context = ApplicationContext.create_test()
        settings = context.get_service(SettingsService)

        settings.set("cache.max_mb", 512)
        assert settings.get("cache.max_mb") == 512

    def test_default_values(self):
        """Test default values."""
        defaults = {"prefetch.enabled": True, "cache.max_mb": 1024}
        config = ContextConfig(settings_defaults=defaults)
        context = ApplicationContext(config)
        settings = context.get_service(SettingsService)

        assert settings.get("prefetch.enabled") is True
        assert settings.get("cache.max_mb") == 1024

    def test_get_nonexistent_with_default(self):
        """Test getting nonexistent key with default."""
        context = ApplicationContext.create_test()
        settings = context.get_service(SettingsService)

        result = settings.get("nonexistent", default="fallback")
        assert result == "fallback"

    def test_on_changed(self):
        """Test change notifications."""
        context = ApplicationContext.create_test()
        settings = context.get_service(SettingsService)

        changes = []

        def on_change(key: str, value: Any):
            """Run the on change workflow."""
            changes.append((key, value))

        unsub = settings.on_changed("cache.max_mb", on_change)

        settings.set("cache.max_mb", 512)
        settings.set("cache.max_mb", 1024)

        assert len(changes) == 2
        assert changes[0] == ("cache.max_mb", 512)
        assert changes[1] == ("cache.max_mb", 1024)

        # Unsubscribe
        unsub()
        settings.set("cache.max_mb", 2048)

        assert len(changes) == 2  # No new change

    def test_get_all(self):
        """Test getting all settings."""
        defaults = {"a": 1, "b": 2}
        config = ContextConfig(settings_defaults=defaults)
        context = ApplicationContext(config)
        settings = context.get_service(SettingsService)

        settings.set("c", 3)

        all_settings = settings.get_all()
        assert all_settings["a"] == 1
        assert all_settings["b"] == 2
        assert all_settings["c"] == 3
