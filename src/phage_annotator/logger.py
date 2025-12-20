"""Dev-only logging helper for console (and optional GUI hook)."""

from __future__ import annotations

import logging
from typing import Optional

_LOGGER_NAME = "phage_annotator"


class _JobIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = "-"
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for console output.

    Parameters
    ----------
    name : str
        Module name, typically ``__name__``.
    """
    base = logging.getLogger(_LOGGER_NAME)
    if not base.handlers:
        base.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(module)s job=%(job_id)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(_JobIdFilter())
        base.addHandler(handler)
        base.propagate = False
    logger = logging.getLogger(f"{_LOGGER_NAME}.{name}")
    logger.setLevel(base.level)
    return logger


def set_level(level: int) -> None:
    """Update log level for all handlers."""
    base = logging.getLogger(_LOGGER_NAME)
    base.setLevel(level)
    for handler in base.handlers:
        handler.setLevel(level)


def attach_gui_handler(handler: Optional[logging.Handler]) -> None:
    """Optionally attach a GUI handler (e.g., a dock log view)."""
    if handler is None:
        return
    base = logging.getLogger(_LOGGER_NAME)
    if handler not in base.handlers:
        base.addHandler(handler)
