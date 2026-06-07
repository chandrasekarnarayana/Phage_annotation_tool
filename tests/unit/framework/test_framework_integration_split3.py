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

from tests.unit.framework.test_framework_integration_split2 import MockCache

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
            """Run the on clear cache workflow."""
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
            """Run the on setting changed workflow."""
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
            """Run the on complete workflow."""
            completed.append("done")

        events.subscribe(WorkCompleteEvent, on_complete)

        def work(x):
            """Run the work workflow."""
            return x * 2

        def done_callback(result):
            """Run the done callback workflow."""
            events.publish(WorkCompleteEvent())

        threads.run_async(work, args=(21,), on_done=done_callback)
        threads.wait_all(timeout=5.0)

        assert len(completed) == 1
