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
        super().__init__(manager, image_id)
        self.roi = roi
    
    def execute(self) -> bool:
        # No before state for add
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
        super().__init__(manager, image_id)
        self.roi_id = roi_id
    
    def execute(self) -> bool:
        # Find and store the ROI before deleting
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
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_name = new_name
    
    def execute(self) -> bool:
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
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.name = self.memento_before.roi_data["name"]
            return True
        return False
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.name = self.memento_after.roi_data["name"]
            return True
        return False


class UpdateRoiGeometryCommand(RoiCommand):
    """Command to update ROI geometry."""
    
    def __init__(
        self,
        manager: "RoiManager",
        image_id: int,
        roi_id: int,
        new_points: List[Tuple[float, float]],
        new_roi_type: str,
    ):
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_points = new_points
        self.new_roi_type = new_roi_type
    
    def execute(self) -> bool:
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="update_roi_geometry",
            image_id=self.image_id,
            roi_data={
                "roi_id": self.roi_id,
                "points": list(roi.points),
                "roi_type": roi.roi_type,
            },
        )
        
        # Update geometry
        roi.points = list(self.new_points)
        roi.roi_type = self.new_roi_type
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="update_roi_geometry",
            image_id=self.image_id,
            roi_data={
                "roi_id": self.roi_id,
                "points": list(self.new_points),
                "roi_type": self.new_roi_type,
            },
        )
        return True
    
    def undo(self) -> bool:
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.points = [tuple(p) for p in self.memento_before.roi_data["points"]]
            roi.roi_type = self.memento_before.roi_data["roi_type"]
            return True
        return False
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.points = [tuple(p) for p in self.memento_after.roi_data["points"]]
            roi.roi_type = self.memento_after.roi_data["roi_type"]
            return True
        return False


class SetRoiPositionCommand(RoiCommand):
    """Command to set ROI position binding."""
    
    def __init__(
        self,
        manager: "RoiManager",
        image_id: int,
        roi_id: int,
        z_index: int = -1,
        t_index: int = -1,
        c_index: int = -1,
    ):
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_z = z_index
        self.new_t = t_index
        self.new_c = c_index
    
    def execute(self) -> bool:
        roi = self.manager.get_roi_by_id(self.roi_id)
        if not roi:
            return False
        
        # Store before state
        self.memento_before = RoiCommandMemento(
            command_type="set_roi_position",
            image_id=self.image_id,
            roi_data={
                "roi_id": self.roi_id,
                "z_index": roi.z_index,
                "t_index": roi.t_index,
                "c_index": roi.c_index,
            },
        )
        
        # Update position
        self.manager.set_roi_position(self.roi_id, self.new_z, self.new_t, self.new_c)
        
        # Store after state
        self.memento_after = RoiCommandMemento(
            command_type="set_roi_position",
            image_id=self.image_id,
            roi_data={
                "roi_id": self.roi_id,
                "z_index": self.new_z,
                "t_index": self.new_t,
                "c_index": self.new_c,
            },
        )
        return True
    
    def undo(self) -> bool:
        if not self.memento_before:
            return False
        data = self.memento_before.roi_data
        self.manager.set_roi_position(
            data["roi_id"],
            data["z_index"],
            data["t_index"],
            data["c_index"],
        )
        return True
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        data = self.memento_after.roi_data
        self.manager.set_roi_position(
            data["roi_id"],
            data["z_index"],
            data["t_index"],
            data["c_index"],
        )
        return True


class BatchDeleteRoisCommand(RoiCommand):
    """Command to delete multiple ROIs."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_ids: List[int]):
        super().__init__(manager, image_id)
        self.roi_ids = roi_ids
    
    def execute(self) -> bool:
        # Store all ROIs before deleting
        rois_data = []
        for roi_id in self.roi_ids:
            roi = self.manager.get_roi_by_id(roi_id)
            if roi:
                rois_data.append(self._roi_to_dict(roi))
        
        if not rois_data:
            return False
        
        self.memento_before = RoiCommandMemento(
            command_type="batch_delete_rois",
            image_id=self.image_id,
            roi_list=rois_data,
        )
        
        # Delete all ROIs
        for roi_id in self.roi_ids:
            self.manager.delete_roi(self.image_id, roi_id)
        
        self.memento_after = RoiCommandMemento(
            command_type="batch_delete_rois",
            image_id=self.image_id,
            roi_list=[],
        )
        return True
    
    def undo(self) -> bool:
        """Restore all deleted ROIs."""
        if not self.memento_before or not self.memento_before.roi_list:
            return False
        for roi_data in self.memento_before.roi_list:
            roi = self._dict_to_roi(roi_data)
            self.manager.add_roi(self.image_id, roi)
        return True
    
    def redo(self) -> bool:
        """Re-delete all ROIs."""
        if not self.memento_before or not self.memento_before.roi_list:
            return False
        for roi_data in self.memento_before.roi_list:
            self.manager.delete_roi(self.image_id, roi_data["roi_id"])
        return True


class AddTagCommand(RoiCommand):
    """Command to add a tag to an ROI."""
    
    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, tag: str):
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.tag = tag
    
    def execute(self) -> bool:
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
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_before.roi_data["tags"]
            return True
        return False
    
    def redo(self) -> bool:
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
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.tag = tag
    
    def execute(self) -> bool:
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
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_before.roi_data["tags"]
            return True
        return False
    
    def redo(self) -> bool:
        if not self.memento_after:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.tags = self.memento_after.roi_data["tags"]
            return True
        return False
