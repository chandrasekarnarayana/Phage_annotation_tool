"""Method group 2 split from test_roi_tags.py."""

import pytest
from phage_annotator.roi.manager import Roi, RoiManager
from phage_annotator.roi.commands import AddTagCommand, RemoveTagCommand


class _TestRoiTagsMethods2:
    """Methods split from TestRoiTags."""

    def test_filter_rois_by_multiple_tags_all(self):
        """Test filtering ROIs by multiple tags (match all)."""
        manager = RoiManager()
        roi1 = Roi(
            roi_id=1,
            name="ROI1",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1", "important"],
        )
        roi2 = Roi(
            roi_id=2,
            name="ROI2",
            roi_type="box",
            points=[(20, 20), (30, 30)],
            tags=["group1"],
        )
        roi3 = Roi(
            roi_id=3,
            name="ROI3",
            roi_type="box",
            points=[(40, 40), (50, 50)],
            tags=["important"],
        )
        image_id = 42
        for roi in [roi1, roi2, roi3]:
            manager.add_roi(image_id, roi)

        # Filter by group1 AND important
        filtered = manager.filter_rois_by_tags(image_id, ["group1", "important"], match_all=True)
        assert len(filtered) == 1
        assert filtered[0].roi_id == 1

    def test_tags_in_json_serialization(self):
        """Test that tags are preserved in JSON serialization."""
        from phage_annotator.roi.manager import save_rois_json, load_rois_json
        import tempfile

        roi = Roi(
            roi_id=1,
            name="TaggedROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1", "important"],
        )

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name

        # Save
        save_rois_json(temp_path, [roi])

        # Load
        loaded_rois = load_rois_json(temp_path)

        # Verify tags preserved
        assert len(loaded_rois) == 1
        assert loaded_rois[0].tags == ["group1", "important"]

    def test_tags_backward_compatibility(self):
        """Test that old ROI JSON without tags loads correctly."""
        from phage_annotator.roi.manager import roi_from_dict

        # Old format without tags
        old_roi_dict = {
            "id": 1,
            "name": "OldROI",
            "type": "box",
            "points": [(0, 0), (10, 10)],
            "color": "#ffcc00",
            "visible": True,
            "z_index": -1,
            "t_index": -1,
            "c_index": -1,
            # No tags field
        }

        roi = roi_from_dict(old_roi_dict, 1)
        assert roi.tags == []  # Should default to empty list

    def test_multiple_tag_operations_undo_redo(self):
        """Test undoing/redoing multiple tag operations."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="ROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Add 3 tags
        cmd1 = AddTagCommand(manager, image_id, roi.roi_id, "tag1")
        cmd2 = AddTagCommand(manager, image_id, roi.roi_id, "tag2")
        cmd3 = AddTagCommand(manager, image_id, roi.roi_id, "tag3")

        manager.execute_command(cmd1)
        manager.execute_command(cmd2)
        manager.execute_command(cmd3)

        assert len(roi.tags) == 3

        # Undo all 3
        manager.undo()
        manager.undo()
        manager.undo()

        assert len(roi.tags) == 0

        # Redo all 3
        manager.redo()
        manager.redo()
        manager.redo()

        assert len(roi.tags) == 3
        assert set(roi.tags) == {"tag1", "tag2", "tag3"}
