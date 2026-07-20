"""Extracted method group 1 for JobManager."""

from __future__ import annotations

import inspect
import os
import threading
import traceback
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Iterable, Optional, Tuple, TYPE_CHECKING

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.utils.logger import get_logger

if TYPE_CHECKING:
    # phage_annotator.ui_qt.services.jobs imports this module (as part of
    # JobManager's mixin composition) before CancelToken/JobSignals/
    # JobHandle/_QueuedJob/JobRunnable are defined, so a top-level runtime
    # import here would be circular. This import is for static analysis
    # only; `submit()` below does the equivalent import lazily at call time
    # (by which point phage_annotator.ui_qt.services.jobs has fully loaded).
    from phage_annotator.ui_qt.services.jobs import (
        CancelToken,
        JobHandle,
        JobRunnable,
        JobSignals,
        JobSnapshot,
        JobTelemetry,
        _QueuedJob,
    )

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
        # Deferred import to avoid a circular import with
        # phage_annotator.ui_qt.services.jobs (see TYPE_CHECKING note above).
        from phage_annotator.ui_qt.services.jobs import (
            CancelToken,
            JobHandle,
            JobRunnable,
            JobSignals,
            _QueuedJob,
        )

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
    def _evict_pending_for(self, incoming: _QueuedJob) -> bool:
        """Evict a lower-priority pending job to make room for a new one."""
        candidate: Optional[_QueuedJob] = None
        for pending in self._pending_jobs:
            if pending.priority > incoming.priority:
                continue
            if candidate is None or (pending.priority, pending.queue_order) < (
                candidate.priority,
                candidate.queue_order,
            ):
                candidate = pending
        if candidate is None:
            return False
        self._pending_jobs.remove(candidate)
        self._cancel_queued_job(candidate, "backpressure")
        return True
    def _cancel_queued_job(self, job: _QueuedJob, reason: str) -> None:
        """Cancel a queued job that could not be admitted."""
        token = self._tokens.get(job.job_id)
        if token is not None:
            token.cancel()
        if job.replace_key:
            self._replace_index.pop(job.replace_key, None)
        QtCore.QTimer.singleShot(
            0,
            lambda name=job.runnable.name, jid=job.job_id: (
                self.job_cancelled.emit(name, jid),
                self.job_finished.emit(name, jid),
            ),
        )
        LOGGER.debug("Dropped queued job %s (%s)", job.runnable.name, reason, extra={"job_id": job.job_id})
    def _start_job(self, job: _QueuedJob) -> None:
        """Start a queued job on the bounded Qt thread pool."""
        self._running_jobs.add(job.job_id)
        if job.replace_key:
            self._replace_index.pop(job.replace_key, None)
        self._pool.start(job.runnable)
    def cancel_all(self) -> None:
        """Cancel all running jobs."""
        for token in list(self._tokens.values()):
            token.cancel()
    def cancel_matching(
        self,
        *,
        replace_key: Optional[str] = None,
        name_contains: Optional[str] = None,
        include_running: bool = True,
        include_pending: bool = True,
    ) -> list[str]:
        """Cancel jobs matching simple queue-facing selectors.

        Parameters are intentionally narrow so GUI code can expose selective
        cancellation without reimplementing queue traversal logic.
        """
        cancelled: list[str] = []
        if include_pending:
            for pending in list(self._pending_jobs):
                if not self._job_matches(
                    pending.job_id,
                    replace_key=replace_key,
                    name_contains=name_contains,
                ):
                    continue
                self._pending_jobs.remove(pending)
                self._cancel_queued_job(pending, "selective-cancel")
                cancelled.append(pending.job_id)
        if include_running:
            for job_id, token in list(self._tokens.items()):
                if job_id not in self._running_jobs:
                    continue
                if not self._job_matches(
                    job_id,
                    replace_key=replace_key,
                    name_contains=name_contains,
                ):
                    continue
                token.cancel()
                cancelled.append(job_id)
        return cancelled
    def cancel(self, job_id: str) -> bool:
        """Cancel a specific running job by id."""
        normalized_job_id = str(job_id)
        for pending in list(self._pending_jobs):
            if pending.job_id != normalized_job_id:
                continue
            self._pending_jobs.remove(pending)
            self._cancel_queued_job(pending, "user-cancel")
            return True
        token = self._tokens.get(normalized_job_id)
        if token is None:
            return False
        token.cancel()
        return True
    def queue_snapshot(self) -> "JobTelemetry":
        """Return a structured queue/running snapshot for diagnostics widgets."""
        from phage_annotator.ui_qt.services.jobs import JobSnapshot, JobTelemetry

        running: list[JobSnapshot] = []
        for job_id in sorted(self._running_jobs):
            running.append(
                JobSnapshot(
                    job_id=str(job_id),
                    name=self._job_names.get(job_id, str(job_id)),
                    state="running",
                    priority=int(self._job_priorities.get(job_id, 1)),
                    queue_order=0,
                    replace_key=self._job_replace_keys.get(job_id),
                    dependencies=self._job_dependencies.get(job_id, ()),
                    blocked_by=(),
                )
            )
        pending: list[JobSnapshot] = []
        blocked_count = 0
        for job in sorted(self._pending_jobs, key=lambda item: (-item.priority, item.queue_order)):
            blocked_by = self._blocked_dependencies(job.dependencies)
            if blocked_by:
                blocked_count += 1
            pending.append(
                JobSnapshot(
                    job_id=job.job_id,
                    name=job.runnable.name,
                    state="blocked" if blocked_by else "queued",
                    priority=job.priority,
                    queue_order=job.queue_order,
                    replace_key=job.replace_key,
                    dependencies=job.dependencies,
                    blocked_by=blocked_by,
                )
            )
        return JobTelemetry(
            active_count=len(running),
            pending_count=len(pending),
            blocked_count=blocked_count,
            total_submitted=int(self.total_submitted),
            total_finished=int(self.total_finished),
            total_cancelled=int(self.total_cancelled),
            total_errors=int(self.total_errors),
            max_pending_jobs=int(self._max_pending_jobs),
            running=tuple(running),
            pending=tuple(pending),
        )
    def active_job_count(self) -> int:
        """Return count of currently tracked active jobs."""
        return int(len(self._tokens))
    def _finalize_job(self, job_id: str) -> None:
        """Release per-job state and admit the next queued job."""
        self._tokens.pop(job_id, None)
        self._callbacks.pop(job_id, None)
        self._running_jobs.discard(job_id)
        self._job_dependencies.pop(job_id, None)
        self._job_names.pop(job_id, None)
        self._job_priorities.pop(job_id, None)
        self._job_replace_keys.pop(job_id, None)
        self._drain_pending_jobs()
    def _drain_pending_jobs(self) -> None:
        """Start queued jobs while capacity remains available."""
        self._apply_pool_limit()
        while self._pending_jobs and len(self._running_jobs) < self._target_worker_count():
            next_job = self._pick_next_pending_job()
            if next_job is None:
                break
            self._start_job(next_job)
    def _pick_next_pending_job(self) -> Optional["_QueuedJob"]:
        """Return the highest-priority pending job, preserving FIFO within a priority."""
        if not self._pending_jobs:
            return None
        ready_jobs = [job for job in self._pending_jobs if not self._blocked_dependencies(job.dependencies)]
        if not ready_jobs:
            return None
        best = min(ready_jobs, key=lambda job: (-job.priority, job.queue_order))
        self._pending_jobs.remove(best)
        return best
    def _blocked_dependencies(self, dependencies: Iterable[str]) -> Tuple[str, ...]:
        """Return the subset of dependencies that are not yet finished."""
        blocked: list[str] = []
        for dep in dependencies:
            dep_id = str(dep)
            if dep_id in self._tokens or any(job.job_id == dep_id for job in self._pending_jobs):
                blocked.append(dep_id)
        return tuple(blocked)
