"""ROI tags system tests."""

import pytest
from phage_annotator.roi.manager import Roi, RoiManager
from phage_annotator.roi.commands import AddTagCommand, RemoveTagCommand


class TestRoiTags:
    """Test ROI tags system."""

    def test_roi_tags_initialized_empty(self):
        """Test that ROI tags are initialized as empty list."""
        roi = Roi(
            roi_id=1,
            name="TestROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        assert roi.tags == []

    def test_roi_tags_set(self):
        """Test setting tags on an ROI."""
        roi = Roi(
            roi_id=1,
            name="TaggedROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1", "important"],
        )
        assert roi.tags == ["group1", "important"]

    def test_add_tag_command(self):
        """Test AddTagCommand."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="ROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Add tag
        cmd = AddTagCommand(manager, image_id, roi.roi_id, "group1")
        assert cmd.execute() is True
        assert "group1" in roi.tags

    def test_add_tag_undo(self):
        """Test undoing AddTagCommand."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="ROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Add tag
        cmd = AddTagCommand(manager, image_id, roi.roi_id, "group1")
        assert manager.execute_command(cmd) is True
        assert "group1" in roi.tags

        # Undo
        assert manager.undo() is True
        assert "group1" not in roi.tags

    def test_add_tag_redo(self):
        """Test redoing AddTagCommand."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="ROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Add tag
        cmd = AddTagCommand(manager, image_id, roi.roi_id, "group1")
        assert manager.execute_command(cmd) is True

        # Undo
        assert manager.undo() is True

        # Redo
        assert manager.redo() is True
        assert "group1" in roi.tags

    def test_remove_tag_command(self):
        """Test RemoveTagCommand."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="ROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1", "important"],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Remove tag
        cmd = RemoveTagCommand(manager, image_id, roi.roi_id, "group1")
        assert cmd.execute() is True
        assert "group1" not in roi.tags
        assert "important" in roi.tags

    def test_remove_tag_undo(self):
        """Test undoing RemoveTagCommand."""
        manager = RoiManager()
        roi = Roi(
            roi_id=1,
            name="ROI",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1", "important"],
        )
        image_id = 42
        manager.add_roi(image_id, roi)

        # Remove tag
        cmd = RemoveTagCommand(manager, image_id, roi.roi_id, "group1")
        assert manager.execute_command(cmd) is True
        assert "group1" not in roi.tags

        # Undo
        assert manager.undo() is True
        assert "group1" in roi.tags

    def test_get_all_tags(self):
        """Test getting all unique tags in image."""
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
            tags=["group2", "important"],
        )
        roi3 = Roi(
            roi_id=3,
            name="ROI3",
            roi_type="box",
            points=[(40, 40), (50, 50)],
            tags=["group1"],
        )
        image_id = 42
        for roi in [roi1, roi2, roi3]:
            manager.add_roi(image_id, roi)

        # Get all tags
        all_tags = manager.get_all_tags(image_id)
        assert sorted(all_tags) == ["group1", "group2", "important"]

    def test_filter_rois_by_tag(self):
        """Test filtering ROIs by single tag."""
        manager = RoiManager()
        roi1 = Roi(
            roi_id=1,
            name="ROI1",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1"],
        )
        roi2 = Roi(
            roi_id=2,
            name="ROI2",
            roi_type="box",
            points=[(20, 20), (30, 30)],
            tags=["group2"],
        )
        roi3 = Roi(
            roi_id=3,
            name="ROI3",
            roi_type="box",
            points=[(40, 40), (50, 50)],
            tags=["group1"],
        )
        image_id = 42
        for roi in [roi1, roi2, roi3]:
            manager.add_roi(image_id, roi)

        # Filter by group1
        filtered = manager.filter_rois_by_tag(image_id, "group1")
        assert len(filtered) == 2
        assert all(roi.roi_id in [1, 3] for roi in filtered)

    def test_filter_rois_by_multiple_tags_any(self):
        """Test filtering ROIs by multiple tags (match any)."""
        manager = RoiManager()
        roi1 = Roi(
            roi_id=1,
            name="ROI1",
            roi_type="box",
            points=[(0, 0), (10, 10)],
            tags=["group1"],
        )
        roi2 = Roi(
            roi_id=2,
            name="ROI2",
            roi_type="box",
            points=[(20, 20), (30, 30)],
            tags=["group2"],
        )
        roi3 = Roi(
            roi_id=3,
            name="ROI3",
            roi_type="box",
            points=[(40, 40), (50, 50)],
            tags=["group3"],
        )
        roi4 = Roi(
            roi_id=4,
            name="ROI4",
            roi_type="box",
            points=[(60, 60), (70, 70)],
            tags=[],
        )
        image_id = 42
        for roi in [roi1, roi2, roi3, roi4]:
            manager.add_roi(image_id, roi)

        # Filter by group1 OR group2
        filtered = manager.filter_rois_by_tags(image_id, ["group1", "group2"], match_all=False)
        assert len(filtered) == 2
        assert all(roi.roi_id in [1, 2] for roi in filtered)

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
