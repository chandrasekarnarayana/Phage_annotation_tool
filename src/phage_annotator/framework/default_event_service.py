"""Default headless event service implementation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Type

from phage_annotator.framework.base import Event, EventService


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
            for callback in list(callbacks):
                try:
                    callback(event)
                except Exception as exc:
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

        def unsubscribe():
            """Remove the callback from the event subscription list."""
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
                    pass
