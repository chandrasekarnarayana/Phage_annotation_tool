"""Log-service interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class LogService(ABC):
    """Structured logging interface for headless operation."""

    @abstractmethod
    def debug(self, message: str, **context) -> None:
        """Log debug message."""

    @abstractmethod
    def info(self, message: str, **context) -> None:
        """Log info message."""

    @abstractmethod
    def warning(self, message: str, **context) -> None:
        """Log warning message."""

    @abstractmethod
    def error(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        """Log error message."""

    @abstractmethod
    def critical(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        """Log critical message."""

    @abstractmethod
    def set_level(self, level: LogLevel) -> None:
        """Set minimum log level."""

    @abstractmethod
    def get_level(self) -> LogLevel:
        """Get current log level."""
