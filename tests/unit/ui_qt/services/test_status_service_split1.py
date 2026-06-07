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


def _build_bound_service(qtbot):
    """Build bound service for the current workflow."""
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    service = StatusService(parent)
    context = QtWidgets.QLabel(parent=parent)
    state = QtWidgets.QLabel(parent=parent)
    metric = QtWidgets.QLabel(parent=parent)
    progress_label = QtWidgets.QLabel(parent=parent)
    progress_bar = QtWidgets.QProgressBar(parent=parent)
    cancel_btn = QtWidgets.QToolButton(parent=parent)
    cancel_all_btn = QtWidgets.QToolButton(parent=parent)
    details = StatusDetailsPanel(parent=parent)
    service.bind_widgets(
        context_label=context,
        state_label=state,
        metric_label=metric,
        progress_label=progress_label,
        progress_bar=progress_bar,
        progress_cancel_btn=cancel_btn,
        progress_cancel_all_btn=cancel_all_btn,
        details_panel=details,
    )
    return service, context, state, metric, progress_label, progress_bar, cancel_btn, details

def test_status_service_prefers_warning_over_activity_and_hides_metric(qtbot) -> None:
    """Verify status service prefers warning over activity and hides metric for the current workflow."""
    service, context, state, metric, progress_label, progress_bar, cancel_btn, details = _build_bound_service(qtbot)
    service.set_derived_status(
        StatusModel(
            context_text="Sample_A | T1 Z1 | Tool: Annotate | Label: Phage",
            idle_text=StatusText.READY_FOR_ANNOTATION,
            metric_text="Visible 12 | Density 0.500/um²",
            details_payload={"dataset_lbl": "Sample_A"},
        )
    )

    assert context.text() == "Sample_A | T1 Z1 | Tool: Annotate | Label: Phage"
    assert state.text() == StatusText.READY_FOR_ANNOTATION
    assert metric.text() == "Visible 12 | Density 0.500/um²"
    assert details.dataset_lbl.text() == "Sample_A"

    service.set_activity(
        ActivityStatus(
            activity_id="job-1",
            text="Exporting annotations...",
            progress=40,
            cancellable=True,
        )
    )

    assert state.text() == "Exporting annotations..."
    assert metric.isVisible() is False
    assert progress_label.isVisible() is True
    assert progress_bar.value() == 40
    assert cancel_btn.isEnabled() is True

    service.set_derived_status(
        StatusModel(
            context_text="Sample_A | T1 Z1 | Tool: Annotate | Label: Phage",
            idle_text=StatusText.READY_FOR_ANNOTATION,
            metric_text="Visible 12 | Density 0.500/um²",
            alert_text=StatusText.SUGGESTIONS_STALE,
            alert_severity="warning",
        )
    )

    assert state.text() == StatusText.SUGGESTIONS_STALE
    assert metric.isVisible() is False

def test_status_service_respects_minimum_visible_duration(qtbot) -> None:
    """Verify status service respects minimum visible duration for the current workflow."""
    service, _context, state, _metric, _progress_label, _progress_bar, _cancel_btn, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.post_message(
        StatusMessage(
            text="Copied ROI",
            severity="info",
            timeout_ms=20,
            source="test",
            sticky=False,
            min_visible_ms=60,
        )
    )

    service.clear_message(source="test")
    assert state.text() == "Copied ROI"
    qtbot.wait(80)
    assert state.text() == StatusText.READY

def test_managed_status_bar_routes_legacy_show_message_into_service(qtbot) -> None:
    """Verify managed status bar routes legacy show message into service for the current workflow."""
    parent = QtWidgets.QMainWindow()
    qtbot.addWidget(parent)
    service = StatusService(parent)
    context = QtWidgets.QLabel(parent=parent)
    state = QtWidgets.QLabel(parent=parent)
    metric = QtWidgets.QLabel(parent=parent)
    service.bind_widgets(context_label=context, state_label=state, metric_label=metric)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))

    status_bar = ManagedStatusBar(parent)
    status_bar.attach_status_service(service)
    parent.setStatusBar(status_bar)
    status_bar.showMessage("Annotations loaded.", 3000)

    assert state.text() == "Annotations loaded."

def test_error_outranks_warning_info_and_activity(qtbot) -> None:
    """Verify error outranks warning info and activity for the current workflow."""
    service, _context, state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, metric_text="Visible 10"))
    service.set_activity(ActivityStatus(activity_id="export", text="Exporting annotations...", progress=20, cancellable=True))
    service.warning("Suggestions stale", source="warn")
    assert state.text() == "Suggestions stale"
    service.error("Export failed", source="error")
    assert state.text() == "Export failed"
    assert metric.isVisible() is False

def test_warning_outranks_activity_and_info(qtbot) -> None:
    """Verify warning outranks activity and info for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.set_activity(ActivityStatus(activity_id="assist", text="Refreshing suggestions...", progress=10))
    service.info("Copied ROI", source="info")
    assert state.text() == "Refreshing suggestions..."
    service.warning("QC warning", source="warn")
    assert state.text() == "QC warning"

def test_activity_remains_visible_despite_lower_priority_info(qtbot) -> None:
    """Verify activity remains visible despite lower priority info for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.set_activity(ActivityStatus(activity_id="save", text="Saving project...", progress=50))
    service.info("Label changed", source="info")
    assert state.text() == "Saving project..."

def test_sticky_dirty_advisory_remains_until_resolved(qtbot) -> None:
    """Verify sticky dirty advisory remains until resolved for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, dirty=True, sticky_advisory_text=StatusText.UNSAVED_CHANGES))
    assert state.text() == StatusText.UNSAVED_CHANGES
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, dirty=False))
    assert state.text() == StatusText.READY

def test_transient_message_expires_correctly(qtbot) -> None:
    """Verify transient message expires correctly for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.info(StatusText.AUTOSAVE_COMPLETE, timeout_ms=40, source="info")
    assert state.text() == StatusText.AUTOSAVE_COMPLETE
    qtbot.wait(60)
    assert state.text() == StatusText.READY

def test_activity_clears_on_completion_failure_and_cancel(qtbot) -> None:
    """Verify activity clears on completion failure and cancel for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY))
    service.set_activity(ActivityStatus(activity_id="job", text="Exporting annotations...", progress=40))
    assert state.text() == "Exporting annotations..."
    service.clear_activity("job")
    assert state.text() == StatusText.READY
    service.set_activity(ActivityStatus(activity_id="job2", text="Training model...", progress=10))
    service.error("Training failed", source="error")
    assert state.text() == "Training failed"
    service.clear_activity("job2")
    assert state.text() == "Training failed"

def test_one_visible_message_with_multiple_internal_items(qtbot) -> None:
    """Verify one visible message with multiple internal items for the current workflow."""
    service, _context, state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, dirty=True, sticky_advisory_text=StatusText.UNSAVED_CHANGES))
    service.set_activity(ActivityStatus(activity_id="job", text=StatusText.SAVING_PROJECT, progress=20))
    service.info("Copied ROI", source="info")
    assert state.text() == StatusText.SAVING_PROJECT
    service.warning(StatusText.SUGGESTIONS_STALE, source="warning")
    assert state.text() == StatusText.SUGGESTIONS_STALE

def test_mode_based_annotation_rendering(qtbot) -> None:
    """Verify mode based annotation rendering for the current workflow."""
    service, context, state, metric, _pl, _pb, _cb, details = _build_bound_service(qtbot)
    model = StatusModel(
        context_text="Sample_A | T1 Z1 | Tool: Annotate | Label: Phage",
        idle_text=StatusText.READY_FOR_ANNOTATION,
        metric_text="Visible 18 | Density 0.440/um²",
        details_payload={
            "points_lbl": "Slice 18 | Total 50",
            "sync_group_lbl": "2",
            "sync_modes_lbl": "Contrast, Zoom/Pan",
            "write_mode_lbl": "Independent",
            "write_context_lbl": "img:12|panel:frame|space:stack",
            "binding_lbl": "sample_A_frame.json",
        },
    )
    service.set_derived_status(model)
    assert "Tool: Annotate" in context.text()
    assert state.text() == StatusText.READY_FOR_ANNOTATION
    assert metric.text() == "Visible 18 | Density 0.440/um²"
    assert details.points_lbl.text() == "Slice 18 | Total 50"
    assert details.sync_group_lbl.text() == "2"
    assert details.sync_modes_lbl.text() == "Contrast, Zoom/Pan"
    assert details.write_mode_lbl.text() == "Independent"
    assert details.write_context_lbl.text() == "img:12|panel:frame|space:stack"
    assert details.binding_lbl.text() == "sample_A_frame.json"

def test_mode_based_roi_rendering(qtbot) -> None:
    """Verify mode based roi rendering for the current workflow."""
    service, _context, state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(
        StatusModel(
            context_text="Sample_A | T1 Z1 | Tool: ROI Box | Label: Phage",
            idle_text=StatusText.READY_FOR_ANNOTATION,
            metric_text="ROI 235.00 um² | Density 0.63/um²",
        )
    )
    assert state.text() == StatusText.READY_FOR_ANNOTATION
    assert metric.text() == "ROI 235.00 um² | Density 0.63/um²"

def test_mode_based_assist_review_rendering(qtbot) -> None:
    """Verify mode based assist review rendering for the current workflow."""
    service, _context, state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(
        StatusModel(
            context_text="Sample_A | T1 Z1 | Tool: Annotate | Label: Phage",
            idle_text=StatusText.REVIEWING_SUGGESTIONS,
            metric_text="Suggestions: 45s old",
        )
    )
    assert state.text() == StatusText.REVIEWING_SUGGESTIONS
    assert metric.text() == "Suggestions: 45s old"

def test_mode_based_playback_rendering(qtbot) -> None:
    """Verify mode based playback rendering for the current workflow."""
    service, _context, state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(
        StatusModel(
            context_text="Sample_A | T2 Z1 | Tool: Annotate | Label: Phage",
            idle_text="Playback running",
            metric_text="Buffer 7/16 | Underruns 0",
        )
    )
    assert state.text() == "Playback running"
    assert metric.text() == "Buffer 7/16 | Underruns 0"

def test_busy_mode_hides_secondary_metric(qtbot) -> None:
    """Verify busy mode hides secondary metric for the current workflow."""
    service, _context, _state, metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    service.set_derived_status(StatusModel(context_text="Sample_A", idle_text=StatusText.READY, metric_text="Visible 15"))
    service.set_activity(ActivityStatus(activity_id="job", text=StatusText.SAVING_PROJECT, progress=30))
    assert metric.isVisible() is False

def test_no_rerender_if_content_unchanged(qtbot, monkeypatch) -> None:
    """Verify no rerender if content unchanged for the current workflow."""
    service, _context, _state, _metric, _pl, _pb, _cb, _details = _build_bound_service(qtbot)
    calls = {"progress": 0, "details": 0}

    def _progress(*args, **kwargs):
        """Handle the progress helper flow."""
        calls["progress"] += 1

    def _details_apply(*args, **kwargs):
        """Handle the details apply helper flow."""
        calls["details"] += 1

    monkeypatch.setattr(service, "_apply_progress_widgets", _progress)
    monkeypatch.setattr(service, "_apply_details_payload", _details_apply)
    model = StatusModel(context_text="Sample_A", idle_text=StatusText.READY, metric_text="Visible 10")
    service.set_derived_status(model)
    service.set_derived_status(model)
    assert calls == {"progress": 1, "details": 1}
