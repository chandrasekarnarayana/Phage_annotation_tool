"""Event data and event-service interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type


@dataclass
class Event:
    """Base class for all events on the event bus."""

    source: Any = None
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Normalize derived state after dataclass initialization."""
        if self.metadata is None:
            self.metadata = {}


class EventService(ABC):
    """Publish/subscribe event bus for loose coupling."""

    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""

    @abstractmethod
    def subscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
    ) -> Callable[[], None]:
        """Subscribe to events of a specific type."""

    @abstractmethod
    def unsubscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
    ) -> None:
        """Unsubscribe from a specific event type."""
