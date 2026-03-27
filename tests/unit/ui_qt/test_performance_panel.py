from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from phage_annotator.cache.projection_cache import ProjectionCache
from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.ui_qt.services.jobs import JobTelemetry, JobSnapshot


class _MainWindowStub:
    def __init__(self) -> None:
        self._status_events = []
        self.images = []
        self.current_image_idx = 0
        self.support_image_idx = 0
        self.jobs = SimpleNamespace(
            queue_snapshot=lambda: JobTelemetry(
                active_count=0,
                pending_count=0,
                blocked_count=0,
                total_submitted=0,
                total_finished=0,
                total_cancelled=0,
                total_errors=0,
                max_pending_jobs=4,
                running=(),
                pending=(),
            ),
            cancel_matching=lambda **_kwargs: [],
            cancel=lambda _job_id: False,
        )

    def _status_success(self, text: str, **_kwargs) -> None:
        self._status_events.append(str(text))

    def _status_info(self, text: str, **_kwargs) -> None:
        self._status_events.append(str(text))


def test_performance_panel_warns_when_cache_reaches_ninety_percent(qtbot) -> None:
    cache = ProjectionCache(max_mb=1)
    arr = np.zeros((1000, 1000), dtype=np.uint8)
    cache.put((0, "mean", (0.0, 0.0, 1.0, 1.0), 0, 0, 0), arr)

    panel = PerformancePanel(parent=None)
    qtbot.addWidget(panel)
    panel.set_cache(cache)
    panel._update_cache_metrics()
    panel._update_warnings()

    assert "Cache at" in panel.warnings_label.text()
    assert "evictions" in panel.warnings_label.text()


def test_performance_panel_clear_cache_resets_usage_and_surfaces_status(qtbot) -> None:
    cache = ProjectionCache(max_mb=8)
    arr = np.zeros((512, 512), dtype=np.uint8)
    cache.put((0, "mean", (0.0, 0.0, 1.0, 1.0), 0, 0, 0), arr)

    main_window = _MainWindowStub()
    panel = PerformancePanel(parent=None)
    panel.main_window = main_window
    qtbot.addWidget(panel)
    panel.set_cache(cache)
    panel._update_cache_metrics()

    assert cache.stats()[0] > 0
    panel._clear_projection_cache()

    assert cache.stats()[0] == 0
    assert cache.telemetry().evictions == 0
    assert main_window._status_events == ["Projection cache cleared."]


def test_performance_panel_surfaces_job_queue_summary(qtbot) -> None:
    main_window = _MainWindowStub()
    main_window.jobs = SimpleNamespace(
        queue_snapshot=lambda: JobTelemetry(
            active_count=1,
            pending_count=2,
            blocked_count=1,
            total_submitted=7,
            total_finished=4,
            total_cancelled=1,
            total_errors=0,
            max_pending_jobs=6,
            running=(
                JobSnapshot(
                    job_id="job-a",
                    name="Mean projection",
                    state="running",
                    priority=1,
                    queue_order=0,
                    replace_key="proj",
                    dependencies=(),
                    blocked_by=(),
                ),
            ),
            pending=(
                JobSnapshot(
                    job_id="job-b",
                    name="ROI measure",
                    state="blocked",
                    priority=1,
                    queue_order=1,
                    replace_key=None,
                    dependencies=("job-a",),
                    blocked_by=("job-a",),
                ),
                JobSnapshot(
                    job_id="job-c",
                    name="Histogram",
                    state="queued",
                    priority=0,
                    queue_order=2,
                    replace_key=None,
                    dependencies=(),
                    blocked_by=(),
                ),
            ),
        ),
        cancel_matching=lambda **_kwargs: [],
        cancel=lambda _job_id: False,
    )
    panel = PerformancePanel(parent=None)
    panel.main_window = main_window
    qtbot.addWidget(panel)

    panel._update_jobs_metrics()
    panel._update_warnings()

    assert panel.jobs_active_label.text() == "1"
    assert panel.jobs_pending_label.text() == "2 / 6"
    assert panel.jobs_blocked_label.text() == "1"
    assert "waiting on job-a" in panel.jobs_queue_summary_label.text().lower()
    assert "waiting on dependencies" in panel.warnings_label.text().lower()
    assert panel.jobs_queue_list.count() == 3
    assert "RUN" in panel.jobs_queue_list.item(0).text()
    assert "WAIT" in panel.jobs_queue_list.item(1).text()


def test_performance_panel_cancel_blocked_jobs_uses_job_ids(qtbot) -> None:
    cancelled: list[str] = []
    main_window = _MainWindowStub()
    main_window.jobs = SimpleNamespace(
        queue_snapshot=lambda: JobTelemetry(
            active_count=0,
            pending_count=1,
            blocked_count=1,
            total_submitted=1,
            total_finished=0,
            total_cancelled=0,
            total_errors=0,
            max_pending_jobs=4,
            running=(),
            pending=(
                JobSnapshot(
                    job_id="job-blocked",
                    name="Blocked ROI",
                    state="blocked",
                    priority=1,
                    queue_order=1,
                    replace_key=None,
                    dependencies=("job-parent",),
                    blocked_by=("job-parent",),
                ),
            ),
        ),
        cancel_matching=lambda **_kwargs: [],
        cancel=lambda job_id: cancelled.append(job_id) or True,
    )
    panel = PerformancePanel(parent=None)
    panel.main_window = main_window
    qtbot.addWidget(panel)

    panel._cancel_blocked_jobs()

    assert cancelled == ["job-blocked"]
    assert main_window._status_events == ["Cancelled 1 dependency-blocked jobs."]
