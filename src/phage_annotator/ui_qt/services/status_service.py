"""Extracted method group 1 for StatusService."""

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




class StatusServiceMixin:
    """Method group 1 extracted from StatusService."""

    def __init__(self, owner: QtWidgets.QWidget | None = None) -> None:
        """Initialize the object and prepare its runtime state."""
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
