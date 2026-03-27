from __future__ import annotations

from phage_annotator.ui_qt.utils.jobs import JobsMixin


class _LogStub(JobsMixin):
    def __init__(self) -> None:
        self.log_view = object()
        self._all_logs = []
        self.refresh_calls = 0
        self.bottom_updates = 0

    def _refresh_log_view(self) -> None:
        self.refresh_calls += 1

    def _update_bottom_task_panels(self) -> None:
        self.bottom_updates += 1


def test_append_log_stores_structured_entry() -> None:
    stub = _LogStub()

    stub._append_log("[JOB] Error: Projection failed", severity="ERROR", category="Job", details="Trace")

    assert len(stub._all_logs) == 1
    entry = stub._all_logs[0]
    assert entry["severity"] == "ERROR"
    assert entry["category"] == "Job"
    assert entry["summary"] == "[JOB] Error: Projection failed"
    assert entry["details"] == "Trace"
    assert stub.refresh_calls == 1
    assert stub.bottom_updates == 1


def test_append_log_infers_warning_and_category_from_text() -> None:
    stub = _LogStub()

    stub._append_log("[CACHE] Warning: pressure rising")

    entry = stub._all_logs[0]
    assert entry["severity"] == "WARNING"
    assert entry["category"] == "CACHE"
