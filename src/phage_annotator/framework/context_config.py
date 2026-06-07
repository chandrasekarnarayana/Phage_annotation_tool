"""Configuration model for application context initialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from phage_annotator.framework.base import (
    CacheService,
    EventService,
    LogService,
    SettingsService,
    ThreadService,
)


@dataclass
class ContextConfig:
    """Configuration for ApplicationContext initialization."""

    log_level: str = "INFO"
    log_file: Optional[str] = None
    max_worker_threads: int = 4
    global_cache_budget_mb: float = 1024.0
    settings_defaults: Optional[Dict[str, Any]] = None
    event_service: Optional[EventService] = None
    log_service: Optional[LogService] = None
    settings_service: Optional[SettingsService] = None
    thread_service: Optional[ThreadService] = None
    cache_service: Optional[CacheService] = None
