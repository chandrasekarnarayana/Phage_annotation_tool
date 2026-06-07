"""Undo/redo commands for ROI Manager operations.

This module provides undoable commands for ROI management operations,
enabling full undo/redo support for ROI edits, additions, deletions,
and property changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from phage_annotator.roi.manager import Roi, RoiManager

from phage_annotator.roi.commands_draw import RoiCommand, RoiCommandMemento


@dataclass





class AddTagCommand(RoiCommand):
    """Command to add a tag to an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, tag: str):
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.tag = tag
    
    def execute(self) -> bool:
        """Document the execute flow."""
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi or self.tag in roi.tags:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="add_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)},
        )
        
        # Add tag
        roi.tags.append(self.tag)
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="add_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)},
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_before.roi_data["tags"]
            return True
        return False
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_after.roi_data["tags"]
            return True
        return False



class RemoveTagCommand(RoiCommand):
    """Command to remove a tag from an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, tag: str):
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.tag = tag
    
    def execute(self) -> bool:
        """Document the execute flow."""
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi or self.tag not in roi.tags:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="remove_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)},
        )
        
        # Remove tag
        roi.tags.remove(self.tag)
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="remove_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)},
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_before.roi_data["tags"]
            return True
        return False
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_after.roi_data["tags"]
            return True
        return False
