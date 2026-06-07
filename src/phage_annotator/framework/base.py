"""Compatibility exports for UI-agnostic framework service contracts."""

from __future__ import annotations

from typing import TypeVar

from phage_annotator.framework.cache_interface import CacheService
from phage_annotator.framework.event_interface import Event, EventService
from phage_annotator.framework.log_interface import LogLevel, LogService
from phage_annotator.framework.registry_interface import ServiceRegistry, ServiceType
from phage_annotator.framework.settings_interface import SettingsService
from phage_annotator.framework.thread_interface import ThreadService

T = TypeVar("T")

__all__ = [
    "CacheService",
    "Event",
    "EventService",
    "LogLevel",
    "LogService",
    "ServiceRegistry",
    "ServiceType",
    "SettingsService",
    "T",
    "ThreadService",
]
