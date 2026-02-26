"""Integration tests for framework services and ApplicationContext.

Tests that services work together correctly in realistic scenarios.
"""

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


# ============================================================================
# EVENT SERVICE TESTS
# ============================================================================

class TestEventService:
    """Tests for event service."""

    def test_publish_subscribe(self):
        """Test basic publish/subscribe."""
        context = ApplicationContext.create_test()
        event_service = context.get_service(EventService)

        received = []

        def handler(event: CustomTestEvent):
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
            raise RuntimeError("Intentional error")

        def working_handler(e: CustomTestEvent):
            received.append(e)

        event_service.subscribe(CustomTestEvent, failing_handler)
        event_service.subscribe(CustomTestEvent, working_handler)

        # This should not raise
        event_service.publish(CustomTestEvent())

        # Working handler should still receive
        assert len(received) == 1


# ============================================================================
# LOG SERVICE TESTS
# ============================================================================

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


# ============================================================================
# SETTINGS SERVICE TESTS
# ============================================================================

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


# ============================================================================
# THREAD SERVICE TESTS
# ============================================================================

class TestThreadService:
    """Tests for thread service."""

    def test_run_async(self):
        """Test async execution."""
        context = ApplicationContext.create_test()
        threads = context.get_service(ThreadService)

        def work(x, y):
            return x + y

        result = [None]

        def on_done(value):
            result[0] = value

        threads.run_async(work, args=(2, 3), on_done=on_done)
        threads.wait_all(timeout=5.0)

        assert result[0] == 5

    def test_run_async_with_error(self):
        """Test async error handling."""
        context = ApplicationContext.create_test()
        threads = context.get_service(ThreadService)

        def failing_work():
            raise ValueError("oops")

        errors = []

        def on_error(exc):
            errors.append(exc)

        threads.run_async(failing_work, on_error=on_error)
        threads.wait_all(timeout=5.0)

        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)

    def test_wait_all(self):
        """Test waiting for completion."""
        context = ApplicationContext.create_test()
        threads = context.get_service(ThreadService)

        completed = []

        def slow_work(x):
            time.sleep(0.1)
            completed.append(x)

        threads.run_async(slow_work, args=(1,))
        threads.run_async(slow_work, args=(2,))

        threads.wait_all(timeout=5.0)

        assert len(completed) == 2

    def test_is_busy(self):
        """Test busy status."""
        context = ApplicationContext.create_test()
        threads = context.get_service(ThreadService)

        def slow_work():
            time.sleep(0.2)

        assert not threads.is_busy()

        # Start a slow task
        threads.run_async(slow_work)

        # Should be busy here (or at least become busy soon)
        # Give it a tiny bit of time to start
        time.sleep(0.01)

        # Wait for completion
        threads.wait_all(timeout=5.0)
        assert not threads.is_busy()


# ============================================================================
# CACHE SERVICE TESTS
# ============================================================================

class MockCache:
    """Mock cache for testing."""

    def __init__(self):
        self._data = {}

    def stats(self):
        return {
            "size_mb": 100,
            "hits": 1000,
            "misses": 50,
        }

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)

    def clear(self):
        self._data.clear()


class TestCacheService:
    """Tests for cache service."""

    def test_register_and_get_cache(self):
        """Test registering and retrieving caches."""
        context = ApplicationContext.create_test()
        cache_service = context.get_service(CacheService)

        mock_cache = MockCache()
        cache_service.register_cache("test_cache", mock_cache)

        retrieved = cache_service.get_cache("test_cache")
        assert retrieved is mock_cache

    def test_get_stats(self):
        """Test getting stats from all caches."""
        context = ApplicationContext.create_test()
        cache_service = context.get_service(CacheService)

        cache1 = MockCache()
        cache2 = MockCache()

        cache_service.register_cache("cache1", cache1)
        cache_service.register_cache("cache2", cache2)

        stats = cache_service.get_stats()

        assert "cache1" in stats
        assert "cache2" in stats
        assert stats["cache1"]["size_mb"] == 100
        assert stats["cache2"]["hits"] == 1000

    def test_clear_all(self):
        """Test clearing all caches."""
        context = ApplicationContext.create_test()
        cache_service = context.get_service(CacheService)

        cache = MockCache()
        cache.set("key", "value")

        cache_service.register_cache("test", cache)
        cache_service.clear_all()

        assert len(cache._data) == 0

    def test_budget_management(self):
        """Test cache budget tracking."""
        context = ApplicationContext.create_test()
        cache_service = context.get_service(CacheService)

        budget = cache_service.get_global_budget()
        assert budget > 0

        cache_service.set_global_budget(2048.0)
        assert cache_service.get_global_budget() == 2048.0


# ============================================================================
# APPLICATION CONTEXT TESTS
# ============================================================================

class TestApplicationContext:
    """Tests for context creation and service lookup."""

    def test_create_default(self):
        """Test creating default context."""
        context = ApplicationContext.create_default()

        # All services should be available
        assert context.get_service(EventService) is not None
        assert context.get_service(LogService) is not None
        assert context.get_service(SettingsService) is not None
        assert context.get_service(ThreadService) is not None
        assert context.get_service(CacheService) is not None

    def test_create_test(self):
        """Test creating test context."""
        context = ApplicationContext.create_test()
        assert context.get_service(EventService) is not None

    def test_create_headless(self):
        """Test creating headless context."""
        context = ApplicationContext.create_headless()
        assert context.get_service(LogService) is not None

    def test_service_singleton_within_context(self):
        """Test that services are singletons within a context."""
        context = ApplicationContext.create_default()

        service1 = context.get_service(EventService)
        service2 = context.get_service(EventService)

        assert service1 is service2

    def test_set_service_override(self):
        """Test overriding a service."""
        from phage_annotator.framework.services import DefaultCacheService

        context = ApplicationContext.create_test()

        original = context.get_service(CacheService)

        new_cache = DefaultCacheService(global_budget_mb=512.0)
        context.set_service(CacheService, new_cache)

        retrieved = context.get_service(CacheService)
        assert retrieved is new_cache
        assert retrieved is not original

    def test_global_context(self):
        """Test global context setting/getting."""
        context = ApplicationContext.create_test()
        ApplicationContext.set_global(context)

        retrieved = ApplicationContext.get_global()
        assert retrieved is context

    def test_helper_functions(self):
        """Test module-level helper functions."""
        context = ApplicationContext.create_test()
        ApplicationContext.set_global(context)

        # These should work without exception
        event_svc = get_event_service()
        log_svc = get_log_service()
        settings_svc = get_settings_service()
        thread_svc = get_thread_service()
        cache_svc = get_cache_service()

        assert isinstance(event_svc, EventService)
        assert isinstance(log_svc, LogService)
        assert isinstance(settings_svc, SettingsService)
        assert isinstance(thread_svc, ThreadService)
        assert isinstance(cache_svc, CacheService)

    def test_shutdown(self):
        """Test graceful shutdown."""
        context = ApplicationContext.create_default()
        # Should not raise
        context.shutdown()

    def test_custom_config(self):
        """Test custom configuration."""
        config = ContextConfig(
            log_level="DEBUG",
            max_worker_threads=8,
            global_cache_budget_mb=2048.0,
        )
        context = ApplicationContext(config)

        log_service = context.get_service(LogService)
        assert log_service.get_level() == LogLevel.DEBUG

        cache_service = context.get_service(CacheService)
        assert cache_service.get_global_budget() == 2048.0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestServiceIntegration:
    """Tests for services working together."""

    def test_event_trigger_cache_clear(self):
        """Test using events to trigger cache clearing."""
        context = ApplicationContext.create_test()

        event_service = context.get_service(EventService)
        cache_service = context.get_service(CacheService)

        # Setup cache
        cache = MockCache()
        cache.set("key", "value")
        cache_service.register_cache("test", cache)

        # Setup event listener to clear cache on custom event
        class ClearCacheEvent(Event):
            pass

        def on_clear_cache(event: ClearCacheEvent):
            cache_service.clear_all()

        event_service.subscribe(ClearCacheEvent, on_clear_cache)

        # Verify cache has data
        assert len(cache._data) > 0

        # Trigger event
        event_service.publish(ClearCacheEvent())

        # Cache should be cleared
        assert len(cache._data) == 0

    def test_settings_change_logs(self):
        """Test logging when settings change."""
        context = ApplicationContext.create_test()

        settings = context.get_service(SettingsService)
        log_service = context.get_service(LogService)

        logged = []

        class SettingChangedEvent(Event):
            key: str = ""
            value: Any = None

        def on_setting_changed(key: str, value: Any):
            event = SettingChangedEvent(key=key, value=value)
            log_service.info(f"Setting changed: {key}={value}")

        settings.on_changed("test_key", on_setting_changed)

        # This should log without error
        settings.set("test_key", 42)

    def test_async_work_with_events(self):
        """Test async work publishing completion events."""
        context = ApplicationContext.create_test()
        ApplicationContext.set_global(context)

        threads = context.get_service(ThreadService)
        events = context.get_service(EventService)

        class WorkCompleteEvent(Event):
            pass

        completed = []

        def on_complete(event: WorkCompleteEvent):
            completed.append("done")

        events.subscribe(WorkCompleteEvent, on_complete)

        def work(x):
            return x * 2

        def done_callback(result):
            events.publish(WorkCompleteEvent())

        threads.run_async(work, args=(21,), on_done=done_callback)
        threads.wait_all(timeout=5.0)

        assert len(completed) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
