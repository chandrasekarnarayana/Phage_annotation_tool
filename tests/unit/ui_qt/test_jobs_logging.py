"""Unit tests for Qt job logging helpers."""

from __future__ import annotations

from phage_annotator.ui_qt.utils.jobs import JobsMixin


class _LogStub(JobsMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.log_view = object()
        self._all_logs = []
        self.refresh_calls = 0
        self.bottom_updates = 0

    def _refresh_log_view(self) -> None:
        """Refresh log view for the current workflow."""
        self.refresh_calls += 1

    def _update_bottom_task_panels(self) -> None:
        """Update bottom task panels for the current workflow."""
        self.bottom_updates += 1


def test_append_log_stores_structured_entry() -> None:
    """Verify append log stores structured entry for the current workflow."""
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
    """Verify append log infers warning and category from text for the current workflow."""
    stub = _LogStub()

    stub._append_log("[CACHE] Warning: pressure rising")

    entry = stub._all_logs[0]
    assert entry["severity"] == "WARNING"
    assert entry["category"] == "CACHE"
