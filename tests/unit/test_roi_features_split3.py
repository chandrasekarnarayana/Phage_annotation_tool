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


class TestRoiIntegration:
    """Test integration with existing ROI features."""

    def test_position_persistence_in_json(self):
        """Test that position values are preserved via JSON serialization."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="PersistROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            z_index=5,
            t_index=3,
            c_index=1,
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Verify position attributes are present
        assert roi.z_index == 5
        assert roi.t_index == 3
        assert roi.c_index == 1

        # Test JSON save/load via the manager's functions
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        # Save ROIs
        from phage_annotator.roi.manager import save_rois_json, load_rois_json
        save_rois_json(temp_path, manager.list_rois(image_id))
        
        # Load ROIs
        loaded_rois = load_rois_json(temp_path)
        
        # Verify position values were preserved
        assert len(loaded_rois) == 1
        loaded_roi = loaded_rois[0]
        assert loaded_roi.z_index == 5
        assert loaded_roi.t_index == 3
        assert loaded_roi.c_index == 1

    def test_undo_redo_with_position_changes(self):
        """Test undo/redo works with position binding changes."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="PosROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            z_index=-1,
            t_index=-1,
            c_index=-1,
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Bind to specific slice using SetRoiPositionCommand
        from phage_annotator.roi.commands import SetRoiPositionCommand

        cmd = SetRoiPositionCommand(manager, image_id, roi.roi_id, z_index=5, t_index=3, c_index=1)
        manager.execute_command(cmd)

        # Verify binding
        bound_roi = manager.get_roi_by_id(roi.roi_id)
        assert bound_roi.z_index == 5
        assert bound_roi.t_index == 3
        assert bound_roi.c_index == 1

        # Undo
        manager.undo()
        unbound_roi = manager.get_roi_by_id(roi.roi_id)
        assert unbound_roi.z_index == -1
        assert unbound_roi.t_index == -1
        assert unbound_roi.c_index == -1

class _MeasureHarness(RoiControlsMixin):
    _roi_measurement_frame = RoiControlsMixin._roi_measurement_frame
    _roi_measurement_rows = RoiControlsMixin._roi_measurement_rows
    _roi_measurement_default_path = RoiControlsMixin._roi_measurement_default_path
    _roi_measurement_summary_text = RoiControlsMixin._roi_measurement_summary_text
    _write_roi_measurements_csv = RoiControlsMixin._write_roi_measurements_csv

    def __init__(self, array: np.ndarray) -> None:
        """Initialize the object and prepare its runtime state."""
        self.primary_image = SimpleNamespace(id=7, array=array)

def test_roi_measurement_frame_supports_tyx() -> None:
    """ROI measurement should accept T/Y/X stacks without assuming a Z axis."""
    harness = _MeasureHarness(np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5))

    frame0 = harness._roi_measurement_frame(harness.primary_image.array, 0)
    frame1 = harness._roi_measurement_frame(harness.primary_image.array, 1)

    assert frame0.shape == (5, 5)
    assert frame1.shape == (5, 5)
    assert float(frame1[0, 0]) == 25.0

def test_roi_measurement_frame_supports_tzyx() -> None:
    """ROI measurement should still select the first Z plane for T/Z/Y/X stacks."""
    harness = _MeasureHarness(np.arange(2 * 3 * 5 * 5, dtype=np.float32).reshape(2, 3, 5, 5))

    frame = harness._roi_measurement_frame(harness.primary_image.array, 1)

    assert frame.shape == (5, 5)
    assert float(frame[0, 0]) == 75.0

def test_roi_measurement_rows_include_traceable_context_and_stable_order() -> None:
    """ROI measurement rows should include ROI/image bindings and deterministic ordering."""
    harness = _MeasureHarness(np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5))
    rois = [
        Roi(roi_id=3, name="beta", roi_type="box", points=[(1, 1), (3, 3)], z_index=2, t_index=4, c_index=1),
        Roi(roi_id=2, name="alpha", roi_type="box", points=[(1, 1), (3, 3)], z_index=-1, t_index=-1, c_index=-1),
    ]

    rows = harness._roi_measurement_rows(harness.primary_image.array, rois, image_id=7)

    assert len(rows) == 4
    assert rows[0]["Image_ID"] == 7
    assert rows[0]["Image_Shape"] == "2x5x5"
    assert rows[0]["Frame_T"] == 0
    assert rows[0]["ROI_ID"] == 2
    assert rows[0]["ROI_Name"] == "alpha"
    assert rows[0]["ROI_Tags"] == ""
    assert rows[0]["ROI_Z_Binding"] == -1
    assert rows[1]["ROI_ID"] == 3
    assert rows[1]["ROI_T_Binding"] == 4
    assert "Area_px2" in rows[0]
    assert "Mean_Intensity" in rows[0]
    assert "Centroid_X_px" in rows[0]
    assert rows[2]["Frame_T"] == 1

def test_roi_measurement_summary_text_includes_aggregate_context() -> None:
    """Measurement summary should expose row count and aggregate signal/area context."""
    harness = _MeasureHarness(np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5))
    rows = harness._roi_measurement_rows(
        harness.primary_image.array,
        [Roi(roi_id=2, name="alpha", roi_type="box", points=[(1, 1), (3, 3)], tags=["qc"])],
        image_id=7,
    )

    summary = harness._roi_measurement_summary_text(rows, roi_count=1, frame_count=2, image_id=7)

    assert "Image 7" in summary
    assert "1 ROI(s)" in summary
    assert "2 frame(s)" in summary
    assert "measurement row(s)" in summary
    assert "Mean area" in summary
    assert "Mean signal" in summary

def test_roi_measurement_default_path_includes_image_id() -> None:
    """ROI measurement export filename should include image identity for traceability."""
    harness = _MeasureHarness(np.zeros((1, 5, 5), dtype=np.float32))

    path = harness._roi_measurement_default_path()

    assert "roi_measurements_image_7_" in path.name
    assert path.suffix == ".csv"
