"""Unit tests for startup memory and responsiveness policy."""

from __future__ import annotations

from phage_annotator.runtime.operational_policy import (
    MAX_WORKER_THREADS,
    MIN_CACHE_BUDGET_MB,
    build_runtime_policy,
)


def test_runtime_policy_uses_bounded_overrides(monkeypatch) -> None:
    """Verify runtime policy uses bounded overrides for the current workflow."""
    monkeypatch.setenv("PHAGE_ANNOTATOR_MAX_WORKERS", "99")
    monkeypatch.setenv("PHAGE_ANNOTATOR_CACHE_MB", "64")

    policy = build_runtime_policy()

    assert policy.max_worker_threads == MAX_WORKER_THREADS
    assert policy.global_cache_budget_mb == float(MIN_CACHE_BUDGET_MB)


def test_runtime_policy_defaults_are_positive(monkeypatch) -> None:
    """Verify runtime policy defaults are positive for the current workflow."""
    monkeypatch.delenv("PHAGE_ANNOTATOR_MAX_WORKERS", raising=False)
    monkeypatch.delenv("PHAGE_ANNOTATOR_CACHE_MB", raising=False)

    policy = build_runtime_policy()

    assert 1 <= policy.max_worker_threads <= MAX_WORKER_THREADS
    assert policy.global_cache_budget_mb >= MIN_CACHE_BUDGET_MB
