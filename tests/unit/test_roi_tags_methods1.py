"""Method group 1 split from test_roi_tags.py."""

import pytest
from phage_annotator.roi.manager import Roi, RoiManager
from phage_annotator.roi.commands import AddTagCommand, RemoveTagCommand


class _TestRoiTagsMethods1:
    """Methods split from TestRoiTags."""

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
