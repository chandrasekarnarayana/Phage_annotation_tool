"""Debug logging helpers for GUI internals."""

from __future__ import annotations

from phage_annotator.gui_constants import DEBUG_CACHE
from phage_annotator.logger import get_logger

LOGGER = get_logger(__name__)


def debug_log(msg: str) -> None:
    """Log cache/debug messages when DEBUG_CACHE is enabled."""
    if DEBUG_CACHE:
        LOGGER.debug(msg)
