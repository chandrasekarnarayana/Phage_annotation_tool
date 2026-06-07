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


@dataclass



class RoiCommandMemento:
    """Snapshot of ROI state for undo/redo."""
    command_type: str
    image_id: int
    roi_data: Dict[str, Any] = field(default_factory=dict)
    roi_list: List[Dict[str, Any]] = field(default_factory=list)

class RoiCommand:
    """Base class for undoable ROI commands."""
    
    def __init__(self, manager: "RoiManager", image_id: int):
        """Document the init flow."""
        self.manager = manager
        self.image_id = image_id
        self.memento_before: Optional[RoiCommandMemento] = None
        self.memento_after: Optional[RoiCommandMemento] = None
    
    def execute(self) -> bool:
        """Execute the command and store state for undo."""
        raise NotImplementedError
    
    def undo(self) -> bool:
        """Undo the command using stored state."""
        raise NotImplementedError
    
    def redo(self) -> bool:
        """Redo the command using stored state."""
        raise NotImplementedError
    
    def to_dict(self) -> dict:
        """Serialize command for stack storage."""
        return {
            "type": self.__class__.__name__,
            "image_id": self.image_id,
            "before": asdict(self.memento_before) if self.memento_before else None,
            "after": asdict(self.memento_after) if self.memento_after else None,
        }
    
    def _roi_to_dict(self, roi: "Roi") -> Dict[str, Any]:
        """Convert ROI to dictionary."""
        return {
            "roi_id": roi.roi_id,
            "name": roi.name,
            "roi_type": roi.roi_type,
            "points": list(roi.points),
            "color": roi.color,
            "visible": roi.visible,
            "z_index": roi.z_index,
            "t_index": roi.t_index,
            "c_index": roi.c_index,
        }
    
    def _dict_to_roi(self, data: Dict[str, Any]) -> "Roi":
        """Convert dictionary to ROI."""
        from phage_annotator.roi.manager import Roi
        return Roi(
            roi_id=data["roi_id"],
            name=data["name"],
            roi_type=data["roi_type"],
            points=[tuple(p) for p in data["points"]],
            color=data["color"],
            visible=data["visible"],
            z_index=data.get("z_index", -1),
            t_index=data.get("t_index", -1),
            c_index=data.get("c_index", -1),
        )

class AddRoiCommand(RoiCommand):
    """Command to add a new ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi: "Roi"):
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi = roi
    
    def execute(self) -> bool:
        # No before state for add
        """Document the execute flow."""
        self.memento_before = RoiCommandMemento(
            command_type="add_roi",
            image_id=self.image_id,
            roi_data=None,
        )
        
        # Add the ROI
        self.manager.add_roi(self.image_id, self.roi)
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="add_roi",
            image_id=self.image_id,
            roi_data=self._roi_to_dict(self.roi),
        )
        return True
    
    def undo(self) -> bool:
        """Remove the added ROI."""
        if not self.memento_after:
            return False
        roi_id = self.memento_after.roi_data["roi_id"]
        self.manager.delete_roi(self.image_id, roi_id)
        return True
    
    def redo(self) -> bool:
        """Re-add the ROI."""
        if not self.memento_after:
            return False
        roi = self._dict_to_roi(self.memento_after.roi_data)
        self.manager.add_roi(self.image_id, roi)
        return True

class DeleteRoiCommand(RoiCommand):
    """Command to delete an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int):
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
    
    def execute(self) -> bool:
        # Find and store the ROI before deleting
        """Document the execute flow."""
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi:
            return False
        
        self.memento_before = RoiCommandMemento(
            command_type="delete_roi",
            image_id=self.image_id,
            roi_data=self._roi_to_dict(roi),
        )
        
        # Delete the ROI
        self.manager.delete_roi(self.image_id, self.roi_id)
        
        # No after state
        self.memento_after = RoiCommandMemento(
            command_type="delete_roi",
            image_id=self.image_id,
            roi_data=None,
        )
        return True
    
    def undo(self) -> bool:
        """Restore the deleted ROI."""
        if not self.memento_before or not self.memento_before.roi_data:
            return False
        roi = self._dict_to_roi(self.memento_before.roi_data)
        self.manager.add_roi(self.image_id, roi)
        return True
    
    def redo(self) -> bool:
        """Re-delete the ROI."""
        if not self.memento_before:
            return False
        roi_id = self.memento_before.roi_data["roi_id"]
        self.manager.delete_roi(self.image_id, roi_id)
        return True

class RenameRoiCommand(RoiCommand):
    """Command to rename an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, new_name: str):
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_name = new_name
    
    def execute(self) -> bool:
        """Document the execute flow."""
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="rename_roi",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "name": roi.name},
        )
        
        # Rename
        roi.name = self.new_name
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="rename_roi",
            image_id=self.image_id,
            roi_data={"roi_id": self.roi_id, "name": self.new_name},
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.name = self.memento_before.roi_data["name"]
            return True
        return False
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.name = self.memento_after.roi_data["name"]
            return True
        return False
