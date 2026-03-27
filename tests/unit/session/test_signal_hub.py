"""Tests for centralized controller signal helpers."""

from __future__ import annotations

from types import SimpleNamespace

import phage_annotator.session.signal_hub as signal_hub
from phage_annotator.framework.events import ViewStateChangedEvent


class _Emitter:
    """Qt-like signal stub for unit tests."""

    def __init__(self) -> None:
        self.calls = 0

    def emit(self) -> None:
        self.calls += 1


class _RecordingEmitter:
    """Qt-like signal stub that records emission ordering."""

    def __init__(self, events: list[object], label: str, controller=None) -> None:
        self.events = events
        self.label = label
        self.controller = controller

    def emit(self) -> None:
        dirty = None
        if self.controller is not None:
            dirty = getattr(getattr(self.controller, "session_state", None), "dirty", None)
        self.events.append((self.label, dirty))


def test_emit_view_changed_publishes_viewport_payload(
    monkeypatch,
) -> None:
    """Canvas sync metadata should flow through the centralized event hub."""
    published: list[object] = []
    controller = SimpleNamespace(view_changed=_Emitter())

    monkeypatch.setattr(signal_hub, "publish_event", lambda event: published.append(event))

    signal_hub.emit_view_changed(
        controller,
        change_type="view_sync",
        viewport={"panel_key": "frame", "zoom": 2.0, "pan_x": 10.0, "pan_y": 20.0},
    )

    assert controller.view_changed.calls == 1
    assert len(published) == 1
    assert isinstance(published[0], ViewStateChangedEvent)
    assert published[0].change_type == "view_sync"
    assert published[0].viewport == {
        "panel_key": "frame",
        "zoom": 2.0,
        "pan_x": 10.0,
        "pan_y": 20.0,
    }


def test_emit_view_changed_emits_qt_signal_before_event_bus(monkeypatch) -> None:
    """Immediate Qt sync should fire before the cross-component event publication."""
    observed: list[object] = []
    controller = SimpleNamespace(view_changed=_RecordingEmitter(observed, "qt"))

    monkeypatch.setattr(
        signal_hub,
        "publish_event",
        lambda event: observed.append(("event", event.change_type)),
    )

    signal_hub.emit_view_changed(controller, change_type="crop", crop_rect=(1.0, 2.0, 3.0, 4.0))

    assert observed == [("qt", None), ("event", "crop")]


def test_emit_annotations_changed_marks_dirty_then_emits_qt_then_events(monkeypatch) -> None:
    """Annotation updates should dirty the session before Qt/event consumers observe them."""
    observed: list[object] = []
    controller = SimpleNamespace(
        session_state=SimpleNamespace(active_primary_id=0, dirty=False, annotations={0: []}),
        annotations_changed=_RecordingEmitter(observed, "qt", controller=None),
    )
    controller.annotations_changed.controller = controller

    monkeypatch.setattr(
        signal_hub,
        "publish_event",
        lambda event: observed.append(("event", type(event).__name__)),
    )

    signal_hub.emit_annotations_changed(controller, image_id=0, change_type="modified")

    assert controller.session_state.dirty is True
    assert observed == [
        ("qt", True),
        ("event", "AnnotationChangedEvent"),
        ("event", "CacheInvalidationEvent"),
    ]


def test_annotation_notification_batch_coalesces_qt_emits_but_keeps_per_image_events(monkeypatch) -> None:
    """Batch annotation updates should emit one Qt notification and per-image events on flush."""
    observed: list[object] = []
    controller = SimpleNamespace(
        session_state=SimpleNamespace(active_primary_id=0, dirty=False, annotations={1: [], 2: []}),
        annotations_changed=_RecordingEmitter(observed, "qt", controller=None),
    )
    controller.annotations_changed.controller = controller

    monkeypatch.setattr(
        signal_hub,
        "publish_event",
        lambda event: observed.append(
            ("event", type(event).__name__, getattr(event, "image_id", None), getattr(event, "change_type", None))
        ),
    )

    with signal_hub.annotation_notification_batch(controller):
        signal_hub.emit_annotations_changed(controller, image_id=1, change_type="removed")
        signal_hub.emit_annotations_changed(controller, image_id=2, change_type="added", invalidate_cache=False)
        assert observed == []
        assert controller.session_state.dirty is True

    assert observed == [
        ("qt", True),
        ("event", "AnnotationChangedEvent", 1, "removed"),
        ("event", "CacheInvalidationEvent", 1, None),
        ("event", "AnnotationChangedEvent", 2, "added"),
    ]
