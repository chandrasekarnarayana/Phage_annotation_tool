"""Shared helpers for context annotation commands.

The command classes live in separate focused modules, while this module keeps
their common hit-testing, snapshot, and notification logic in one place.
"""

from __future__ import annotations

from typing import Iterator

from phage_annotator.core.annotation import Keypoint
from phage_annotator.session.signal_hub import emit_annotations_changed


def iter_slice_annotations(controller, image_id: int) -> Iterator[object]:
    """Yield annotations visible on the controller's current t/z slice."""
    annotations = controller.session_state.annotations.get(image_id, [])
    view_state = getattr(controller, "view_state", None)
    current_t = getattr(view_state, "t", None)
    current_z = getattr(view_state, "z", None)
    if not isinstance(current_t, int):
        current_t = None
    if not isinstance(current_z, int):
        current_z = None
    for annotation in annotations:
        ann_t = getattr(annotation, "t", current_t)
        ann_z = getattr(annotation, "z", current_z)
        if current_t is not None and ann_t not in (-1, current_t):
            continue
        if current_z is not None and ann_z not in (-1, current_z):
            continue
        yield annotation


def find_annotation_index_by_id(controller, image_id: int, annotation_id: str) -> int:
    """Return the storage index for an annotation id, or -1 when absent."""
    annotations = controller.session_state.annotations.get(image_id, [])
    for index, annotation in enumerate(annotations):
        if getattr(annotation, "annotation_id", None) == annotation_id:
            return index
    return -1


def annotation_to_snapshot(annotation) -> dict:
    """Copy an annotation into a command-history snapshot."""
    return {
        "image_id": getattr(annotation, "image_id", 0),
        "image_name": getattr(annotation, "image_name", ""),
        "t": getattr(annotation, "t", -1),
        "z": getattr(annotation, "z", -1),
        "x": float(getattr(annotation, "x", 0.0)),
        "y": float(getattr(annotation, "y", 0.0)),
        "label": getattr(annotation, "label", "phage"),
        "annotation_id": getattr(annotation, "annotation_id", ""),
        "image_key": getattr(annotation, "image_key", ""),
        "source": getattr(annotation, "source", "manual"),
        "modality_idx": getattr(annotation, "modality_idx", None),
        "annotation_context": getattr(annotation, "annotation_context", ""),
        "meta": dict(getattr(annotation, "meta", {}) or {}),
    }


def snapshot_to_annotation(snapshot: dict) -> Keypoint:
    """Rebuild a Keypoint from a command-history snapshot."""
    return Keypoint(
        image_id=int(snapshot.get("image_id", 0)),
        image_name=str(snapshot.get("image_name", "")),
        t=int(snapshot.get("t", -1)),
        z=int(snapshot.get("z", -1)),
        y=float(snapshot.get("y", 0.0)),
        x=float(snapshot.get("x", 0.0)),
        label=str(snapshot.get("label", "phage")),
        annotation_id=str(snapshot.get("annotation_id", "")),
        image_key=str(snapshot.get("image_key", "")),
        source=str(snapshot.get("source", "manual")),
        meta=dict(snapshot.get("meta", {}) or {}),
        modality_idx=snapshot.get("modality_idx"),
        annotation_context=str(snapshot.get("annotation_context", "")),
    )


def emit_context_annotations_changed(controller) -> None:
    """Notify listeners after context commands mutate annotations."""
    emit_annotations_changed(controller)
