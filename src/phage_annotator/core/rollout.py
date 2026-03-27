"""Feature-flag and baseline instrumentation helpers.

This module keeps rollout toggles and workflow metrics in one small, explicit
place so phased UI/data migrations remain reversible.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping

DEFAULT_FEATURE_FLAGS: Dict[str, bool] = {
    "baseline_workflow_metrics": True,
    "annotation_provenance_schema": True,
    "annotation_table_truth_columns": True,
    "sidebar_workflow_v2": False,
    "right_rail_review_v2": False,
    "review_qc_merge_v2": False,
    "advanced_workspace_v2": False,
    "interactive_learning_experimental": False,
}


def normalize_feature_flags(flags: Mapping[str, Any] | None = None) -> Dict[str, bool]:
    """Return a normalized feature-flag payload with stable defaults."""
    normalized = dict(DEFAULT_FEATURE_FLAGS)
    for key, value in dict(flags or {}).items():
        normalized[str(key)] = bool(value)
    return normalized


def default_workflow_metrics(*, now: float | None = None) -> Dict[str, Any]:
    """Create a fresh baseline workflow-metrics payload."""
    started_at = float(time.time() if now is None else now)
    return {
        "schema": "workflow_metrics.v1",
        "session_started_at": started_at,
        "first_annotation_at": None,
        "first_review_decision_at": None,
        "annotations_added": 0,
        "annotations_updated": 0,
        "annotations_deleted": 0,
        "annotation_imports": 0,
        "suggestions_generated": 0,
        "suggestions_accepted": 0,
        "suggestions_rejected": 0,
        "review_decisions": 0,
        "merge_conflicts": 0,
        "qc_issue_count": 0,
        "annotation_count": 0,
        "provenance_complete_count": 0,
        "provenance_complete_fraction": 0.0,
        "recent_events": [],
    }


def record_workflow_event(
    metrics: Mapping[str, Any] | None,
    event_type: str,
    *,
    now: float | None = None,
    **details: Any,
) -> Dict[str, Any]:
    """Return updated workflow metrics after applying one event."""
    payload = dict(default_workflow_metrics() if metrics is None else metrics)
    ts = float(time.time() if now is None else now)
    kind = str(event_type or "").strip().lower()
    recent = list(payload.get("recent_events", []))
    recent.append({"timestamp": ts, "event_type": kind, "details": dict(details)})
    payload["recent_events"] = recent[-200:]

    if kind == "annotation_added":
        payload["annotations_added"] = int(payload.get("annotations_added", 0)) + 1
        payload["first_annotation_at"] = payload.get("first_annotation_at") or ts
    elif kind == "annotation_updated":
        payload["annotations_updated"] = int(payload.get("annotations_updated", 0)) + 1
    elif kind == "annotation_deleted":
        payload["annotations_deleted"] = int(payload.get("annotations_deleted", 0)) + int(
            details.get("count", 1)
        )
    elif kind == "annotations_imported":
        payload["annotation_imports"] = int(payload.get("annotation_imports", 0)) + int(
            details.get("count", 1)
        )
    elif kind == "suggestions_generated":
        payload["suggestions_generated"] = int(payload.get("suggestions_generated", 0)) + int(
            details.get("count", 0)
        )
    elif kind == "suggestions_accepted":
        accepted = int(details.get("count", 1))
        payload["suggestions_accepted"] = int(payload.get("suggestions_accepted", 0)) + accepted
        payload["review_decisions"] = int(payload.get("review_decisions", 0)) + accepted
        payload["first_review_decision_at"] = payload.get("first_review_decision_at") or ts
    elif kind == "suggestions_rejected":
        rejected = int(details.get("count", 1))
        payload["suggestions_rejected"] = int(payload.get("suggestions_rejected", 0)) + rejected
        payload["review_decisions"] = int(payload.get("review_decisions", 0)) + rejected
        payload["first_review_decision_at"] = payload.get("first_review_decision_at") or ts
    elif kind == "merge_conflict":
        payload["merge_conflicts"] = int(payload.get("merge_conflicts", 0)) + int(
            details.get("count", 1)
        )
    elif kind == "qc_issues_updated":
        payload["qc_issue_count"] = max(0, int(details.get("count", 0)))

    return payload


def update_provenance_coverage(
    metrics: Mapping[str, Any] | None,
    *,
    total_annotations: int,
    complete_annotations: int,
) -> Dict[str, Any]:
    """Return workflow metrics updated with provenance coverage counts."""
    payload = dict(default_workflow_metrics() if metrics is None else metrics)
    total = max(0, int(total_annotations))
    complete = max(0, min(total, int(complete_annotations)))
    payload["annotation_count"] = total
    payload["provenance_complete_count"] = complete
    payload["provenance_complete_fraction"] = (float(complete) / float(total)) if total else 0.0
    return payload
