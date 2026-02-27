"""Unit tests for reviewer workflow analytics."""

from __future__ import annotations

from phage_annotator.analysis.reviewer_analytics import (
    build_reviewer_dashboard_text,
    compute_issue_trend,
    compute_reviewer_metrics,
)


def test_compute_reviewer_metrics_aggregates_by_user() -> None:
    audit_log = [
        {"timestamp": 10.0, "user": "alice", "event_type": "annotation_added", "details": {}},
        {"timestamp": 20.0, "user": "alice", "event_type": "annotation_updated", "details": {}},
        {"timestamp": 40.0, "user": "alice", "event_type": "review_state_updated", "details": {"count": 2}},
        {"timestamp": 50.0, "user": "bob", "event_type": "annotation_deleted", "details": {}},
        {"timestamp": 60.0, "user": "bob", "event_type": "suggestion_command", "details": {"command": "accept_suggestion"}},
    ]
    metrics = compute_reviewer_metrics(audit_log)
    assert metrics["alice"]["annotations_added"] == 1.0
    assert metrics["alice"]["reviews_completed"] == 2.0
    assert metrics["bob"]["annotations_deleted"] == 1.0
    assert metrics["bob"]["suggestions_accepted"] == 1.0


def test_issue_trend_and_dashboard_text() -> None:
    audit_log = [
        {
            "timestamp": 100.0,
            "user": "alice",
            "event_type": "qc_validation_completed",
            "details": {"image_id": 0, "total_issues": 4, "issue_counts_by_type": {"duplicate": 2}},
        },
        {
            "timestamp": 200.0,
            "user": "alice",
            "event_type": "qc_validation_completed",
            "details": {"image_id": 0, "total_issues": 1, "issue_counts_by_type": {"duplicate": 1}},
        },
    ]
    trend = compute_issue_trend(audit_log)
    assert len(trend) == 2
    assert trend[-1]["total_issues"] == 1
    text = build_reviewer_dashboard_text(audit_log)
    assert "QC issue trend:" in text
    assert "Change vs previous snapshot: -3" in text
