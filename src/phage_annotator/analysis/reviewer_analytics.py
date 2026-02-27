"""Reviewer workflow analytics from audit and QC history."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def compute_reviewer_metrics(audit_log: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Aggregate per-user workflow metrics from immutable audit events."""
    per_user: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "events": 0.0,
            "annotations_added": 0.0,
            "annotations_updated": 0.0,
            "annotations_deleted": 0.0,
            "reviews_completed": 0.0,
            "suggestions_generated": 0.0,
            "suggestions_accepted": 0.0,
            "suggestions_rejected": 0.0,
            "first_event_ts": 0.0,
            "last_event_ts": 0.0,
            "active_hours": 0.0,
            "annotation_velocity_per_hour": 0.0,
        }
    )

    for event in audit_log:
        user = str(event.get("user") or "unknown")
        ts = _as_float(event.get("timestamp"), 0.0)
        event_type = str(event.get("event_type") or "")
        details = event.get("details") if isinstance(event.get("details"), Mapping) else {}

        row = per_user[user]
        row["events"] += 1.0
        if row["first_event_ts"] == 0.0 or (ts > 0 and ts < row["first_event_ts"]):
            row["first_event_ts"] = ts
        if ts > row["last_event_ts"]:
            row["last_event_ts"] = ts

        if event_type == "annotation_added":
            row["annotations_added"] += 1.0
        elif event_type == "annotation_updated":
            row["annotations_updated"] += 1.0
        elif event_type == "annotation_deleted":
            row["annotations_deleted"] += 1.0
        elif event_type == "review_state_updated":
            row["reviews_completed"] += _as_float(details.get("count"), 0.0)
        elif event_type == "suggestions_generated":
            row["suggestions_generated"] += _as_float(details.get("count"), 0.0)
        elif event_type == "suggestion_command":
            command = str(details.get("command") or "").lower()
            if command == "accept_suggestion":
                row["suggestions_accepted"] += 1.0
            elif command == "reject_suggestion":
                row["suggestions_rejected"] += 1.0

    for row in per_user.values():
        elapsed_s = max(0.0, row["last_event_ts"] - row["first_event_ts"])
        row["active_hours"] = elapsed_s / 3600.0
        edits = row["annotations_added"] + row["annotations_updated"] + row["annotations_deleted"]
        if row["active_hours"] > 0:
            row["annotation_velocity_per_hour"] = edits / row["active_hours"]
        else:
            row["annotation_velocity_per_hour"] = edits

    return dict(sorted(per_user.items(), key=lambda kv: kv[0]))


def compute_issue_trend(audit_log: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Return time-ordered QC issue snapshots from validation audit events."""
    trend: List[Dict[str, Any]] = []
    for event in audit_log:
        if str(event.get("event_type") or "") != "qc_validation_completed":
            continue
        details = event.get("details") if isinstance(event.get("details"), Mapping) else {}
        by_type = details.get("issue_counts_by_type")
        by_type_dict = dict(by_type) if isinstance(by_type, Mapping) else {}
        trend.append(
            {
                "timestamp": _as_float(event.get("timestamp"), 0.0),
                "image_id": int(_as_float(details.get("image_id"), -1)),
                "total_issues": int(_as_float(details.get("total_issues"), 0)),
                "issue_counts_by_type": {str(k): int(_as_float(v, 0)) for k, v in by_type_dict.items()},
            }
        )
    trend.sort(key=lambda row: float(row["timestamp"]))
    return trend


def build_reviewer_dashboard_text(audit_log: Iterable[Mapping[str, Any]]) -> str:
    """Build plain-text dashboard summary for quick review in GUI."""
    per_user = compute_reviewer_metrics(audit_log)
    trend = compute_issue_trend(audit_log)

    lines = ["Reviewer Analytics", "==================", ""]
    if not per_user:
        lines.append("No audit events available yet.")
    else:
        lines.append("Per-user metrics:")
        for user, row in per_user.items():
            lines.append(
                (
                    f"- {user}: edits={int(row['annotations_added'] + row['annotations_updated'] + row['annotations_deleted'])}, "
                    f"reviews={int(row['reviews_completed'])}, "
                    f"suggestions A/R={int(row['suggestions_accepted'])}/{int(row['suggestions_rejected'])}, "
                    f"velocity={row['annotation_velocity_per_hour']:.2f}/hr"
                )
            )

    lines.append("")
    lines.append("QC issue trend:")
    if not trend:
        lines.append("- No QC validation snapshots recorded yet.")
    else:
        latest = trend[-1]
        lines.append(
            f"- Latest total issues: {int(latest['total_issues'])} (image_id={int(latest['image_id'])})"
        )
        by_type = latest.get("issue_counts_by_type", {})
        if by_type:
            parts = [f"{k}={int(v)}" for k, v in sorted(by_type.items())]
            lines.append("- Latest by type: " + ", ".join(parts))
        if len(trend) >= 2:
            delta = int(trend[-1]["total_issues"]) - int(trend[-2]["total_issues"])
            lines.append(f"- Change vs previous snapshot: {delta:+d}")

    return "\n".join(lines)
