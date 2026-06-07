"""Extracted method group 1 for JobManager."""

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




class JobManagerQueueMixin:
    """Method group 1 extracted from JobManager."""

    def __init__(
        self,
        parent: Optional[QtCore.QObject] = None,
        *,
        max_workers: Optional[int] = None,
        max_pending_jobs: Optional[int] = None,
    ) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self._pool = QtCore.QThreadPool(self)
        self._tokens: dict[str, CancelToken] = {}
        self._callbacks: dict[
            str,
            Tuple[
                Optional[Callable[[Any], None]],
                Optional[Callable[[str], None]],
                Optional[Callable[[int, str], None]],
            ],
        ] = {}
        self._job_names: dict[str, str] = {}
        self._job_priorities: dict[str, int] = {}
        self._job_replace_keys: dict[str, str] = {}
        self._job_dependencies: dict[str, Tuple[str, ...]] = {}
        self._running_jobs: set[str] = set()
        self._pending_jobs: Deque[_QueuedJob] = deque()
        self._replace_index: dict[str, str] = {}
        self._queue_counter = 0
        self._ui_busy_provider: Optional[Callable[[], bool]] = None
        self.total_submitted = 0
        self.total_finished = 0
        self.total_cancelled = 0
        self.total_errors = 0
        self._base_max_workers = int(max_workers or self._recommended_worker_count())
        self._max_pending_jobs = int(max_pending_jobs or max(6, self._base_max_workers * 4))
        self._pool.setMaxThreadCount(self._base_max_workers)
        self.job_started.connect(self._record_started)
        self.job_error.connect(self._record_error)
        self.job_cancelled.connect(self._record_cancelled)
        self.job_finished.connect(self._record_finished)
    @staticmethod
    def _recommended_worker_count() -> int:
        """Return a conservative worker count that leaves headroom for the UI."""
        cpu_count = max(1, int(os.cpu_count() or 1))
        if cpu_count <= 2:
            return 1
        if cpu_count <= 4:
            return 2
        if cpu_count <= 8:
            return 3
        return 4
    def set_ui_busy_provider(self, provider: Optional[Callable[[], bool]]) -> None:
        """Set a callable used to reduce background concurrency during UI activity."""
        self._ui_busy_provider = provider
        self._apply_pool_limit()
    def _target_worker_count(self) -> int:
        """Return the current concurrency limit after UI-load adaptation."""
        if self._base_max_workers <= 1:
            return 1
        try:
            ui_busy = bool(self._ui_busy_provider and self._ui_busy_provider())
        except Exception:
            ui_busy = False
        if ui_busy:
            return max(1, self._base_max_workers - 1)
        return self._base_max_workers
    def _apply_pool_limit(self) -> None:
        """Apply the current adaptive worker limit to the Qt thread pool."""
        self._pool.setMaxThreadCount(self._target_worker_count())
    def submit(
        self,
        fn: Callable[..., Any],
        *,
        name: Optional[str] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
        cancel_token: Optional[CancelToken] = None,
        timeout_sec: Optional[float] = None,
        retries: int = 0,
        retry_delay_sec: float = 0.5,
        retry_on: Tuple[type[BaseException], ...] = (Exception,),
        priority: str = "normal",
        replace_key: Optional[str] = None,
        depends_on: Iterable[str] | None = None,
    ) -> JobHandle:
        """Run the submit workflow."""
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
        signals.finished.connect(lambda _name, jid: self._finalize_job(jid))

        if on_result is not None or on_error is not None or on_progress is not None:
            self._callbacks[job_id] = (on_result, on_error, on_progress)

        signals.result.connect(lambda _name, jid, result: self._dispatch_result(jid, result))
        signals.error.connect(lambda _name, jid, err: self._dispatch_error(jid, err))
        signals.progress.connect(lambda _name, jid, value, msg: self._dispatch_progress(jid, value, msg))

        runnable = JobRunnable(job_name, job_id, fn, token, signals)
        self._tokens[job_id] = token
        self._job_names[job_id] = str(job_name)
        self._job_priorities[job_id] = self._priority_value(priority)
        if replace_key:
            self._job_replace_keys[job_id] = str(replace_key)
        dep_ids = tuple(str(dep) for dep in (depends_on or ()) if str(dep))
        if dep_ids:
            self._job_dependencies[job_id] = dep_ids
        self.total_submitted += 1
        handle = JobHandle(
            name=job_name,
            cancel_token=token,
            job_id=job_id,
            replace_key=str(replace_key) if replace_key else None,
        )
        self._enqueue_or_start(
            _QueuedJob(
                runnable=runnable,
                job_id=job_id,
                priority=self._job_priorities[job_id],
                queue_order=self._next_queue_order(),
                replace_key=str(replace_key) if replace_key else None,
                dependencies=dep_ids,
            )
        )
        return handle
    @staticmethod
    def _priority_value(priority: str) -> int:
        """Map string priority into an ordering weight."""
        norm = str(priority).strip().lower()
        if norm in {"high", "interactive"}:
            return 2
        if norm in {"low", "background"}:
            return 0
        return 1
    def _next_queue_order(self) -> int:
        """Handle the next queue order helper flow."""
        self._queue_counter += 1
        return self._queue_counter
    def _enqueue_or_start(self, job: _QueuedJob) -> None:
        """Start a job immediately if capacity exists, otherwise queue it."""
        self._apply_pool_limit()
        if len(self._running_jobs) < self._target_worker_count():
            self._start_job(job)
            return

        if job.replace_key:
            self._drop_replaced_pending_job(job.replace_key)

        if len(self._pending_jobs) >= self._max_pending_jobs:
            if not self._evict_pending_for(job):
                self._cancel_queued_job(job, "queue-saturated")
                return

        self._pending_jobs.append(job)
        if job.replace_key:
            self._replace_index[job.replace_key] = job.job_id
    def _drop_replaced_pending_job(self, replace_key: str) -> None:
        """Remove an older pending job with the same replace key."""
        existing_job_id = self._replace_index.get(str(replace_key))
        if not existing_job_id:
            return
        for pending in list(self._pending_jobs):
            if pending.job_id != existing_job_id:
                continue
            self._pending_jobs.remove(pending)
            self._cancel_queued_job(pending, "replaced")
            break
