"""Default headless logging service implementation."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from phage_annotator.framework.base import LogLevel, LogService


class DefaultLogService(LogService):
    """Simple logging service using Python's logging module.

    Sends to stdout/file. UI layer can route to QTextEdit.
    """

    def __init__(self, name: str = "phage.core", level: LogLevel = LogLevel.INFO):
        """Initialize logger."""
        self._logger = logging.getLogger(name)
        self._level = level
        self._logger.setLevel(level.value * 10)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def debug(self, message: str, **context) -> None:
        """Log a debug message with optional structured context."""
        self._log(LogLevel.DEBUG, message, context)

    def info(self, message: str, **context) -> None:
        """Log an informational message with optional structured context."""
        self._log(LogLevel.INFO, message, context)

    def warning(self, message: str, **context) -> None:
        """Log a warning message with optional structured context."""
        self._log(LogLevel.WARNING, message, context)

    def error(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        """Log an error message with optional exception context."""
        self._log(LogLevel.ERROR, message, context, exc_info)

    def critical(self, message: str, exc_info: Optional[Exception] = None, **context) -> None:
        """Log a critical message with optional exception context."""
        self._log(LogLevel.CRITICAL, message, context, exc_info)

    def set_level(self, level: LogLevel) -> None:
        """Set the minimum emitted log level."""
        self._level = level
        self._logger.setLevel(level.value * 10)

    def get_level(self) -> LogLevel:
        """Return the current minimum emitted log level."""
        return self._level

    def _log(
        self,
        level: LogLevel,
        message: str,
        context: Dict[str, Any],
        exc_info: Optional[Exception] = None,
    ) -> None:
        """Format context and delegate to the standard logging backend."""
        if context:
            context_str = " | " + ", ".join(f"{key}={value}" for key, value in context.items())
            message = message + context_str

        if level == LogLevel.DEBUG:
            self._logger.debug(message)
        elif level == LogLevel.INFO:
            self._logger.info(message)
        elif level == LogLevel.WARNING:
            self._logger.warning(message)
        elif level == LogLevel.ERROR:
            self._logger.error(message, exc_info=exc_info)
        elif level == LogLevel.CRITICAL:
            self._logger.critical(message, exc_info=exc_info)
