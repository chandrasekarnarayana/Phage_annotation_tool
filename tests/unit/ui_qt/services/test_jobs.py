"""Unit tests for JobManager public job-control API."""

from __future__ import annotations

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
