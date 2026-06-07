"""Compatibility layer exposing the Qt job manager from framework namespace.

This module avoids importing Qt modules at import time so framework checks can
remain Qt-free while preserving the historical import path:

    """

from __future__ import annotations

from importlib import import_module
from typing import Any

_SYMBOLS = {"CancelToken", "JobHandle", "JobManager", "JobRunnable", "JobSignals"}
__all__ = sorted(_SYMBOLS)


def __getattr__(name: str) -> Any:
    """Delegate unknown attribute access to the wrapped value."""
    if name not in _SYMBOLS:
        raise AttributeError(name)
    module = import_module("phage_annotator.ui_qt.services.jobs")
    return getattr(module, name)
