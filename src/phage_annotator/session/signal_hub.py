"""Centralized signal emit helpers for SessionController.

Keeps signal triggering in one place so callers avoid scattered hard-coded
signal access and can progressively migrate to event-bus-backed reactions.

Contract:
- controller Qt signals drive immediate GUI synchronization
- application events drive cross-component/service reactions
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Mapping, Optional

from phage_annotator.framework import get_event_service
from phage_annotator.framework.events import (
    AnnotationChangedEvent,
    ApplicationEvent,
    CacheInvalidationEvent,
    ViewStateChangedEvent,
)


def _get_action_logger():
    """Lazy import to avoid circular dependencies."""
    try:
        from phage_annotator.ui_qt.services.action_logger import get_action_logger
        return get_action_logger()
    except ImportError:
        return None


class ControllerSignals:
    """Canonical SessionController signal names."""

    STATE_CHANGED = "state_changed"
    VIEW_CHANGED = "view_changed"
    DISPLAY_CHANGED = "display_changed"
    ANNOTATIONS_CHANGED = "annotations_changed"
    PLAYBACK_CHANGED = "playback_changed"
    ERROR_OCCURRED = "error_occurred"
    ROI_CHANGED = "roi_changed"


_ANNOTATION_BATCH_DEPTH_ATTR = "_annotation_signal_batch_depth"
_ANNOTATION_BATCH_STATE_ATTR = "_annotation_signal_batch_state"


def emit_controller_signal(controller: Any, signal_name: str, *args: Any) -> None:
    """Emit a Qt signal by canonical string name if available."""
    signal = getattr(controller, signal_name, None)
    if signal is None:
        return
    try:
        signal.emit(*args)
    except Exception:
        return


def publish_event(event: ApplicationEvent) -> None:
    """Publish an application event if the global event service is ready."""
    try:
        get_event_service().publish(event)
    except Exception:
        return


def emit_state_changed(controller: Any) -> None:
    emit_controller_signal(controller, ControllerSignals.STATE_CHANGED)
    logger = _get_action_logger()
    if logger:
        logger.log_action("state_changed", details={"signal": "state_changed"})


def _merge_annotation_change_type(previous: str | None, current: str) -> str:
    """Collapse multiple per-image change types into one safe summary."""
    if not previous:
        return str(current)
    if previous == current:
        return str(previous)
    return "modified"


def _annotation_batch_state(controller: Any) -> dict[int, dict[str, Any]]:
    state = getattr(controller, _ANNOTATION_BATCH_STATE_ATTR, None)
    if not isinstance(state, dict):
        state = {}
        setattr(controller, _ANNOTATION_BATCH_STATE_ATTR, state)
    return state


def _flush_annotation_batch(controller: Any) -> None:
    pending = dict(getattr(controller, _ANNOTATION_BATCH_STATE_ATTR, {}) or {})
    setattr(controller, _ANNOTATION_BATCH_STATE_ATTR, {})
    if not pending:
        return
    emit_controller_signal(controller, ControllerSignals.ANNOTATIONS_CHANGED)
    
    logger = _get_action_logger()
    total_count = sum(len(list(controller.session_state.annotations.get(int(img_id), []))) for img_id in pending)
    if logger:
        logger.log_action(
            "annotations_batch_flushed",
            panel="annotate",
            details={
                "image_count": len(pending),
                "total_annotations": total_count,
                "image_ids": sorted(int(k) for k in pending)
            }
        )
    
    for image_id in sorted(int(k) for k in pending):
        entry = dict(pending.get(int(image_id), {}) or {})
        annotations = []
        try:
            annotations = list(controller.session_state.annotations.get(int(image_id), []))
        except Exception:
            annotations = []
        publish_event(
            AnnotationChangedEvent(
                image_id=int(image_id),
                annotations=annotations,
                change_type=str(entry.get("change_type", "modified")),
            )
        )
        if bool(entry.get("invalidate_cache", True)):
            publish_event(CacheInvalidationEvent(scope="image", image_id=int(image_id)))


@contextmanager
def annotation_notification_batch(controller: Any):
    """Coalesce repeated annotation notifications into one Qt emit plus per-image events."""
    depth = int(getattr(controller, _ANNOTATION_BATCH_DEPTH_ATTR, 0) or 0)
    setattr(controller, _ANNOTATION_BATCH_DEPTH_ATTR, depth + 1)
    try:
        yield
    finally:
        remaining = max(0, int(getattr(controller, _ANNOTATION_BATCH_DEPTH_ATTR, 1) or 1) - 1)
        setattr(controller, _ANNOTATION_BATCH_DEPTH_ATTR, remaining)
        if remaining == 0:
            _flush_annotation_batch(controller)


def emit_view_changed(
    controller: Any,
    *,
    change_type: Optional[str] = None,
    t_index: Optional[int] = None,
    z_index: Optional[int] = None,
    roi_rect: Optional[tuple] = None,
    crop_rect: Optional[tuple] = None,
    viewport: Optional[Mapping[str, Any]] = None,
) -> None:
    emit_controller_signal(controller, ControllerSignals.VIEW_CHANGED)
    
    logger = _get_action_logger()
    if logger and change_type:
        logger.log_action(
            "view_state_changed",
            details={
                "change_type": change_type,
                "t_index": t_index,
                "z_index": z_index,
                "roi_rect": str(roi_rect) if roi_rect else None,
                "crop_rect": str(crop_rect) if crop_rect else None,
            }
        )
    
    if change_type:
        publish_event(
            ViewStateChangedEvent(
                change_type=str(change_type),
                t_index=t_index,
                z_index=z_index,
                roi_rect=roi_rect,
                crop_rect=crop_rect,
                viewport=dict(viewport or {}) if viewport else None,
            )
        )


def emit_display_changed(controller: Any) -> None:
    emit_controller_signal(controller, ControllerSignals.DISPLAY_CHANGED)
    logger = _get_action_logger()
    if logger:
        logger.log_action("display_state_changed", details={"signal": "display_changed"})


def emit_playback_changed(controller: Any) -> None:
    emit_controller_signal(controller, ControllerSignals.PLAYBACK_CHANGED)
    logger = _get_action_logger()
    if logger:
        logger.log_action("playback_state_changed", details={"signal": "playback_changed"})


def emit_roi_changed(controller: Any) -> None:
    emit_controller_signal(controller, ControllerSignals.ROI_CHANGED)
    logger = _get_action_logger()
    if logger:
        logger.log_action("roi_state_changed", details={"signal": "roi_changed"})


def emit_error(controller: Any, message: str) -> None:
    emit_controller_signal(controller, ControllerSignals.ERROR_OCCURRED, str(message))
    logger = _get_action_logger()
    if logger:
        logger.log_action("error_signal", details={"message": str(message)}, error=str(message))


def emit_annotations_changed(
    controller: Any,
    *,
    image_id: Optional[int] = None,
    change_type: str = "modified",
    invalidate_cache: bool = True,
) -> None:
    """Emit centralized annotation-change updates to Qt + event bus."""
    if hasattr(controller, "session_state"):
        controller.session_state.dirty = True

    if image_id is None:
        image_id = int(getattr(getattr(controller, "session_state", None), "active_primary_id", 0))
    if int(getattr(controller, _ANNOTATION_BATCH_DEPTH_ATTR, 0) or 0) > 0:
        pending = _annotation_batch_state(controller)
        entry = dict(pending.get(int(image_id), {}) or {})
        entry["change_type"] = _merge_annotation_change_type(entry.get("change_type"), str(change_type))
        entry["invalidate_cache"] = bool(entry.get("invalidate_cache", False) or invalidate_cache)
        pending[int(image_id)] = entry
        setattr(controller, _ANNOTATION_BATCH_STATE_ATTR, pending)
        return

    emit_controller_signal(controller, ControllerSignals.ANNOTATIONS_CHANGED)

    annotations = []
    try:
        annotations = list(controller.session_state.annotations.get(int(image_id), []))
    except Exception:
        annotations = []

    publish_event(
        AnnotationChangedEvent(
            image_id=int(image_id),
            annotations=annotations,
            change_type=str(change_type),
        )
    )
    if invalidate_cache:
        publish_event(CacheInvalidationEvent(scope="image", image_id=int(image_id)))
