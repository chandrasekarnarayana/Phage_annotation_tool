"""Integration tests for the compact status bar and presenter wiring."""

from __future__ import annotations

import time

import pytest


@pytest.mark.gui
def test_controller_state_change_updates_compact_status_bar(qtbot, tmp_path):
    """Controller signals should flow through the queued refresh path into status labels."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "status_bar_signal_flow.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.current_label = "Phage"
    win.controller.state_changed.emit()
    qtbot.wait(50)

    assert "Tool:" in win.status_context_lbl.text()
    assert "Label: Phage" in win.status_context_lbl.text()
    assert win.status_state_lbl.text() in {"Ready", "Ready for annotation", "Unsaved changes"}


@pytest.mark.gui
def test_job_activity_updates_compact_status_and_progress_widgets(qtbot, tmp_path):
    """Job lifecycle callbacks should drive presenter-owned activity widgets."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "status_bar_jobs.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._on_job_started("Export annotations", "job-1")
    win._on_job_progress("Export annotations", "job-1", 35, "Writing bundle")
    qtbot.wait(20)

    assert "Export annotations" in win.status_state_lbl.text()
    assert win.progress_bar.isVisible() is True
    assert win.progress_bar.value() == 35

    win._on_job_finished("Export annotations", "job-1")
    qtbot.wait(20)
    assert win.progress_bar.isVisible() is False


@pytest.mark.gui
def test_warning_persists_over_competing_activity_until_resolved(qtbot, tmp_path):
    """Derived warnings should stay visible when lower-priority activity starts."""
    pytest.importorskip("PyQt5")
    from phage_annotator.core.annotation import PointSuggestion
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "status_bar_warning_priority.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    image_id = int(win.primary_image.id)
    ts = float(time.time()) - 120.0
    row = PointSuggestion(
        image_id=image_id,
        image_name=str(win.primary_image.name),
        t=int(win.t_slider.value()),
        z=int(win.z_slider.value()),
        y=10.0,
        x=10.0,
        score=0.9,
        label=str(win.current_label),
        suggestion_id="stale-priority-1",
    )
    row.meta["generated_at_ts"] = ts
    win.suggestions[image_id] = [row]
    win._annotation_edit_ts_by_image[image_id] = ts + 5.0
    win._update_status()
    qtbot.wait(30)

    assert win.status_state_lbl.text() == "Suggestions stale"
    win._on_job_started("Refreshing suggestions", "job-warn-1")
    qtbot.wait(30)
    assert win.status_state_lbl.text() == "Suggestions stale"
