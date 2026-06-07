"""Split definitions from metadata_commands.py."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController
    from phage_annotator.core.annotation import Keypoint

from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.signal_hub import emit_annotations_changed


from phage_annotator.session.metadata_commands_split1 import _emit_metadata_changed

class UpdateLabelCommand(Command):
    """Command to change annotation label.
    
    Special case of UpdateMetadataCommand for label field.
    """
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        annotation_id: str,
        new_label: str,
    ):
        """Initialize label update command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID.
        annotation_id : str
            Unique annotation ID.
        new_label : str
            New label string.
        """
        super().__init__(controller, image_id)
        self.annotation_id = annotation_id
        self.new_label = new_label
        self.old_label: Optional[str] = None
    
    def execute(self) -> bool:
        """Execute label update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        # Store old label
        self.old_label = keypoint.label
        
        # Update label
        keypoint.label = self.new_label
        
        # Store mementos
        self.memento_before = CommandMemento(
            command_type="update_label",
            image_id=self.image_id,
            data={
                "annotation_id": self.annotation_id,
                "old_label": self.old_label,
            },
        )
        self.memento_after = CommandMemento(
            command_type="update_label",
            image_id=self.image_id,
            data={
                "annotation_id": self.annotation_id,
                "new_label": self.new_label,
            },
        )
        _emit_metadata_changed(self.controller, self.image_id)
        return True
    
    def undo(self) -> bool:
        """Undo label update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        keypoint.label = self.old_label
        _emit_metadata_changed(self.controller, self.image_id)
        return True
    
    def redo(self) -> bool:
        """Redo label update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        keypoint.label = self.new_label
        _emit_metadata_changed(self.controller, self.image_id)
        return True
    
    def _find_annotation(self) -> Optional["Keypoint"]:
        """Find annotation in session by ID."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for annotation in annotations:
            if annotation.annotation_id == self.annotation_id:
                return annotation
        return None

    def emit_change_signals(self) -> None:
        """Metadata commands publish annotation changes internally."""
        return None
