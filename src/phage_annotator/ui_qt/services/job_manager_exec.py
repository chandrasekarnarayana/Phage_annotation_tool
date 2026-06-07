"""Extracted method group 3 for JobManager."""

from __future__ import annotations

import inspect
import os
import threading
import traceback
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Iterable, Optional, Tuple

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.utils.logger import get_logger

LOGGER = get_logger(__name__)




class JobManagerExecMixin:
    """Method group 3 extracted from JobManager."""

    def _job_matches(
        self,
        job_id: str,
        *,
        replace_key: Optional[str],
        name_contains: Optional[str],
    ) -> bool:
        """Handle the job matches helper flow."""
        if replace_key is not None and self._job_replace_keys.get(job_id) != str(replace_key):
            return False
        if name_contains is not None and str(name_contains).strip():
            if str(name_contains).lower() not in self._job_names.get(job_id, "").lower():
                return False
        return True
    def _record_started(self, _name: str, _job_id: str) -> None:
        """Record started for the current workflow."""
        return
    def _record_error(self, _name: str, _job_id: str, _traceback_text: str) -> None:
        """Record error for the current workflow."""
        self.total_errors += 1
    def _record_cancelled(self, _name: str, _job_id: str) -> None:
        """Record cancelled for the current workflow."""
        self.total_cancelled += 1
    def _record_finished(self, _name: str, _job_id: str) -> None:
        """Record finished for the current workflow."""
        self.total_finished += 1
    def _dispatch_result(self, job_id: str, result: Any) -> None:
        """Dispatch result for the current workflow."""
        callbacks = self._callbacks.get(job_id)
        if callbacks and callbacks[0] is not None:
            callbacks[0](result)
    def _dispatch_error(self, job_id: str, err: str) -> None:
        """Dispatch error for the current workflow."""
        callbacks = self._callbacks.get(job_id)
        if callbacks and callbacks[1] is not None:
            callbacks[1](err)
    def _dispatch_progress(self, job_id: str, value: int, msg: str) -> None:
        """Dispatch progress for the current workflow."""
        callbacks = self._callbacks.get(job_id)
        if callbacks and callbacks[2] is not None:
            callbacks[2](value, msg)
