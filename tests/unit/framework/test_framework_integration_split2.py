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

class TestThreadService:
    """Tests for thread service."""

    def test_run_async(self):
        """Test async execution."""
        context = ApplicationContext.create_test()
        threads = context.get_service(ThreadService)

        def work(x, y):
            """Run the work workflow."""
            return x + y

        result = [None]

        def on_done(value):
            """Run the on done workflow."""
            result[0] = value

        threads.run_async(work, args=(2, 3), on_done=on_done)
        threads.wait_all(timeout=5.0)

        assert result[0] == 5

    def test_run_async_with_error(self):
        """Test async error handling."""
        context = ApplicationContext.create_test()
        threads = context.get_service(ThreadService)

        def failing_work():
            """Run the failing work workflow."""
            raise ValueError("oops")

        errors = []

        def on_error(exc):
            """Run the on error workflow."""
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
            """Run the slow work workflow."""
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
            """Run the slow work workflow."""
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

class MockCache:
    """Mock cache for testing."""

    def __init__(self):
        """Initialize the object and prepare its runtime state."""
        self._data = {}

    def stats(self):
        """Return the stats value."""
        return {
            "size_mb": 100,
            "hits": 1000,
            "misses": 50,
        }

    def set(self, key, value):
        """Set set for the current workflow."""
        self._data[key] = value

    def get(self, key):
        """Return get for the current workflow."""
        return self._data.get(key)

    def clear(self):
        """Clear clear for the current workflow."""
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
