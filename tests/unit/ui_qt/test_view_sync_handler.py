"""Regression tests for the linked view-sync handler contract."""

from __future__ import annotations

from types import SimpleNamespace

import phage_annotator.ui_qt.controls.display as display_module
from phage_annotator.ui_qt.controls.display import DisplayControlsMixin


class _Axis:
    def __init__(self) -> None:
        self.xlim = None
        self.ylim = None

    def set_xlim(self, left: float, right: float) -> None:
        self.xlim = (left, right)

    def set_ylim(self, top: float, bottom: float) -> None:
        self.ylim = (top, bottom)


class _Harness(DisplayControlsMixin):
    def __init__(self) -> None:
        self._panel_sync_reverse = {0: "modality_0"}
        self.renderer = SimpleNamespace(axes={"modality_0": _Axis()})
        self._last_display_shape = (100, 200)
        self._suppress_limits = False
        self.link_zoom = True
        self._last_zoom_linked = None
        self.controller = object()


def test_view_sync_handler_accepts_full_signal_signature(monkeypatch) -> None:
    emitted: list[tuple[object, dict]] = []

    def _record_emit(controller, **payload):
        emitted.append((controller, dict(payload)))

    monkeypatch.setattr(display_module, "emit_view_changed", _record_emit)

    harness = _Harness()
    harness._on_view_sync_changed(0, 2.0, 20.0, 10.0, 7, 3)

    axis = harness.renderer.axes["modality_0"]
    assert axis.xlim == (20.0, 120.0)
    assert axis.ylim == (60.0, 10.0)
    assert harness._last_zoom_linked == ((20.0, 120.0), (60.0, 10.0))
    assert emitted == [
        (
            harness.controller,
            {
                "change_type": "view_sync",
                "viewport": {
                    "panel_key": "modality_0",
                    "modality_idx": 0,
                    "zoom": 2.0,
                    "pan_x": 20.0,
                    "pan_y": 10.0,
                    "xlim": (20.0, 120.0),
                    "ylim": (60.0, 10.0),
                },
            },
        )
    ]
