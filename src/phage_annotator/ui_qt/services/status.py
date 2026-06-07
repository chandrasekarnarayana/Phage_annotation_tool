"""Central status models and presenter for the Qt annotation GUI.

This module unifies compact status-bar rendering, transient feedback messages,
and progress/activity presentation behind one owner. Feature code can continue
to call legacy helpers during migration, but the presenter decides what is
actually visible based on derived state plus message/activity priority rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from typing import Any, Mapping
import time

from phage_annotator.ui_qt.services import disk_cache_eviction as _status_render_module
from phage_annotator.ui_qt.services import status_service as _status_service_module


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


_SEVERITY_PRIORITY = {
    "error": 60,
    "warning": 50,
    "success": 20,
    "info": 10,
}


_SEVERITY_PRIORITY = {
    "error": 60,
    "warning": 50,
    "success": 20,
    "info": 10,
}



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
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self._status_service: StatusService | None = None

    def attach_status_service(self, service: "StatusService") -> None:
        """Bind the presenter used to absorb legacy status-bar messages."""
        self._status_service = service

    def showMessage(self, message: str, timeout: int = 0) -> None:  # noqa: N802 - Qt API
        """Run the showMessage workflow."""
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
        """Run the clearMessage workflow."""
        service = self._status_service
        if service is None:
            super().clearMessage()
            return
        service.clear_message(source="qt-statusbar")


_SEVERITY_PRIORITY = {
    "error": 60,
    "warning": 50,
    "success": 20,
    "info": 10,
}




StatusServiceMixin = _status_service_module.StatusServiceMixin
DiskCacheEvictionMixin = _status_render_module.DiskCacheEvictionMixin

_status_service_module.StatusModel = StatusModel
_status_service_module.StatusMessage = StatusMessage
_status_service_module.ActivityStatus = ActivityStatus
_status_render_module.StatusMessage = StatusMessage
_status_render_module.ActivityStatus = ActivityStatus


class StatusService(StatusServiceMixin, DiskCacheEvictionMixin, QtCore.QObject):
    """Own compact status-bar presentation and message/activity prioritization.

The service separates:
- derived status from controller/session/view state
- explicit message events from feature actions
- long-running activity/progress state

Rendering is anti-flicker aware:
- unchanged content does not rerender
- transient messages have a minimum visible duration
- derived state updates can be throttled"""

    pass
