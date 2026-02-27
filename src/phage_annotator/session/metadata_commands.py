"""Commands for annotation metadata updates (undoable).

Metadata mutations are command-based to support undo/redo and maintain
consistency with the session's command stack.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController
    from phage_annotator.core.annotation import Keypoint

from phage_annotator.session.commands import Command, CommandMemento


class UpdateMetadataCommand(Command):
    """Command to update metadata for a single annotation.
    
    Supports changing any field in the annotation's metadata dict.
    """
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        annotation_id: str,
        field_name: str,
        new_value: Any,
    ):
        """Initialize metadata update command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID (used for grouping).
        annotation_id : str
            Unique annotation ID.
        field_name : str
            Metadata field to update.
        new_value : Any
            New value for the field.
        """
        super().__init__(controller, image_id)
        self.annotation_id = annotation_id
        self.field_name = field_name
        self.new_value = new_value
        self.old_value: Optional[Any] = None
    
    def execute(self) -> bool:
        """Execute metadata update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        # Store old value
        self.old_value = keypoint.meta.get(self.field_name)
        
        # Update metadata
        keypoint.meta[self.field_name] = self.new_value
        
        # Mark session as dirty
        self.controller.session_state.dirty = True
        
        # Store mementos
        self.memento_before = CommandMemento(
            command_type="update_metadata",
            image_id=self.image_id,
            data={
                "annotation_id": self.annotation_id,
                "field": self.field_name,
                "old_value": self.old_value,
            },
        )
        self.memento_after = CommandMemento(
            command_type="update_metadata",
            image_id=self.image_id,
            data={
                "annotation_id": self.annotation_id,
                "field": self.field_name,
                "new_value": self.new_value,
            },
        )
        
        return True
    
    def undo(self) -> bool:
        """Undo metadata update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        keypoint.meta[self.field_name] = self.old_value
        self.controller.session_state.dirty = True
        return True
    
    def redo(self) -> bool:
        """Redo metadata update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        keypoint.meta[self.field_name] = self.new_value
        self.controller.session_state.dirty = True
        return True
    
    def _find_annotation(self) -> Optional["Keypoint"]:
        """Find annotation in session by ID."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for annotation in annotations:
            if annotation.annotation_id == self.annotation_id:
                return annotation
        return None


class BulkUpdateMetadataCommand(Command):
    """Command to update metadata for multiple annotations.
    
    All updates are grouped as a single undo item.
    """
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        updates: List[tuple],
    ):
        """Initialize bulk metadata update command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller.
        image_id : int
            Image ID (for grouping).
        updates : List[tuple]
            List of (annotation_id, field_name, new_value) tuples.
        """
        super().__init__(controller, image_id)
        self.updates = updates
        self.old_values: Dict[str, Dict[str, Any]] = {}  # annotation_id -> {field: value}
    
    def execute(self) -> bool:
        """Execute bulk metadata updates."""
        # Store old values
        for annotation_id, field_name, new_value in self.updates:
            keypoint = self._find_annotation(annotation_id)
            if keypoint is None:
                return False
            
            if annotation_id not in self.old_values:
                self.old_values[annotation_id] = {}
            self.old_values[annotation_id][field_name] = keypoint.meta.get(field_name)
            
            # Apply update
            keypoint.meta[field_name] = new_value
        
        # Mark session as dirty
        self.controller.session_state.dirty = True
        
        # Store mementos
        self.memento_before = CommandMemento(
            command_type="bulk_update_metadata",
            image_id=self.image_id,
            data={"updates": len(self.updates)},
        )
        self.memento_after = CommandMemento(
            command_type="bulk_update_metadata",
            image_id=self.image_id,
            data={"updates": len(self.updates)},
        )
        
        return True
    
    def undo(self) -> bool:
        """Undo all metadata updates."""
        for annotation_id, fields in self.old_values.items():
            keypoint = self._find_annotation(annotation_id)
            if keypoint is None:
                return False
            
            for field_name, old_value in fields.items():
                keypoint.meta[field_name] = old_value
        
        self.controller.session_state.dirty = True
        return True
    
    def redo(self) -> bool:
        """Redo all metadata updates."""
        for annotation_id, field_name, new_value in self.updates:
            keypoint = self._find_annotation(annotation_id)
            if keypoint is None:
                return False
            
            keypoint.meta[field_name] = new_value
        
        self.controller.session_state.dirty = True
        return True
    
    def _find_annotation(self, annotation_id: str) -> Optional["Keypoint"]:
        """Find annotation in session by ID."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for annotation in annotations:
            if annotation.annotation_id == annotation_id:
                return annotation
        return None


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
        
        # Mark session as dirty
        self.controller.session_state.dirty = True
        
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
        
        return True
    
    def undo(self) -> bool:
        """Undo label update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        keypoint.label = self.old_label
        self.controller.session_state.dirty = True
        return True
    
    def redo(self) -> bool:
        """Redo label update."""
        keypoint = self._find_annotation()
        if keypoint is None:
            return False
        
        keypoint.label = self.new_label
        self.controller.session_state.dirty = True
        return True
    
    def _find_annotation(self) -> Optional["Keypoint"]:
        """Find annotation in session by ID."""
        annotations = self.controller.session_state.annotations.get(self.image_id, [])
        for annotation in annotations:
            if annotation.annotation_id == self.annotation_id:
                return annotation
        return None
