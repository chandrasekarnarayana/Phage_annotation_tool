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
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_points = new_points
        self.new_roi_type = new_roi_type
    
    def execute(self) -> bool:
        """Document the execute flow."""
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
        """Document the undo flow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.points = [tuple(p) for p in self.memento_before.roi_data["points"]]
            roi.roi_type = self.memento_before.roi_data["roi_type"]
            return True
        return False
    
    def redo(self) -> bool:
        """Document the redo flow."""
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
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_z = z_index
        self.new_t = t_index
        self.new_c = c_index
    
    def execute(self) -> bool:
        """Document the execute flow."""
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
        """Document the undo flow."""
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
        """Document the redo flow."""
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
        """Document the init flow."""
        super().__init__(manager, image_id)
        self.roi_ids = roi_ids
    
    def execute(self) -> bool:
        # Store all ROIs before deleting
        """Document the execute flow."""
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
