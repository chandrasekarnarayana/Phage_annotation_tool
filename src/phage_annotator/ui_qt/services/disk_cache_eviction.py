"""Extracted method group 2 for StatusService."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Mapping, TYPE_CHECKING

from matplotlib.backends.qt_compat import QtCore, QtWidgets

if TYPE_CHECKING:
    # Runtime bindings for StatusMessage/ActivityStatus are injected by
    # phage_annotator.ui_qt.services.status (which imports this module) to
    # avoid a circular import; this import is for static analysis only.
    from phage_annotator.ui_qt.services.status import ActivityStatus, StatusMessage


_SEVERITY_PRIORITY = {
    "error": 60,
    "warning": 50,
    "success": 20,
    "info": 10,
}




class DiskCacheEvictionMixin:
    """Method group 2 extracted from StatusService."""

    def clear_activity(self, activity_id: str | None = None) -> None:
        """Clear the active activity when it finishes or is cancelled."""
        if activity_id is not None and self._activity is not None:
            if str(self._activity.activity_id) != str(activity_id):
                return
        self._activity = None
        self.render()
    def render(self) -> None:
        """Render the current compact status-bar payload and details panel payload."""
        context_text = self._derived.context_text or "-"
        state_text, state_level = self._resolve_state_text()
        metric_text = self._resolve_metric_text(state_level)
        progress_visible, progress_text, progress_value, progress_cancellable = self._resolve_progress()
        details_payload = dict(self._derived.details_payload or {})
        signature = (
            context_text,
            state_text,
            state_level,
            metric_text,
            progress_visible,
            progress_text,
            progress_value,
            progress_cancellable,
            tuple(sorted(details_payload.items())),
        )
        if signature == self._last_render_signature:
            return
        self._last_render_signature = signature

        if self._context_label is not None:
            self._context_label.setText(context_text)
        if self._state_label is not None:
            self._state_label.setText(state_text)
            self._state_label.setProperty("statusSeverity", state_level)
            self._state_label.style().unpolish(self._state_label)
            self._state_label.style().polish(self._state_label)
        if self._metric_label is not None:
            self._metric_label.setText(metric_text)
            self._metric_label.setVisible(bool(metric_text))
        if self._log_status_label is not None:
            self._log_status_label.setText(state_text)
        self._apply_progress_widgets(progress_visible, progress_text, progress_value, progress_cancellable)
        self._apply_details_payload(details_payload)
    def infer_severity(self, text: str) -> str:
        """Infer severity from legacy free-text status messages."""
        lowered = str(text or "").strip().lower()
        if any(token in lowered for token in ("error", "failed", "failure", "invalid")):
            return "error"
        if any(token in lowered for token in ("warning", "stale", "pending", "cancelled", "underrun")):
            return "warning"
        if any(token in lowered for token in ("saved", "loaded", "done", "complete", "applied", "restored")):
            return "success"
        return "info"
    def _normalize_timeout(self, message: StatusMessage) -> int | None:
        """Apply global timeout policy for status feedback."""
        if message.sticky:
            return None
        if message.timeout_ms is not None:
            return int(message.timeout_ms)
        severity = str(message.severity or "info").lower()
        if severity == "error":
            return 7000
        if severity == "warning":
            return 5000
        if severity == "success":
            return 3000
        return 2000
    def _resolve_state_text(self) -> tuple[str, str]:
        """Select the single visible state/activity message by priority."""
        explicit = self._message
        if explicit is not None:
            severity = str(explicit.severity or "info").lower()
            if severity == "error":
                return explicit.text, "error"
            if severity == "warning":
                return explicit.text, "warning"

        alert_text = str(self._derived.alert_text or "").strip()
        alert_severity = str(self._derived.alert_severity or "").strip().lower()
        if alert_text and alert_severity == "error":
            return alert_text, "error"
        if alert_text and alert_severity == "warning":
            return alert_text, "warning"

        if self._activity is not None and str(self._activity.state) == "running":
            return self._activity.text, "activity"

        sticky = self._message
        if sticky is not None and bool(sticky.sticky):
            return sticky.text, str(sticky.severity or "info").lower()

        if self._derived.dirty:
            advisory = str(self._derived.sticky_advisory_text or "Unsaved changes").strip()
            return advisory, "advisory"

        if explicit is not None:
            return explicit.text, str(explicit.severity or "info").lower()

        idle = str(self._derived.idle_text or "Ready").strip()
        return idle, "idle"
    def _resolve_metric_text(self, state_level: str) -> str:
        """Keep the metric slot quiet while higher-priority messages are visible."""
        if state_level not in {"idle"}:
            return ""
        alert_text = str(self._derived.alert_text or "").strip()
        if alert_text:
            return alert_text
        return str(self._derived.metric_text or "").strip()
    def _resolve_progress(self) -> tuple[bool, str, int, bool]:
        """Return current progress-widget state derived from the active activity."""
        activity = self._activity
        if activity is None or str(activity.state) != "running":
            return False, "", 0, False
        progress = int(activity.progress) if activity.progress is not None else 0
        return True, activity.text, progress, bool(activity.cancellable)
    def _apply_progress_widgets(
        self,
        visible: bool,
        text: str,
        progress: int,
        cancellable: bool,
    ) -> None:
        """Render activity progress widgets as one controlled status sub-view."""
        if self._progress_label is not None:
            self._progress_label.setText(f"Working: {text}" if text else "Working:")
            self._progress_label.setVisible(visible)
        if self._progress_bar is not None:
            self._progress_bar.setVisible(visible)
            self._progress_bar.setValue(max(0, min(100, int(progress))))
        if self._progress_cancel_btn is not None:
            self._progress_cancel_btn.setVisible(visible)
            self._progress_cancel_btn.setEnabled(bool(visible and cancellable))
        if self._progress_cancel_all_btn is not None:
            self._progress_cancel_all_btn.setVisible(visible)
    def _apply_details_payload(self, payload: Mapping[str, str]) -> None:
        """Push derived structured status values into the details panel."""
        panel = self._details_panel
        if panel is None:
            return
        for key, value in payload.items():
            widget = getattr(panel, key, None)
            if widget is not None and hasattr(widget, "setText"):
                widget.setText(str(value))
    def _expire_transient_message(self) -> None:
        """Expire timed messages and honor deferred anti-flicker clears."""
        current = self._message
        if current is None:
            return
        if self._clear_pending_for_source is not None:
            if str(current.source) == str(self._clear_pending_for_source):
                self._message = None
            self._clear_pending_for_source = None
        elif not current.sticky and current.timeout_ms is not None:
            self._message = None
        self.render()
    def _apply_pending_derived_model(self) -> None:
        """Apply the latest throttled derived model update."""
        if self._pending_model is None:
            return
        self._derived = self._pending_model
        self._pending_model = None
        self.render()
