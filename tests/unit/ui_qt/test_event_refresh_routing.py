"""Regression tests for controller-to-refresh routing decisions."""

from __future__ import annotations

from phage_annotator.ui_qt.actions.events import EventsMixin


class _Harness(EventsMixin):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._controller_view_refresh_hint = None

    def _request_ui_refresh(self, reason: str, **kwargs) -> None:
        self.calls.append((reason, dict(kwargs)))


def test_controller_view_sync_hint_skips_image_refresh() -> None:
    harness = _Harness()
    harness._controller_view_refresh_hint = "view_sync"

    harness._on_controller_view_changed()

    assert harness.calls == [("controller-view-sync", {"image": False, "status": True})]


def test_controller_view_default_requests_image_refresh() -> None:
    harness = _Harness()

    harness._on_controller_view_changed()

    assert harness.calls == [("controller-view", {"image": True, "status": True})]
