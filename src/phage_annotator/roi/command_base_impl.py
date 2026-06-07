"""Roi command base impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from phage_annotator.roi.command_base import RoiCommand
from phage_annotator.roi.roi_interactor_core import RoiInteractorCoreMixin
from phage_annotator.roi.manager_core_impl import RoiManager
from phage_annotator.roi.roi_model import RoiModelMixin

if TYPE_CHECKING:
    from phage_annotator.roi.manager import Roi, RoiManager



class AddTagCommand(RoiCommand, RoiManager, RoiInteractorCoreMixin, RoiModelMixin):
    """Command to add a tag to an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, tag: str):
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.tag = tag
    
    def execute(self) -> bool:
        """Execute execute for the current workflow."""
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi or self.tag in roi.tags:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="add_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)})
        
        # Add tag
        roi.tags.append(self.tag)
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="add_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)})
        return True
    
    def undo(self) -> bool:
        """Undo undo for the current workflow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_before.roi_data["tags"]
            return True
        return False
    
    def redo(self) -> bool:
        """Run the redo workflow."""
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_after.roi_data["tags"]
            return True
        return False

class RemoveTagCommand(RoiCommand, RoiManager, RoiInteractorCoreMixin, RoiModelMixin):
    """Command to remove a tag from an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, tag: str):
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.tag = tag
    
    def execute(self) -> bool:
        """Execute execute for the current workflow."""
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi or self.tag not in roi.tags:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="remove_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)})
        
        # Remove tag
        roi.tags.remove(self.tag)
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="remove_tag",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "tags": list(roi.tags)})
        return True
    
    def undo(self) -> bool:
        """Undo undo for the current workflow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_before.roi_data["tags"]
            return True
        return False
    
    def redo(self) -> bool:
        """Run the redo workflow."""
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_after.roi_data["tags"]
            return True
        return False
