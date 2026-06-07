"""Background job helpers using Qt thread pool.

This module provides a minimal job system built on QThreadPool + QRunnable
with GUI-thread callbacks via Qt signals. It supports progress updates and
cooperative cancellation via a thread-safe CancelToken.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from matplotlib.backends.qt_compat import QtCore
from typing import Any, Callable, Deque, Iterable, Optional, Tuple
import inspect
import os
import threading
import time as _time
import traceback
import uuid

from phage_annotator.utils.logger import get_logger
from phage_annotator.ui_qt.services.job_manager_exec import JobManagerExecMixin
from phage_annotator.ui_qt.services.job_manager_queue import JobManagerQueueMixin


LOGGER = get_logger(__name__)
Signal = QtCore.pyqtSignal if hasattr(QtCore, "pyqtSignal") else QtCore.Signal



class CancelToken:
    """Thread-safe cancellation token.

    Notes
    -----
    Cancellation is cooperative: workers must check ``is_cancelled()``.
    """

    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self._lock = threading.Lock()
        self._cancelled = False

    def cancel(self) -> None:
        """Run the cancel workflow."""
        with self._lock:
            self._cancelled = True

    def is_cancelled(self) -> bool:
        """Return whether cancelled is true for the current state."""
        with self._lock:
            return self._cancelled

class JobSignals(QtCore.QObject):
    """Qt signals for job lifecycle events.

    Signals are emitted from the worker thread and delivered on the GUI thread
    by Qt's queued connection mechanism.
    """

    started = Signal(str, str)
    progress = Signal(str, str, int, str)
    result = Signal(str, str, object)
    error = Signal(str, str, str)
    cancelled = Signal(str, str)
    finished = Signal(str, str)

    def __init__(self, name: str, job_id: str) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.name = name
        self.job_id = job_id

@dataclass
class JobHandle:
    """Handle returned from JobManager.submit.

    Attributes
    ----------
    name : str
        Job name used for display/logging.
    cancel_token : CancelToken
        Cooperative cancellation token for this job.
    job_id : str
        Unique identifier for job tracking and logging.
    """

    name: str
    cancel_token: CancelToken
    job_id: str
    replace_key: Optional[str] = None

@dataclass
class _QueuedJob:
    """Internal queued job descriptor.

    Jobs are admitted through a bounded pending queue so weaker machines do not
    accumulate unbounded background pressure while the UI remains active.
    """

    runnable: JobRunnable
    job_id: str
    priority: int
    queue_order: int
    replace_key: Optional[str] = None
    dependencies: Tuple[str, ...] = ()

@dataclass(frozen=True)
class JobSnapshot:
    """Immutable summary of one running or queued job."""

    job_id: str
    name: str
    state: str
    priority: int
    queue_order: int
    replace_key: Optional[str]
    dependencies: Tuple[str, ...]
    blocked_by: Tuple[str, ...]

@dataclass(frozen=True)
class JobTelemetry:
    """Public queue and lifecycle telemetry for diagnostics surfaces."""

    active_count: int
    pending_count: int
    blocked_count: int
    total_submitted: int
    total_finished: int
    total_cancelled: int
    total_errors: int
    max_pending_jobs: int
    running: Tuple[JobSnapshot, ...]
    pending: Tuple[JobSnapshot, ...]

class JobRunnable(QtCore.QRunnable):
    """QRunnable wrapper that emits JobSignals.

    All signals are emitted from the worker thread but delivered to the GUI
    thread via Qt's signal/slot mechanism.
    """

    def __init__(
        self,
        name: str,
        job_id: str,
        fn: Callable[..., Any],
        cancel_token: CancelToken,
        signals: JobSignals,
    ) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.name = name
        self.job_id = job_id
        self.fn = fn
        self.cancel_token = cancel_token
        self.signals = signals

    def run(self) -> None:
        """Run run for the current workflow."""
        start_ts = _time.monotonic()
        self.signals.started.emit(self.name, self.job_id)
        LOGGER.info("Job started: %s", self.name, extra={"job_id": self.job_id})
        if self.cancel_token.is_cancelled():
            self.signals.cancelled.emit(self.name, self.job_id)
            self.signals.finished.emit(self.name, self.job_id)
            LOGGER.info("Job cancelled before run: %s", self.name, extra={"job_id": self.job_id})
            return

        def progress(value: Optional[int] = None, message: str = "") -> None:
            """Run the progress workflow."""
            val = 0 if value is None else int(max(0, min(100, value)))
            self.signals.progress.emit(self.name, self.job_id, val, message)

        try:
            result = _call_job(self.fn, progress, self.cancel_token)
            if self.cancel_token.is_cancelled():
                self.signals.cancelled.emit(self.name, self.job_id)
                LOGGER.info("Job cancelled: %s", self.name, extra={"job_id": self.job_id})
            else:
                self.signals.result.emit(self.name, self.job_id, result)
                LOGGER.info("Job finished: %s", self.name, extra={"job_id": self.job_id})
        except Exception:
            err = traceback.format_exc()
            self.signals.error.emit(self.name, self.job_id, err)
            LOGGER.error("Job error: %s\n%s", self.name, err, extra={"job_id": self.job_id})
        finally:
            dur = _time.monotonic() - start_ts
            LOGGER.info("Job finished (%.2fs): %s", dur, self.name, extra={"job_id": self.job_id})
            self.signals.finished.emit(self.name, self.job_id)


LOGGER = get_logger(__name__)




class JobManager(JobManagerQueueMixin, JobManagerExecMixin, QtCore.QObject):
    """Submit and manage background jobs with GUI-thread callbacks.

Invariants
----------
- Callbacks are executed on the GUI thread via Qt signals.
- Cancellation is cooperative via CancelToken."""

    job_started = Signal(str, str)
    job_progress = Signal(str, str, int, str)
    job_result = Signal(str, str, object)
    job_error = Signal(str, str, str)
    job_cancelled = Signal(str, str)
    job_finished = Signal(str, str)


LOGGER = get_logger(__name__)



def _call_job(
    fn: Callable[..., Any],
    progress: Callable[[Optional[int], str], None],
    cancel_token: CancelToken,
) -> Any:
    """Handle the call job helper flow."""
    sig = inspect.signature(fn)
    params = sig.parameters
    # Check for both 'cancel_token' and 'cancel' parameter names
    has_cancel = "cancel_token" in params or "cancel" in params
    cancel_param_name = "cancel_token" if "cancel_token" in params else "cancel"
    
    if "progress" in params and has_cancel:
        return fn(progress=progress, **{cancel_param_name: cancel_token})
    if "progress" in params:
        return fn(progress=progress)
    if has_cancel:
        return fn(**{cancel_param_name: cancel_token})
    return fn()
