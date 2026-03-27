"""Central status models and presenter for the Qt annotation GUI.

This module unifies compact status-bar rendering, transient feedback messages,
and progress/activity presentation behind one owner. Feature code can continue
to call legacy helpers during migration, but the presenter decides what is
actually visible based on derived state plus message/activity priority rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Mapping

from matplotlib.backends.qt_compat import QtCore, QtWidgets


_SEVERITY_PRIORITY = {
    "error": 60,
    "warning": 50,
    "success": 20,
    "info": 10,
}


class StatusText:
    """Canonical wording for common scientific annotation status states."""

    READY = "Ready"
    READY_FOR_ANNOTATION = "Ready for annotation"
    REVIEWING_SUGGESTIONS = "Reviewing suggestions"
    SAVING_PROJECT = "Saving project..."
    EXPORTING_ANNOTATIONS = "Exporting annotations..."
    SUGGESTIONS_STALE = "Suggestions stale"
    AUTOSAVE_COMPLETE = "Autosave complete"
    QC_WARNING = "QC warning"
    UNSAVED_CHANGES = "Unsaved changes"


@dataclass(slots=True)
class StatusMessage:
    """Ephemeral or sticky user-facing status feedback.

    The presenter may keep multiple internal status inputs active over time,
    but only one message is allowed to occupy the visible state zone at once.
    """

    text: str
    severity: str = "info"
    timeout_ms: int | None = None
    source: str = "unknown"
    sticky: bool = False
    min_visible_ms: int = 1200
    created_mono: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class ActivityStatus:
    """Long-running or workflow-scoped activity shown in the state zone."""

    activity_id: str
    text: str
    progress: int | None = None
    cancellable: bool = False
    state: str = "running"
    source: str = "unknown"


@dataclass(slots=True)
class StatusModel:
    """Derived operational status built from controller/session/view/job state."""

    context_text: str
    idle_text: str = "Ready"
    metric_text: str = ""
    alert_text: str = ""
    alert_severity: str | None = None
    sticky_advisory_text: str = ""
    dirty: bool = False
    progress_text: str = ""
    progress_value: int | None = None
    details_payload: dict[str, str] = field(default_factory=dict)


class ManagedStatusBar(QtWidgets.QStatusBar):
    """Status bar that routes legacy Qt `showMessage()` calls into the presenter.

    Existing feature code still calls `self.statusBar().showMessage(...)` in
    many places. During migration this subclass preserves compatibility while
    ensuring the centralized presenter remains the only visible message owner.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_service: StatusService | None = None

    def attach_status_service(self, service: "StatusService") -> None:
        """Bind the presenter used to absorb legacy status-bar messages."""
        self._status_service = service

    def showMessage(self, message: str, timeout: int = 0) -> None:  # noqa: N802 - Qt API
        service = self._status_service
        if service is None:
            super().showMessage(message, timeout)
            return
        text = str(message or "").strip()
        if not text:
            service.clear_message(source="qt-statusbar")
            return
        timeout_ms = int(timeout) if int(timeout or 0) > 0 else None
        service.post_message(
            StatusMessage(
                text=text,
                severity=service.infer_severity(text),
                timeout_ms=timeout_ms,
                source="qt-statusbar",
                sticky=timeout_ms is None,
            )
        )

    def clearMessage(self) -> None:  # noqa: N802 - Qt API
        service = self._status_service
        if service is None:
            super().clearMessage()
            return
        service.clear_message(source="qt-statusbar")


class StatusService(QtCore.QObject):
    """Own compact status-bar presentation and message/activity prioritization.

    The service separates:
    - derived status from controller/session/view state
    - explicit message events from feature actions
    - long-running activity/progress state

    Rendering is anti-flicker aware:
    - unchanged content does not rerender
    - transient messages have a minimum visible duration
    - derived state updates can be throttled
    """

    def __init__(self, owner: QtWidgets.QWidget | None = None) -> None:
        super().__init__(owner)
        self._owner = owner
        self._derived = StatusModel(context_text="-", idle_text="Ready")
        self._activity: ActivityStatus | None = None
        self._message: StatusMessage | None = None
        self._clear_pending_for_source: str | None = None
        self._last_render_signature: tuple[Any, ...] | None = None
        self._pending_model: StatusModel | None = None

        self._message_timer = QtCore.QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self._expire_transient_message)

        self._derived_timer = QtCore.QTimer(self)
        self._derived_timer.setSingleShot(True)
        self._derived_timer.timeout.connect(self._apply_pending_derived_model)

        self._context_label: QtWidgets.QLabel | None = None
        self._state_label: QtWidgets.QLabel | None = None
        self._metric_label: QtWidgets.QLabel | None = None
        self._progress_label: QtWidgets.QLabel | None = None
        self._progress_bar: QtWidgets.QProgressBar | None = None
        self._progress_cancel_btn: QtWidgets.QToolButton | None = None
        self._progress_cancel_all_btn: QtWidgets.QToolButton | None = None
        self._details_panel: QtWidgets.QWidget | None = None
        self._log_status_label: QtWidgets.QLabel | None = None

    def bind_widgets(
        self,
        *,
        context_label: QtWidgets.QLabel,
        state_label: QtWidgets.QLabel,
        metric_label: QtWidgets.QLabel,
        progress_label: QtWidgets.QLabel | None = None,
        progress_bar: QtWidgets.QProgressBar | None = None,
        progress_cancel_btn: QtWidgets.QToolButton | None = None,
        progress_cancel_all_btn: QtWidgets.QToolButton | None = None,
        details_panel: QtWidgets.QWidget | None = None,
        log_status_label: QtWidgets.QLabel | None = None,
    ) -> None:
        """Bind status widgets managed by the presenter."""
        self._context_label = context_label
        self._state_label = state_label
        self._metric_label = metric_label
        self._progress_label = progress_label
        self._progress_bar = progress_bar
        self._progress_cancel_btn = progress_cancel_btn
        self._progress_cancel_all_btn = progress_cancel_all_btn
        self._details_panel = details_panel
        self._log_status_label = log_status_label
        self.render()

    def set_derived_status(self, model: StatusModel, *, throttle_ms: int = 0) -> None:
        """Store derived status and rerender, optionally with throttling."""
        if int(throttle_ms or 0) > 0:
            self._pending_model = model
            self._derived_timer.start(int(throttle_ms))
            return
        self._derived = model
        self.render()

    def post_message(self, message: StatusMessage) -> None:
        """Show or queue a transient/sticky feedback message."""
        message.timeout_ms = self._normalize_timeout(message)
        self._message = message
        self._clear_pending_for_source = None
        if not message.sticky and message.timeout_ms is not None:
            self._message_timer.start(int(max(message.timeout_ms, message.min_visible_ms)))
        else:
            self._message_timer.stop()
        self.render()

    def info(self, text: str, *, timeout_ms: int | None = None, source: str = "info") -> None:
        """Post a short informational status message."""
        self.post_message(
            StatusMessage(
                text=str(text),
                severity="info",
                timeout_ms=timeout_ms,
                source=source,
                sticky=False,
            )
        )

    def success(self, text: str, *, timeout_ms: int | None = None, source: str = "success") -> None:
        """Post a success status message."""
        self.post_message(
            StatusMessage(
                text=str(text),
                severity="success",
                timeout_ms=timeout_ms,
                source=source,
                sticky=False,
            )
        )

    def warning(
        self,
        text: str,
        *,
        timeout_ms: int | None = None,
        source: str = "warning",
        sticky: bool = False,
    ) -> None:
        """Post a warning status message."""
        self.post_message(
            StatusMessage(
                text=str(text),
                severity="warning",
                timeout_ms=timeout_ms,
                source=source,
                sticky=sticky,
            )
        )

    def error(
        self,
        text: str,
        *,
        timeout_ms: int | None = None,
        source: str = "error",
        sticky: bool = False,
    ) -> None:
        """Post an error status message."""
        self.post_message(
            StatusMessage(
                text=str(text),
                severity="error",
                timeout_ms=timeout_ms,
                source=source,
                sticky=sticky,
            )
        )

    def clear_message(self, *, source: str | None = None, force: bool = False) -> None:
        """Clear the active transient/sticky message with anti-flicker protection."""
        current = self._message
        if current is None:
            return
        if source is not None and str(current.source) != str(source):
            return
        if force or current.sticky:
            self._message = None
            self._message_timer.stop()
            self._clear_pending_for_source = None
            self.render()
            return
        elapsed_ms = int(max(0.0, (time.monotonic() - current.created_mono) * 1000.0))
        remaining = max(0, int(current.min_visible_ms) - elapsed_ms)
        if remaining > 0:
            self._clear_pending_for_source = current.source
            self._message_timer.start(remaining)
            return
        self._message = None
        self._message_timer.stop()
        self._clear_pending_for_source = None
        self.render()

    def set_activity(self, activity: ActivityStatus | None) -> None:
        """Set or clear the active workflow/activity state."""
        self._activity = activity
        self.render()

    def update_activity(
        self,
        *,
        activity_id: str,
        text: str | None = None,
        progress: int | None = None,
        state: str | None = None,
    ) -> None:
        """Update the currently active activity without flickering."""
        activity = self._activity
        if activity is None or str(activity.activity_id) != str(activity_id):
            return
        if text is not None:
            activity.text = str(text)
        if progress is not None:
            activity.progress = int(progress)
        if state is not None:
            activity.state = str(state)
        self.render()

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
