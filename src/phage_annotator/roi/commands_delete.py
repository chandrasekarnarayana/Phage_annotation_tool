"""Delete/clear ROI commands: DeleteRoiCommand, BatchDeleteRoisCommand, tag commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from phage_annotator.roi.manager import Roi, RoiManager

from phage_annotator.roi.commands_draw import RoiCommand, RoiCommandMemento


class DeleteRoiCommand(RoiCommand):
    """Command to delete an ROI."""

    def __init__(self, manager: "RoiManager", image_id: int, roi_id: int):
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_id = roi_id

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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


class BatchDeleteRoisCommand(RoiCommand):
    """Command to delete multiple ROIs."""

    def __init__(self, manager: "RoiManager", image_id: int, roi_ids: List[int]):
        """Initialize the object and prepare its runtime state."""
        super().__init__(manager, image_id)
        self.roi_ids = roi_ids

    def execute(self) -> bool:
        """Execute execute for the current workflow."""
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


class RemoveTagCommand(RoiCommand):
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
