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


class TestRoiPositionColumns:
    """Test position display columns (z/t/c)."""

    def test_roi_position_bindings_all(self):
        """Test ROI with z/t/c bound to all slices."""
        roi = Roi(
            roi_id=1,
            name="TestROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            z_index=-1,  # -1 means "all"
            t_index=-1,
            c_index=-1,
        )
        assert roi.z_index == -1
        assert roi.t_index == -1
        assert roi.c_index == -1

    def test_roi_position_bindings_specific(self):
        """Test ROI bound to specific slices."""
        roi = Roi(
            roi_id=2,
            name="SliceROI",
            roi_type="circle",
            points=[(5, 5), (10, 5)],
            z_index=2,
            t_index=3,
            c_index=1,
        )
        assert roi.z_index == 2
        assert roi.t_index == 3
        assert roi.c_index == 1

    def test_roi_manager_set_position(self):
        """Test RoiManager set_roi_position method."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="PosROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Bind to specific slice
        assert manager.set_roi_position(roi.roi_id, z=5, t=3, c=2)

        # Verify binding
        retrieved_roi = manager.get_roi_by_id(roi.roi_id)
        assert retrieved_roi.z_index == 5
        assert retrieved_roi.t_index == 3
        assert retrieved_roi.c_index == 2

    def test_roi_manager_set_position_to_all(self):
        """Test binding ROI to all slices."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="AllROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            z_index=2,
            t_index=3,
            c_index=1,
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Bind to all slices
        assert manager.set_roi_position(roi.roi_id, z=-1, t=-1, c=-1)

        # Verify binding
        retrieved_roi = manager.get_roi_by_id(roi.roi_id)
        assert retrieved_roi.z_index == -1
        assert retrieved_roi.t_index == -1
        assert retrieved_roi.c_index == -1
