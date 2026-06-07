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
    emit_context_annotations_changed,
    iter_slice_annotations,
)
from phage_annotator.utils.hit_testing import HitTester





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

        slice_annotations = list(iter_slice_annotations(self.controller, self.image_id))
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
        emit_context_annotations_changed(self.controller)

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
                emit_context_annotations_changed(self.controller)
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
                emit_context_annotations_changed(self.controller)
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
        """Document the init flow."""
        super().__init__(controller, image_id)
        self.x = x
        self.y = y
        self.radius = radius
        self.annotation_id = annotation_id
        self.new_label = new_label
        self.new_meta = dict(new_meta)

    def execute(self) -> bool:
        """Document the execute flow."""
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
            slice_annotations = list(iter_slice_annotations(self.controller, self.image_id))
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
        emit_context_annotations_changed(self.controller)

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
        """Document the undo flow."""
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
                emit_context_annotations_changed(self.controller)
                return True
        return False

    def redo(self) -> bool:
        """Document the redo flow."""
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
                emit_context_annotations_changed(self.controller)
                return True
        return False

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None
