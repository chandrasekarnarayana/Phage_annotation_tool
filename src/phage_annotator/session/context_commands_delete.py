"""Context annotation commands for near-point context actions.

The commands in this module are designed for right-click annotation workflows
and integrate with the shared command stack for undo/redo safety.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.context_command_support import (
    annotation_to_snapshot,
    emit_context_annotations_changed,
    find_annotation_index_by_id,
    iter_slice_annotations,
    snapshot_to_annotation,
)
from phage_annotator.utils.hit_testing import HitTester





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

        slice_annotations = list(iter_slice_annotations(self.controller, self.image_id))
        nearest = HitTester.find_nearest(slice_annotations, self.x, self.y, radius=self.radius)
        if nearest is None:
            return False

        target, _ = nearest
        target_idx = find_annotation_index_by_id(
            self.controller, self.image_id, target.annotation_id
        )
        if target_idx < 0:
            return False

        self.deleted_annotation_id = target.annotation_id
        self.deleted_annotation_data = annotation_to_snapshot(target)
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
        emit_context_annotations_changed(self.controller)

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
        restored = snapshot_to_annotation(snapshot)
        if index < 0 or index >= len(annotations):
            annotations.append(restored)
        else:
            annotations.insert(index, restored)
        emit_context_annotations_changed(self.controller)
        return True
    
    def redo(self) -> bool:
        """Re-delete the annotation."""
        if self.memento_after is None:
            return False
        annotation_id = self.memento_after.data.get("annotation_id")
        if not isinstance(annotation_id, str):
            return False
        idx = find_annotation_index_by_id(self.controller, self.image_id, annotation_id)
        if idx < 0:
            return False
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        annotations.pop(idx)
        emit_context_annotations_changed(self.controller)
        return True

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None
