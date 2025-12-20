"""Background job helpers using Qt thread pool.

This module provides a minimal job system built on QThreadPool + QRunnable
with GUI-thread callbacks via Qt signals. It supports progress updates and
cooperative cancellation via a thread-safe CancelToken.
"""

from __future__ import annotations

import inspect
import threading
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.logger import get_logger

LOGGER = get_logger(__name__)

class CancelToken:
    """Thread-safe cancellation token.

    Notes
    -----
    Cancellation is cooperative: workers must check ``is_cancelled()``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled


class JobSignals(QtCore.QObject):
    """Qt signals for job lifecycle events.

    Signals are emitted from the worker thread and delivered on the GUI thread
    by Qt's queued connection mechanism.
    """
    started = QtCore.pyqtSignal(str, str)
    progress = QtCore.pyqtSignal(str, str, int, str)
    result = QtCore.pyqtSignal(str, str, object)
    error = QtCore.pyqtSignal(str, str, str)
    cancelled = QtCore.pyqtSignal(str, str)
    finished = QtCore.pyqtSignal(str, str)

    def __init__(self, name: str, job_id: str) -> None:
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


class JobRunnable(QtCore.QRunnable):
    """QRunnable wrapper that emits JobSignals.

    All signals are emitted from the worker thread but delivered to the GUI
    thread via Qt's signal/slot mechanism.
    """
    def __init__(self, name: str, job_id: str, fn: Callable[..., Any], cancel_token: CancelToken, signals: JobSignals) -> None:
        super().__init__()
        self.name = name
        self.job_id = job_id
        self.fn = fn
        self.cancel_token = cancel_token
        self.signals = signals

    def run(self) -> None:
        self.signals.started.emit(self.name, self.job_id)
        LOGGER.info("Job started: %s", self.name, extra={"job_id": self.job_id})
        if self.cancel_token.is_cancelled():
            self.signals.cancelled.emit(self.name, self.job_id)
            self.signals.finished.emit(self.name, self.job_id)
            LOGGER.info("Job cancelled before run: %s", self.name, extra={"job_id": self.job_id})
            return

        def progress(value: Optional[int] = None, message: str = "") -> None:
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
            self.signals.finished.emit(self.name, self.job_id)


class JobManager(QtCore.QObject):
    """Submit and manage background jobs with GUI-thread callbacks.

    Invariants
    ----------
    - Callbacks are executed on the GUI thread via Qt signals.
    - Cancellation is cooperative via CancelToken.
    """
    job_started = QtCore.pyqtSignal(str, str)
    job_progress = QtCore.pyqtSignal(str, str, int, str)
    job_result = QtCore.pyqtSignal(str, str, object)
    job_error = QtCore.pyqtSignal(str, str, str)
    job_cancelled = QtCore.pyqtSignal(str, str)
    job_finished = QtCore.pyqtSignal(str, str)

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._pool = QtCore.QThreadPool.globalInstance()
        self._tokens: dict[str, CancelToken] = {}
        self._callbacks: dict[str, Tuple[Optional[Callable[[Any], None]], Optional[Callable[[str], None]], Optional[Callable[[int, str], None]]]] = {}

    def submit(
        self,
        fn: Callable[..., Any],
        *,
        name: Optional[str] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> JobHandle:
        job_name = name or getattr(fn, "__name__", "Job")
        token = cancel_token or CancelToken()
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        signals = JobSignals(job_name, job_id)

        signals.started.connect(self.job_started.emit)
        signals.progress.connect(self.job_progress.emit)
        signals.result.connect(self.job_result.emit)
        signals.error.connect(self.job_error.emit)
        signals.cancelled.connect(self.job_cancelled.emit)
        signals.finished.connect(self.job_finished.emit)
        signals.finished.connect(lambda _name, jid: self._tokens.pop(jid, None))

        if on_result is not None:
            self._callbacks[job_id] = (on_result, on_error, on_progress)
        if on_error is not None:
            self._callbacks[job_id] = (on_result, on_error, on_progress)
        if on_progress is not None:
            self._callbacks[job_id] = (on_result, on_error, on_progress)

        signals.result.connect(self._dispatch_result)
        signals.error.connect(self._dispatch_error)
        signals.progress.connect(self._dispatch_progress)
        signals.finished.connect(lambda _name, jid: self._callbacks.pop(jid, None))

        runnable = JobRunnable(job_name, job_id, fn, token, signals)
        self._tokens[job_id] = token
        self._pool.start(runnable)
        return JobHandle(job_name, token, job_id)

    def cancel(self, job_id: str) -> None:
        """Request cancellation for a job by id."""
        token = self._tokens.get(job_id)
        if token is not None:
            token.cancel()

    def cancel_all(self) -> None:
        """Request cancellation for all tracked jobs."""
        for token in list(self._tokens.values()):
            token.cancel()

    def _dispatch_result(self, _name: str, job_id: str, result: object) -> None:
        cb = self._callbacks.get(job_id)
        if cb is None:
            return
        on_result, _, _ = cb
        if on_result is not None:
            on_result(result)

    def _dispatch_error(self, _name: str, job_id: str, err: str) -> None:
        cb = self._callbacks.get(job_id)
        if cb is None:
            return
        _, on_error, _ = cb
        if on_error is not None:
            on_error(err)

    def _dispatch_progress(self, _name: str, job_id: str, value: int, msg: str) -> None:
        cb = self._callbacks.get(job_id)
        if cb is None:
            return
        _, _, on_progress = cb
        if on_progress is not None:
            on_progress(value, msg)


def _call_job(fn: Callable[..., Any], progress: Callable[..., Any], cancel_token: CancelToken) -> Any:
    """Invoke a job function with an optional (progress, cancel_token) signature.

    The helper inspects the function signature to support:
    - fn()
    - fn(progress)
    - fn(progress, cancel_token)
    """
    signature = inspect.signature(fn)
    params = list(signature.parameters.values())
    if any(p.kind == p.VAR_POSITIONAL for p in params):
        return fn(progress, cancel_token)
    if len(params) == 0:
        return fn()
    if len(params) == 1:
        return fn(progress)
    return fn(progress, cancel_token)
