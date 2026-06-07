"""Split definitions from test_roi_features.py."""


import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace

from phage_annotator.roi.manager import Roi, RoiManager
from phage_annotator.roi.commands import (
    AddRoiCommand,
    DeleteRoiCommand,
    RenameRoiCommand,
    UpdateRoiGeometryCommand,
    BatchDeleteRoisCommand,
)
from phage_annotator.ui_qt.controls.roi import RoiControlsMixin


class TestRoiUndoRedo:
    """Test fine-grained undo/redo."""

    def test_undo_redo_stacks_initialized(self):
        """Test that undo/redo stacks are initialized."""
        manager = RoiManager()
        assert manager.can_undo() is False
        assert manager.can_redo() is False

    def test_add_roi_command_execute(self):
        """Test AddRoiCommand execution."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="TestROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42

        cmd = AddRoiCommand(manager, image_id, roi)
        assert cmd.execute() is True

        # Verify ROI was added
        retrieved = manager.get_roi_by_id(roi.roi_id)
        assert retrieved is not None
        assert retrieved.name == "TestROI"

    def test_add_roi_undo(self):
        """Test undoing an add ROI operation."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="UndoROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42

        cmd = AddRoiCommand(manager, image_id, roi)
        assert manager.execute_command(cmd) is True
        assert manager.can_undo() is True

        # Undo
        assert manager.undo() is True
        assert manager.get_roi_by_id(roi.roi_id) is None
        assert manager.can_redo() is True

    def test_add_roi_redo(self):
        """Test redoing an add ROI operation."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="RedoROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42

        cmd = AddRoiCommand(manager, image_id, roi)
        assert manager.execute_command(cmd) is True

        # Undo then redo
        assert manager.undo() is True
        assert manager.redo() is True

        # Verify ROI is back
        retrieved = manager.get_roi_by_id(roi.roi_id)
        assert retrieved is not None
        assert retrieved.name == "RedoROI"

    def test_delete_roi_undo(self):
        """Test undoing a delete ROI operation."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="DelROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Delete with command
        cmd = DeleteRoiCommand(manager, image_id, roi.roi_id)
        assert manager.execute_command(cmd) is True
        assert manager.get_roi_by_id(roi.roi_id) is None

        # Undo
        assert manager.undo() is True
        retrieved = manager.get_roi_by_id(roi.roi_id)
        assert retrieved is not None
        assert retrieved.name == "DelROI"

    def test_rename_roi_undo(self):
        """Test undoing a rename operation."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="OldName",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Rename with command
        cmd = RenameRoiCommand(manager, image_id, roi.roi_id, "NewName")
        assert manager.execute_command(cmd) is True
        assert manager.get_roi_by_id(roi.roi_id).name == "NewName"

        # Undo
        assert manager.undo() is True
        assert manager.get_roi_by_id(roi.roi_id).name == "OldName"

    def test_update_geometry_undo(self):
        """Test undoing a geometry update operation."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="GeomROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        original_points = roi.points.copy()

        # Update geometry
        new_points = [(5, 5), (15, 15)]
        cmd = UpdateRoiGeometryCommand(
            manager, image_id, roi.roi_id, new_points, "box"
        )
        assert manager.execute_command(cmd) is True
        assert manager.get_roi_by_id(roi.roi_id).points == new_points

        # Undo
        assert manager.undo() is True
        assert manager.get_roi_by_id(roi.roi_id).points == original_points

    def test_batch_delete_undo(self):
        """Test undoing a batch delete operation."""
        manager = RoiManager()
        rois = [
            Roi(roi_id=i, name=f"ROI{i}", roi_type="box", points=[(0, 0), (10, 10)])
            for i in range(3)
        ]
        image_id = 42
        for roi in rois:
            manager.add_roi(image_id, roi)

        roi_ids = [roi.roi_id for roi in rois]

        # Delete all with command
        cmd = BatchDeleteRoisCommand(manager, image_id, roi_ids)
        assert manager.execute_command(cmd) is True

        # Verify all deleted
        for roi_id in roi_ids:
            assert manager.get_roi_by_id(roi_id) is None

        # Undo
        assert manager.undo() is True

        # Verify all restored
        for roi_id in roi_ids:
            assert manager.get_roi_by_id(roi_id) is not None

    def test_undo_clears_redo_stack(self):
        """Test that executing a new command after undo clears redo stack."""
        manager = RoiManager()
        roi1 = Roi(
            roi_id=1,
            name="ROI1",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        roi2 = Roi(
            roi_id=2,
            name="ROI2",
            roi_type="box",
            points=[(20, 20), (30, 30)],
        )
        image_id = 42

        # Execute 2 commands
        cmd1 = AddRoiCommand(manager, image_id, roi1)
        cmd2 = AddRoiCommand(manager, image_id, roi2)
        manager.execute_command(cmd1)
        manager.execute_command(cmd2)

        # Undo to get redo capability
        manager.undo()
        assert manager.can_redo() is True

        # Execute new command
        roi3 = Roi(roi_id=3, name="ROI3", roi_type="box", points=[(40, 40), (50, 50)])
        cmd3 = AddRoiCommand(manager, image_id, roi3)
        manager.execute_command(cmd3)

        # Redo should be disabled
        assert manager.can_redo() is False

    def test_undo_redo_multiple_operations(self):
        """Test undo/redo with multiple operations."""
        manager = RoiManager()
        image_id = 42
        roi = Roi(
            roi_id=1,
            name="MultiROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )

        # Execute: Add -> Rename -> Update geometry
        cmd1 = AddRoiCommand(manager, image_id, roi)
        manager.execute_command(cmd1)

        cmd2 = RenameRoiCommand(manager, image_id, roi.roi_id, "Renamed")
        manager.execute_command(cmd2)

        cmd3 = UpdateRoiGeometryCommand(
            manager, image_id, roi.roi_id, [(5, 5), (15, 15)], "box"
        )
        manager.execute_command(cmd3)

        # Undo 3 times
        assert manager.undo() is True  # Undo update
        assert manager.undo() is True  # Undo rename
        assert manager.undo() is True  # Undo add

        # ROI should be gone
        assert manager.get_roi_by_id(roi.roi_id) is None

        # Redo 3 times
        assert manager.redo() is True  # Redo add
        assert manager.redo() is True  # Redo rename
        assert manager.redo() is True  # Redo update

        # Verify final state
        final_roi = manager.get_roi_by_id(roi.roi_id)
        assert final_roi.name == "Renamed"
        assert final_roi.points == [(5, 5), (15, 15)]
