"""Edit/modify ROI commands: rename, update geometry, set position."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from phage_annotator.roi.manager import Roi, RoiManager

from phage_annotator.roi.commands_draw import RoiCommand, RoiCommandMemento


class RenameRoiCommand(RoiCommand):
    """Command to rename an ROI."""

    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int, new_name: str):
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_name = new_name

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.name = self.memento_before.roi_data["name"]
            return True
        return False

    def redo(self) -> bool:
        """Run the redo workflow."""
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
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_points = new_points
        self.new_roi_type = new_roi_type

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
        if not self.memento_before:
            return False
        roi = self.manager.get_roi_by_id(self.roi_id)
        if roi:
            roi.points = [tuple(p) for p in self.memento_before.roi_data["points"]]
            roi.roi_type = self.memento_before.roi_data["roi_type"]
            return True
        return False

    def redo(self) -> bool:
        """Run the redo workflow."""
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
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id
        self.new_z = z_index
        self.new_t = t_index
        self.new_c = c_index

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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
        """Undo undo for the current workflow."""
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
        """Run the redo workflow."""
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
