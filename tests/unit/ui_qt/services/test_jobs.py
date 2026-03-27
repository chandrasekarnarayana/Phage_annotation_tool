"""Unit tests for JobManager public job-control API."""

from __future__ import annotations

from concurrent.futures import Future

from phage_annotator.ui_qt.services.jobs import CancelToken, JobManager


def test_active_job_count_tracks_tokens() -> None:
    jobs = JobManager()
    assert jobs.active_job_count() == 0
    jobs._tokens["job-1"] = CancelToken()
    jobs._tokens["job-2"] = CancelToken()
    assert jobs.active_job_count() == 2


def test_cancel_existing_job_marks_token_cancelled() -> None:
    jobs = JobManager()
    token = CancelToken()
    jobs._tokens["job-1"] = token
    assert jobs.cancel("job-1") is True
    assert token.is_cancelled() is True


def test_cancel_missing_job_returns_false() -> None:
    jobs = JobManager()
    assert jobs.cancel("missing") is False


def test_finalize_job_releases_callbacks_and_running_state() -> None:
    jobs = JobManager(max_workers=1, max_pending_jobs=1)
    jobs._tokens["job-1"] = CancelToken()
    jobs._callbacks["job-1"] = (lambda _result: None, None, None)
    jobs._running_jobs.add("job-1")

    jobs._finalize_job("job-1")

    assert "job-1" not in jobs._tokens
    assert "job-1" not in jobs._callbacks
    assert "job-1" not in jobs._running_jobs


def test_target_worker_count_reduces_when_ui_busy() -> None:
    jobs = JobManager(max_workers=3)
    jobs.set_ui_busy_provider(lambda: True)
    assert jobs._target_worker_count() == 2


def test_enqueue_or_start_drops_when_queue_is_saturated(qtbot) -> None:
    jobs = JobManager(max_workers=1, max_pending_jobs=1)
    started: list[str] = []
    cancelled: list[str] = []
    finished: list[str] = []
    jobs.job_cancelled.connect(lambda _name, jid: cancelled.append(jid))
    jobs.job_finished.connect(lambda _name, jid: finished.append(jid))
    jobs._start_job = lambda job: started.append(job.job_id) or jobs._running_jobs.add(job.job_id)  # type: ignore[method-assign]

    first = jobs.submit(lambda: 1, name="first", priority="normal")
    second = jobs.submit(lambda: 2, name="second", priority="background")
    third = jobs.submit(lambda: 3, name="third", priority="background")
    qtbot.wait(20)

    assert started == [first.job_id]
    assert [job.job_id for job in jobs._pending_jobs] == [second.job_id]
    assert third.cancel_token.is_cancelled() is True
    assert third.job_id in cancelled
    assert third.job_id in finished


def test_queue_snapshot_reports_blocked_dependencies() -> None:
    jobs = JobManager(max_workers=1, max_pending_jobs=4)
    jobs._start_job = lambda job: jobs._running_jobs.add(job.job_id)  # type: ignore[method-assign]

    first = jobs.submit(lambda: 1, name="first")
    second = jobs.submit(lambda: 2, name="second", depends_on=(first.job_id,))

    snapshot = jobs.queue_snapshot()

    assert snapshot.active_count == 1
    assert snapshot.pending_count == 1
    assert snapshot.blocked_count == 1
    assert snapshot.pending[0].state == "blocked"
    assert snapshot.pending[0].blocked_by == (first.job_id,)
    assert second.job_id == snapshot.pending[0].job_id


def test_cancel_pending_job_removes_it_from_queue(qtbot) -> None:
    jobs = JobManager(max_workers=1, max_pending_jobs=4)
    jobs._start_job = lambda job: jobs._running_jobs.add(job.job_id)  # type: ignore[method-assign]

    first = jobs.submit(lambda: 1, name="first")
    second = jobs.submit(lambda: 2, name="second")

    assert first.job_id in jobs._running_jobs
    assert second.job_id in [job.job_id for job in jobs._pending_jobs]
    assert jobs.cancel(second.job_id) is True
    qtbot.wait(20)

    assert second.job_id not in [job.job_id for job in jobs._pending_jobs]
    assert second.cancel_token.is_cancelled() is True


def test_cancel_matching_cancels_pending_replace_key_only(qtbot) -> None:
    jobs = JobManager(max_workers=1, max_pending_jobs=4)
    jobs._start_job = lambda job: jobs._running_jobs.add(job.job_id)  # type: ignore[method-assign]

    jobs.submit(lambda: 1, name="first", replace_key="projection")
    second = jobs.submit(lambda: 2, name="second", replace_key="projection")
    third = jobs.submit(lambda: 3, name="third", replace_key="other")

    cancelled = jobs.cancel_matching(replace_key="projection", include_running=False)
    qtbot.wait(20)

    assert second.job_id in cancelled
    assert third.job_id not in cancelled
    assert second.job_id not in [job.job_id for job in jobs._pending_jobs]
