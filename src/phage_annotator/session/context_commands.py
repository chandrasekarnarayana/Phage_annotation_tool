"""Context annotation commands for near-point context actions.

The commands in this module are designed for right-click annotation workflows
and integrate with the shared command stack for undo/redo safety.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.core.annotation import Keypoint
from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.utils.hit_testing import HitTester, LocalMaxSnapper


def _coerce_index(value, default: int = 0) -> int:
    """Coerce scalar index-like values while avoiding mock-object surprises."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return int(default)


def _emit_annotations_changed(controller: "SessionController") -> None:
    """Notify listeners that annotation data changed."""
    emit_annotations_changed(controller)


def _annotation_to_snapshot(annotation: Keypoint) -> dict:
    """Convert a keypoint to a serializable snapshot."""
    return {
        "image_id": int(getattr(annotation, "image_id", -1)),
        "image_name": str(getattr(annotation, "image_name", "")),
        "t": int(getattr(annotation, "t", -1)),
        "z": int(getattr(annotation, "z", -1)),
        "y": float(getattr(annotation, "y", 0.0)),
        "x": float(getattr(annotation, "x", 0.0)),
        "label": str(getattr(annotation, "label", "phage")),
        "annotation_id": str(getattr(annotation, "annotation_id", "")),
        "image_key": str(getattr(annotation, "image_key", "")),
        "source": str(getattr(annotation, "source", "manual")),
        "meta": dict(getattr(annotation, "meta", {})),
        "modality_idx": getattr(annotation, "modality_idx", None),
    }


def _snapshot_to_annotation(snapshot: dict) -> Keypoint:
    """Reconstruct a keypoint from a snapshot."""
    return Keypoint(
        image_id=int(snapshot.get("image_id", -1)),
        image_name=str(snapshot.get("image_name", "")),
        t=int(snapshot.get("t", -1)),
        z=int(snapshot.get("z", -1)),
        y=float(snapshot.get("y", 0.0)),
        x=float(snapshot.get("x", 0.0)),
        label=str(snapshot.get("label", "phage")),
        annotation_id=str(snapshot.get("annotation_id", "")),
        image_key=str(snapshot.get("image_key", snapshot.get("image_name", ""))),
        source=str(snapshot.get("source", "manual")),
        meta=dict(snapshot.get("meta", {})),
        modality_idx=snapshot.get("modality_idx"),
    )


def _find_annotation_index_by_id(
    controller: "SessionController",
    image_id: int,
    annotation_id: str,
) -> int:
    """Return index of annotation by ID, or -1 if not found."""
    annotations = controller.session_state.annotations.get(image_id, [])
    for idx, annotation in enumerate(annotations):
        if annotation.annotation_id == annotation_id:
            return idx
    return -1


def _iter_slice_annotations(
    controller: "SessionController",
    image_id: int,
):
    """Iterate annotations visible on the active T/Z slice."""
    t_idx = _coerce_index(getattr(controller.view_state, "t", 0), default=0)
    z_idx = _coerce_index(getattr(controller.view_state, "z", 0), default=0)
    for annotation in controller.session_state.annotations.get(image_id, []):
        annotation_t = _coerce_index(getattr(annotation, "t", -1), default=-1)
        annotation_z = _coerce_index(getattr(annotation, "z", -1), default=-1)
        if annotation_t in (t_idx, -1) and annotation_z in (z_idx, -1):
            yield annotation


class DeleteNearestCommand(Command):
    """Command to delete the nearest annotation to a point."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        x: float,
        y: float,
        radius: float = 20.0,
    ):
        """Initialize delete nearest command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID.
        x, y : float
            Screen/display coordinate of the click.
        radius : float, default 20.0
            Hit radius in display pixels.
        """
        super().__init__(controller, image_id)
        self.x = x
        self.y = y
        self.radius = radius
        self.deleted_annotation_id: Optional[str] = None
        self.deleted_annotation_data: Optional[dict] = None
        self.deleted_index: Optional[int] = None
    
    def execute(self) -> bool:
        """Find and delete the nearest annotation within radius."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        if not annotations:
            return False

        slice_annotations = list(_iter_slice_annotations(self.controller, self.image_id))
        nearest = HitTester.find_nearest(slice_annotations, self.x, self.y, radius=self.radius)
        if nearest is None:
            return False

        target, _ = nearest
        target_idx = _find_annotation_index_by_id(
            self.controller, self.image_id, target.annotation_id
        )
        if target_idx < 0:
            return False

        self.deleted_annotation_id = target.annotation_id
        self.deleted_annotation_data = _annotation_to_snapshot(target)
        self.deleted_index = target_idx

        self.memento_before = CommandMemento(
            command_type="delete_nearest",
            image_id=self.image_id,
            data={
                "annotation_id": self.deleted_annotation_id,
                "annotation_snapshot": self.deleted_annotation_data,
                "index": self.deleted_index,
            },
        )

        annotations.pop(target_idx)
        _emit_annotations_changed(self.controller)

        self.memento_after = CommandMemento(
            command_type="delete_nearest",
            image_id=self.image_id,
            data={
                "annotation_id": self.deleted_annotation_id,
                "index": self.deleted_index,
            },
        )

        return True
    
    def undo(self) -> bool:
        """Restore the deleted annotation."""
        if self.memento_before is None:
            return False

        snapshot = self.memento_before.data.get("annotation_snapshot")
        if not isinstance(snapshot, dict):
            return False
        index = int(self.memento_before.data.get("index", -1))
        annotations = self.controller.session_state.annotations.setdefault(self.image_id, [])
        restored = _snapshot_to_annotation(snapshot)
        if index < 0 or index >= len(annotations):
            annotations.append(restored)
        else:
            annotations.insert(index, restored)
        _emit_annotations_changed(self.controller)
        return True
    
    def redo(self) -> bool:
        """Re-delete the annotation."""
        if self.memento_after is None:
            return False
        annotation_id = self.memento_after.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        idx = _find_annotation_index_by_id(self.controller, self.image_id, annotation_id)
        if idx < 0:
            return False
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        annotations.pop(idx)
        _emit_annotations_changed(self.controller)
        return True

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None


class MarkUncertainCommand(Command):
    """Command to mark nearest annotation as uncertain."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        x: float,
        y: float,
        radius: float = 20.0,
        *,
        uncertain: bool = True,
    ):
        """Initialize mark uncertain command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID.
        x, y : float
            Screen/display coordinate of the click.
        radius : float, default 20.0
            Hit radius in display pixels.
        """
        super().__init__(controller, image_id)
        self.x = x
        self.y = y
        self.radius = radius
        self.uncertain = bool(uncertain)
        self.target_annotation_id: Optional[str] = None
        self.was_uncertain: Optional[bool] = None
    
    def execute(self) -> bool:
        """Find and mark nearest annotation as uncertain."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        if not annotations:
            return False

        slice_annotations = list(_iter_slice_annotations(self.controller, self.image_id))
        nearest = HitTester.find_nearest(slice_annotations, self.x, self.y, radius=self.radius)
        if nearest is None:
            return False

        target, _ = nearest
        self.target_annotation_id = target.annotation_id
        self.was_uncertain = bool(target.meta.get("uncertain", False))

        self.memento_before = CommandMemento(
            command_type="mark_uncertain",
            image_id=self.image_id,
            data={
                "annotation_id": self.target_annotation_id,
                "was_uncertain": self.was_uncertain,
            },
        )

        target.meta["uncertain"] = self.uncertain
        _emit_annotations_changed(self.controller)

        self.memento_after = CommandMemento(
            command_type="mark_uncertain",
            image_id=self.image_id,
            data={
                "annotation_id": self.target_annotation_id,
                "is_uncertain": self.uncertain,
            },
        )

        return True
    
    def undo(self) -> bool:
        """Restore uncertain flag to previous state."""
        if self.memento_before is None:
            return False
        annotation_id = self.memento_before.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        previous = bool(self.memento_before.data.get("was_uncertain", False))
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for ann in annotations:
            if ann.annotation_id == annotation_id:
                ann.meta["uncertain"] = previous
                _emit_annotations_changed(self.controller)
                return True
        return False
    
    def redo(self) -> bool:
        """Re-mark as uncertain."""
        if self.memento_after is None:
            return False
        annotation_id = self.memento_after.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        state = bool(self.memento_after.data.get("is_uncertain", True))
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for ann in annotations:
            if ann.annotation_id == annotation_id:
                ann.meta["uncertain"] = state
                _emit_annotations_changed(self.controller)
                return True
        return False

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None


class EditNearestMetadataCommand(Command):
    """Command to update label/metadata on the nearest annotation."""

    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        x: float,
        y: float,
        radius: float,
        *,
        annotation_id: Optional[str] = None,
        new_label: Optional[str],
        new_meta: dict,
    ):
        super().__init__(controller, image_id)
        self.x = x
        self.y = y
        self.radius = radius
        self.annotation_id = annotation_id
        self.new_label = new_label
        self.new_meta = dict(new_meta)

    def execute(self) -> bool:
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        if not annotations:
            return False

        target = None
        if self.annotation_id is not None:
            for ann in annotations:
                if ann.annotation_id == self.annotation_id:
                    target = ann
                    break
            if target is None:
                return False
        else:
            slice_annotations = list(_iter_slice_annotations(self.controller, self.image_id))
            nearest = HitTester.find_nearest(slice_annotations, self.x, self.y, radius=self.radius)
            if nearest is None:
                return False
            target, _ = nearest

        old_label = target.label
        old_meta = dict(target.meta)
        if old_label == self.new_label and old_meta == self.new_meta:
            return False

        self.memento_before = CommandMemento(
            command_type="edit_nearest_metadata",
            image_id=self.image_id,
            data={
                "annotation_id": target.annotation_id,
                "old_label": old_label,
                "old_meta": old_meta,
            },
        )

        target.meta = dict(self.new_meta)
        if self.new_label is not None:
            target.label = self.new_label
        _emit_annotations_changed(self.controller)

        self.memento_after = CommandMemento(
            command_type="edit_nearest_metadata",
            image_id=self.image_id,
            data={
                "annotation_id": target.annotation_id,
                "new_label": target.label,
                "new_meta": dict(target.meta),
            },
        )
        return True

    def undo(self) -> bool:
        if self.memento_before is None:
            return False
        annotation_id = self.memento_before.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for ann in annotations:
            if ann.annotation_id == annotation_id:
                ann.label = str(self.memento_before.data.get("old_label", ann.label))
                ann.meta = dict(self.memento_before.data.get("old_meta", ann.meta))
                _emit_annotations_changed(self.controller)
                return True
        return False

    def redo(self) -> bool:
        if self.memento_after is None:
            return False
        annotation_id = self.memento_after.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for ann in annotations:
            if ann.annotation_id == annotation_id:
                ann.label = str(self.memento_after.data.get("new_label", ann.label))
                ann.meta = dict(self.memento_after.data.get("new_meta", ann.meta))
                _emit_annotations_changed(self.controller)
                return True
        return False

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None


class SnapToLocalMaxCommand(Command):
    """Command to snap nearest annotation to local maximum."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        x: float,
        y: float,
        radius: float = 20.0,
        search_radius: float = 10.0,
        image_data=None,
    ):
        """Initialize snap to local max command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID.
        x, y : float
            Initial coordinate.
        radius : float, default 20.0
            Hit radius for finding nearest annotation.
        search_radius : float, default 10.0
            Search radius for local maximum.
        """
        super().__init__(controller, image_id)
        self.x = x
        self.y = y
        self.radius = radius
        self.search_radius = search_radius
        self.image_data = image_data
        self.target_annotation_id: Optional[str] = None
        self.old_x: Optional[float] = None
        self.old_y: Optional[float] = None
        self.new_x: Optional[float] = None
        self.new_y: Optional[float] = None
    
    def execute(self) -> bool:
        """Find nearest annotation and snap to local maximum."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        if not annotations:
            return False

        slice_annotations = list(_iter_slice_annotations(self.controller, self.image_id))
        nearest = HitTester.find_nearest(slice_annotations, self.x, self.y, radius=self.radius)
        if nearest is None:
            return False

        target, _ = nearest
        self.target_annotation_id = target.annotation_id
        self.old_x = float(target.x)
        self.old_y = float(target.y)

        if self.image_data is None:
            new_x, new_y = self.old_x, self.old_y
        else:
            new_x, new_y = LocalMaxSnapper.snap_to_local_max(
                self.image_data,
                x=self.old_x,
                y=self.old_y,
                search_radius=self.search_radius,
            )
        self.new_x = float(new_x)
        self.new_y = float(new_y)

        self.memento_before = CommandMemento(
            command_type="snap_to_local_max",
            image_id=self.image_id,
            data={
                "annotation_id": self.target_annotation_id,
                "old_x": self.old_x,
                "old_y": self.old_y,
            },
        )

        target.x = self.new_x
        target.y = self.new_y
        _emit_annotations_changed(self.controller)

        self.memento_after = CommandMemento(
            command_type="snap_to_local_max",
            image_id=self.image_id,
            data={
                "annotation_id": self.target_annotation_id,
                "new_x": self.new_x,
                "new_y": self.new_y,
            },
        )

        return True
    
    def undo(self) -> bool:
        """Restore to original position."""
        if self.memento_before is None:
            return False
        annotation_id = self.memento_before.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        old_x = self.memento_before.data.get("old_x")
        old_y = self.memento_before.data.get("old_y")
        if old_x is None or old_y is None:
            return False
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for ann in annotations:
            if ann.annotation_id == annotation_id:
                ann.x = float(old_x)
                ann.y = float(old_y)
                _emit_annotations_changed(self.controller)
                return True
        return False
    
    def redo(self) -> bool:
        """Re-snap to local maximum."""
        if self.memento_after is None:
            return False
        annotation_id = self.memento_after.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        new_x = self.memento_after.data.get("new_x")
        new_y = self.memento_after.data.get("new_y")
        if new_x is None or new_y is None:
            return False
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for ann in annotations:
            if ann.annotation_id == annotation_id:
                ann.x = float(new_x)
                ann.y = float(new_y)
                _emit_annotations_changed(self.controller)
                return True
        return False

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None
