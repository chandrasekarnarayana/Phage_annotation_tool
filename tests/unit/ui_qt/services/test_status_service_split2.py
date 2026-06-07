"""Split definitions from test_status_service.py."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.status_details_panel import StatusDetailsPanel
from phage_annotator.ui_qt.services.status import (
    ActivityStatus,
    ManagedStatusBar,
    StatusMessage,
    StatusModel,
    StatusService,
    StatusText,
)


from tests.unit.ui_qt.services.test_status_service_split1 import _build_bound_service

def test_high_frequency_updates_are_throttled(qtbot) -> None:
    """Verify high frequency updates are throttled for the current workflow."""
    service, _context, state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, metric_text="Visible 10"))
    service.set_derived_status(
        StatusModel(context_text="Sample_A", idle_text="Playback running", metric_text="Buffer 5/16"),
        throttle_ms=50,
    )
    assert state.text() == StatusText.READY
    qtbot.wait(70)
    assert state.text() == "Playback running"
    assert metric.text() == "Buffer 5/16"

def test_save_dirty_status_behavior(qtbot) -> None:
    """Verify save dirty status behavior for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, dirty=True, sticky_advisory_text=StatusText.UNSAVED_CHANGES))
    assert state.text() == StatusText.UNSAVED_CHANGES
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, dirty=False))
    service.success(StatusText.AUTOSAVE_COMPLETE, timeout_ms=40, source="save")
    assert state.text() == StatusText.AUTOSAVE_COMPLETE
    qtbot.wait(60)
    assert state.text() == StatusText.READY

def test_export_running_then_info_toast_arrives(qtbot) -> None:
    """Verify export running then info toast arrives for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.set_activity(ActivityStatus(activity_id="export", text=StatusText.EXPORTING_ANNOTATIONS, progress=5))
    service.info("Label changed", source="info")
    assert state.text() == StatusText.EXPORTING_ANNOTATIONS

def test_playback_active_then_buffer_underrun_occurs(qtbot) -> None:
    """Verify playback active then buffer underrun occurs for the current workflow."""
    service, _context, state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text="Playback running", metric_text="Buffer 7/16 | Underruns 0"))
    service.warning("Buffer underrun", timeout_ms=100, source="playback")
    assert state.text() == "Buffer underrun"
    qtbot.wait(120)
    assert state.text() == "Playback running"
    assert metric.text() == "Buffer 7/16 | Underruns 0"

def test_stale_warning_while_assist_refresh_starts(qtbot) -> None:
    """Verify stale warning while assist refresh starts for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.REVIEWING_SUGGESTIONS, alert_text=StatusText.SUGGESTIONS_STALE, alert_severity="warning"))
    service.set_activity(ActivityStatus(activity_id="assist", text="Refreshing suggestions...", progress=15))
    assert state.text() == StatusText.SUGGESTIONS_STALE

def test_job_failure_while_another_activity_is_active(qtbot) -> None:
    """Verify job failure while another activity is active for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.set_activity(ActivityStatus(activity_id="assist", text="Refreshing suggestions...", progress=15))
    service.error("Export failed", source="export")
    assert state.text() == "Export failed"
