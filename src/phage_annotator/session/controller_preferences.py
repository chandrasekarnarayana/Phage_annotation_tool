"""User and session preference controller helpers."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from phage_annotator.core.rollout import (
    default_workflow_metrics,
    normalize_feature_flags,
    record_workflow_event,
    update_provenance_coverage,
)

from phage_annotator.session.signal_hub import emit_state_changed


class SessionControllerPreferencesMixin:
    """Controller helpers for user/session preference state."""

    def feature_enabled(self, flag_name: str, default: bool | None = None) -> bool:
        """Return whether a named rollout flag is enabled."""
        flags = normalize_feature_flags(getattr(self.session_state, "feature_flags", {}))
        if default is None:
            default = bool(flags.get(str(flag_name), False))
        return bool(flags.get(str(flag_name), default))

    def set_feature_flag(self, flag_name: str, enabled: bool) -> None:
        """Persist one rollout flag through the controller boundary."""
        current = normalize_feature_flags(getattr(self.session_state, "feature_flags", {}))
        key = str(flag_name)
        value = bool(enabled)
        if current.get(key) == value:
            return
        current[key] = value
        self.session_state.feature_flags = current
        settings = getattr(self, "_settings", None)
        if settings is not None:
            settings.setValue(f"featureFlags/{key}", value)
        emit_state_changed(self)

    def record_workflow_event(self, event_type: str, **details: Any) -> None:
        """Append one baseline instrumentation event when enabled."""
        if not self.feature_enabled("baseline_workflow_metrics", True):
            return
        self.session_state.workflow_metrics = record_workflow_event(
            getattr(self.session_state, "workflow_metrics", None),
            event_type,
            **details,
        )

    def workflow_metrics_snapshot(self) -> Mapping[str, Any]:
        """Return a stable snapshot of workflow metrics."""
        return dict(getattr(self.session_state, "workflow_metrics", {}) or default_workflow_metrics())

    def refresh_provenance_coverage_metrics(self) -> None:
        """Recompute provenance coverage across all current annotations."""
        total = 0
        complete = 0
        for rows in dict(getattr(self.session_state, "annotations", {}) or {}).values():
            for annotation in list(rows or []):
                total += 1
                status = str(getattr(annotation, "status", "")).strip()
                source = str(getattr(annotation, "source", "")).strip()
                if source and status:
                    complete += 1
        self.session_state.workflow_metrics = update_provenance_coverage(
            getattr(self.session_state, "workflow_metrics", None),
            total_annotations=total,
            complete_annotations=complete,
        )

    def append_audit_event(self, event_type: str, **details: object) -> None:
        """Append an immutable audit event entry to session state."""
        import time

        self.session_state.audit_log.append(
            {
                "timestamp": time.time(),
                "user": self.session_state.current_user,
                "event_type": event_type,
                "details": dict(details),
            }
        )

    def mark_session_dirty(self, dirty: bool = True) -> None:
        """Update session dirty state through the controller boundary."""
        self.set_dirty(bool(dirty))

    def set_annotation_space_value(self, space: str) -> None:
        """Persist annotation-space selection."""
        self.session_state.annotation_space = str(space or "stack")
        emit_state_changed(self)

    def set_current_user_value(self, user: str) -> None:
        """Persist current user identity."""
        self.session_state.current_user = str(user or "local_user")
        emit_state_changed(self)

    def set_suggestion_retrain_config(
        self, *, enabled: Optional[bool] = None, min_labels: Optional[int] = None
    ) -> None:
        """Persist suggestion-ranker retrain policy and notify observers."""
        changed = False
        if enabled is not None:
            value = bool(enabled)
            if self.session_state.suggestion_auto_retrain_enabled != value:
                self.session_state.suggestion_auto_retrain_enabled = value
                changed = True
        if min_labels is not None:
            value = int(max(1, min_labels))
            if self.session_state.suggestion_auto_retrain_min_labels != value:
                self.session_state.suggestion_auto_retrain_min_labels = value
                changed = True
        if changed:
            emit_state_changed(self)

    def set_assist_minima(
        self,
        *,
        min_total: Optional[int] = None,
        min_positive: Optional[int] = None,
        min_negative: Optional[int] = None,
        min_per_context: Optional[int] = None,
    ) -> None:
        """Persist assist readiness minima."""
        changed = False
        if min_total is not None:
            value = int(max(1, min_total))
            if self.session_state.assist_min_total_labels != value:
                self.session_state.assist_min_total_labels = value
                changed = True
        if min_positive is not None:
            value = int(max(1, min_positive))
            if self.session_state.assist_min_positive_labels != value:
                self.session_state.assist_min_positive_labels = value
                changed = True
        if min_negative is not None:
            value = int(max(1, min_negative))
            if self.session_state.assist_min_negative_labels != value:
                self.session_state.assist_min_negative_labels = value
                changed = True
        if min_per_context is not None:
            value = int(max(1, min_per_context))
            if self.session_state.assist_min_labels_per_context != value:
                self.session_state.assist_min_labels_per_context = value
                changed = True
        if changed:
            emit_state_changed(self)

    def set_generation_space_value(self, generation_space: str) -> None:
        """Persist assist generation space selection."""
        value = str(generation_space or "stack").strip().lower()
        if value not in {"stack", "projection"}:
            value = "stack"
        if self.session_state.generation_space == value:
            return
        self.session_state.generation_space = value
        emit_state_changed(self)

    def set_disable_bulk_accept_when_stale_value(self, enabled: bool) -> None:
        """Persist stale batch-accept protection policy."""
        value = bool(enabled)
        if self.session_state.disable_bulk_accept_when_stale == value:
            return
        self.session_state.disable_bulk_accept_when_stale = value
        emit_state_changed(self)
