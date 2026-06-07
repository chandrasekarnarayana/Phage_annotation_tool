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
from phage_annotator.utils.hit_testing import HitTester, LocalMaxSnapper





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

        slice_annotations = list(iter_slice_annotations(self.controller, self.image_id))
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
        emit_context_annotations_changed(self.controller)

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
                emit_context_annotations_changed(self.controller)
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
                emit_context_annotations_changed(self.controller)
                return True
        return False

    def emit_change_signals(self) -> None:
        """Context commands publish annotation changes internally."""
        return None
