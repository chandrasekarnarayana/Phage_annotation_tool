"""Unit tests for context annotation actions.

Tests cover:
- Hit testing accuracy
- Local maximum snapping
- Context commands (delete, uncertain, snap)
- Transaction semantics for bulk operations
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, Mock
from types import SimpleNamespace

from phage_annotator.session.context_commands import (
    DeleteNearestCommand,
    EditNearestMetadataCommand,
    MarkUncertainCommand,
    SnapToLocalMaxCommand,
)
from phage_annotator.core.session_state import ViewState
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.annotations import SessionAnnotationsMixin
from phage_annotator.session.view import SessionViewMixin
from phage_annotator.utils.hit_testing import HitTester, LocalMaxSnapper


class MockKeypoint:
    """Mock annotation for testing."""
    
    def __init__(
        self,
        x: float,
        y: float,
        label: str = "test",
        annotation_id: str = "test_1",
    ):
        self.image_id = 0
        self.image_name = "mock_image"
        self.t = 0
        self.z = 0
        self.x = x
        self.y = y
        self.label = label
        self.annotation_id = annotation_id
        self.image_key = "mock_image"
        self.source = "manual"
        self.modality_idx = None
        self.meta = {}


class _Emitter:
    def emit(self) -> None:
        """Qt-like signal stub for controller harness tests."""


class _ContextCommandHarness(SessionViewMixin, SessionAnnotationsMixin):
    """Minimal controller harness for context command stack tests."""

    def __init__(self, annotations):
        self._undo_stack = []
        self._redo_stack = []
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.session_state = SimpleNamespace(
            annotations={0: annotations},
            dirty=False,
        )
        self.view_state = ViewState(t=0, z=0)
        self.display_mapping = DisplayMapping(0.0, 1.0)

    def set_dirty(self, dirty: bool = True) -> None:
        self.session_state.dirty = dirty


class TestHitTester:
    """Tests for hit testing utilities."""
    
    def test_find_nearest_single_annotation(self):
        """Test finding nearest when only one annotation exists."""
        annotations = [MockKeypoint(100, 100)]
        result = HitTester.find_nearest(annotations, 0, 0, radius=200)
        
        assert result is not None
        assert result[0].annotation_id == "test_1"
        # Distance should be sqrt(100^2 + 100^2) ≈ 141.4
        assert 141 < result[1] < 142
    
    def test_find_nearest_empty_list(self):
        """Test finding nearest in empty annotation list."""
        result = HitTester.find_nearest([], 10, 10)
        assert result is None
    
    def test_find_nearest_respects_radius(self):
        """Test that find_nearest respects the radius parameter."""
        annotations = [
            MockKeypoint(100, 100, annotation_id="a1"),
            MockKeypoint(200, 200, annotation_id="a2"),
        ]
        
        # With small radius, should find nothing
        result = HitTester.find_nearest(annotations, 0, 0, radius=50)
        assert result is None
        
        # With larger radius, should find nearest
        result = HitTester.find_nearest(annotations, 110, 110, radius=20)
        assert result is not None
        assert result[0].annotation_id == "a1"
    
    def test_find_all_within_sorted_by_distance(self):
        """Test that find_all_within returns results sorted by distance."""
        annotations = [
            MockKeypoint(100, 100, annotation_id="a1"),
            MockKeypoint(50, 50, annotation_id="a2"),
            MockKeypoint(150, 150, annotation_id="a3"),
        ]
        
        results = HitTester.find_all_within(annotations, 0, 0, radius=220)
        
        # Should be sorted by distance
        assert len(results) == 3
        assert results[0][0].annotation_id == "a2"  # Closest
        assert results[1][0].annotation_id == "a1"  # Middle
        assert results[2][0].annotation_id == "a3"  # Farthest
        
        # Verify distances are increasing
        assert results[0][1] < results[1][1] < results[2][1]
    
    def test_hit_test_box(self):
        """Test rectangular region hit testing."""
        annotations = [
            MockKeypoint(50, 50, annotation_id="a1"),
            MockKeypoint(100, 100, annotation_id="a2"),
            MockKeypoint(150, 150, annotation_id="a3"),
        ]
        
        # Query a box that includes a2
        results = HitTester.hit_test_box(annotations, 90, 90, 110, 110)
        
        assert len(results) == 1
        assert results[0].annotation_id == "a2"
    
    def test_hit_test_circle(self):
        """Test circular region hit testing."""
        annotations = [
            MockKeypoint(100, 100, annotation_id="a1"),
            MockKeypoint(105, 105, annotation_id="a2"),  # ~7 pixels away
            MockKeypoint(120, 120, annotation_id="a3"),  # ~28 pixels away
        ]
        
        # Query circle with radius 10
        results = HitTester.hit_test_circle(annotations, 100, 100, radius=10)
        
        # Should include only a1 and a2
        assert len(results) == 2
        assert all(a.annotation_id in ["a1", "a2"] for a in results)


class TestLocalMaxSnapper:
    """Tests for local maximum snapping."""
    
    def test_snap_to_local_max_simple_peak(self):
        """Test snapping to a simple local maximum."""
        # Create synthetic image with a peak at (5, 5)
        image = np.zeros((10, 10), dtype=np.float32)
        image[4:7, 4:7] = [[1, 2, 1], [2, 10, 2], [1, 2, 1]]
        
        new_x, new_y = LocalMaxSnapper.snap_to_local_max(image, 4.0, 4.0, search_radius=5)
        
        # Should snap close to (5, 5)
        assert 4 < new_x < 6
        assert 4 < new_y < 6
    
    def test_snap_to_centroid_weighted(self):
        """Test snapping to intensity-weighted centroid."""
        # Create Gaussian-like peak
        image = np.zeros((10, 10), dtype=np.float32)
        image[4:7, 4:7] = [[1, 2, 1], [2, 10, 2], [1, 2, 1]]
        
        cx, cy = LocalMaxSnapper.snap_to_centroid(image, 5.0, 5.0, search_radius=5)
        
        # Centroid should be near center of mass
        assert isinstance(cx, float)
        assert isinstance(cy, float)
        assert 3 < cx < 7
        assert 3 < cy < 7
    
    def test_snap_outside_bounds_unchanged(self):
        """Test that snap returns original point if outside image bounds."""
        image = np.zeros((10, 10))
        
        # Point way outside
        new_x, new_y = LocalMaxSnapper.snap_to_local_max(image, -100, -100, search_radius=5)
        
        # Should return clipped but otherwise original
        assert isinstance(new_x, float)
        assert isinstance(new_y, float)
    
    def test_snap_with_threshold(self):
        """Test snapping with intensity threshold."""
        image = np.array([
            [1, 1, 1],
            [1, 100, 1],
            [1, 1, 1],
        ], dtype=np.float32)
        
        # Snap with high threshold - should ignore peak
        cx, cy = LocalMaxSnapper.snap_to_centroid(image, 1.0, 1.0, search_radius=2, threshold=200)
        
        # With threshold above peak, should return original or center
        assert isinstance(cx, float)
        assert isinstance(cy, float)


class TestContextCommands:
    """Tests for context annotation commands."""
    
    def test_mark_uncertain_command_execute(self):
        """Test marking annotation as uncertain."""
        mock_controller = MagicMock()
        mock_ann = MockKeypoint(100, 100, annotation_id="test_ann")
        mock_controller.session_state.annotations = {0: [mock_ann]}
        mock_controller.session_state.dirty = False
        
        cmd = MarkUncertainCommand(mock_controller, 0, 100, 100, radius=50)
        assert cmd.execute()
        
        # Check annotation is marked uncertain
        assert mock_ann.meta.get("uncertain") is True
        assert mock_controller.session_state.dirty is True
    
    def test_mark_uncertain_command_undo(self):
        """Test undo of mark uncertain command."""
        mock_controller = MagicMock()
        mock_ann = MockKeypoint(100, 100, annotation_id="test_ann")
        mock_ann.meta["uncertain"] = False
        mock_controller.session_state.annotations = {0: [mock_ann]}
        mock_controller.session_state.dirty = False
        
        cmd = MarkUncertainCommand(mock_controller, 0, 100, 100, radius=50)
        assert cmd.execute()
        assert mock_ann.meta.get("uncertain") is True
        
        # Undo
        assert cmd.undo()
        assert mock_ann.meta.get("uncertain") is False
    
    def test_mark_uncertain_no_nearby_annotation(self):
        """Test mark uncertain when no annotation is nearby."""
        mock_controller = MagicMock()
        mock_ann = MockKeypoint(200, 200, annotation_id="test_ann")
        mock_controller.session_state.annotations = {0: [mock_ann]}
        
        # Query far away
        cmd = MarkUncertainCommand(mock_controller, 0, 0, 0, radius=50)
        assert not cmd.execute()  # Should fail
    
    def test_snap_to_local_max_command_undo_redo(self):
        """Test undo/redo for snap to local max."""
        mock_controller = MagicMock()
        mock_ann = MockKeypoint(100, 100, annotation_id="test_ann")
        mock_controller.session_state.annotations = {0: [mock_ann]}
        mock_controller.session_state.dirty = False
        
        cmd = SnapToLocalMaxCommand(mock_controller, 0, 100, 100, radius=50, search_radius=10)
        assert cmd.execute()
        
        original_pos = (mock_ann.x, mock_ann.y)
        
        # Undo
        assert cmd.undo()
        assert (mock_ann.x, mock_ann.y) == original_pos
        
        # Redo (position might change if snapping was effective)
        assert cmd.redo()


class TestContextCommandTransactions:
    """Tests for transaction behavior with context commands."""
    
    def test_context_commands_in_transaction(self):
        """Test grouping context commands in a transaction."""
        from phage_annotator.session.commands import TransactionCommand
        
        mock_controller = MagicMock()
        anns = [
            MockKeypoint(100, 100, annotation_id="a1"),
            MockKeypoint(110, 110, annotation_id="a2"),
        ]
        mock_controller.session_state.annotations = {0: anns}
        mock_controller.session_state.dirty = False
        
        # Create transaction with multiple context commands
        txn = TransactionCommand(mock_controller, 0, "Context Actions")
        txn.add_command(MarkUncertainCommand(mock_controller, 0, 100, 100, radius=50))
        txn.add_command(MarkUncertainCommand(mock_controller, 0, 110, 110, radius=50))
        
        # Execute transaction
        assert txn.execute()
        
        # Both should be marked
        assert anns[0].meta.get("uncertain") is True
        assert anns[1].meta.get("uncertain") is True

    def test_transaction_undo_redo_for_bulk_context_updates(self):
        """Bulk context transaction should undo and redo as one item."""
        from phage_annotator.session.commands import TransactionCommand

        anns = [
            MockKeypoint(100, 100, annotation_id="a1"),
            MockKeypoint(120, 120, annotation_id="a2"),
        ]
        harness = _ContextCommandHarness(anns)
        txn = TransactionCommand(harness, 0, "Bulk uncertain update")
        txn.add_command(MarkUncertainCommand(harness, 0, 100, 100, radius=40))
        txn.add_command(MarkUncertainCommand(harness, 0, 120, 120, radius=40))

        assert txn.execute()
        assert anns[0].meta.get("uncertain") is True
        assert anns[1].meta.get("uncertain") is True

        assert txn.undo()
        assert anns[0].meta.get("uncertain") is False
        assert anns[1].meta.get("uncertain") is False

        assert txn.redo()
        assert anns[0].meta.get("uncertain") is True
        assert anns[1].meta.get("uncertain") is True
    
    def test_context_action_hit_test_accuracy(self):
        """Test accuracy of hit testing in context action scenarios."""
        # Create realistic annotation set
        annotations = [
            MockKeypoint(100, 100, annotation_id="target"),
            MockKeypoint(115, 115, annotation_id="nearby"),
            MockKeypoint(50, 50, annotation_id="far"),
        ]
        
        # Click near the target
        result = HitTester.find_nearest(annotations, 103, 103, radius=10)
        
        assert result is not None
        assert result[0].annotation_id == "target"
        assert result[1] < 5
    
    def test_context_action_with_snap_accuracy(self):
        """Test snap accuracy with realistic image data."""
        # Create image with clear peak
        image = np.zeros((20, 20), dtype=np.float32)
        # Place peak at (10, 10)
        for i in range(8, 13):
            for j in range(8, 13):
                image[i, j] = 10.0 - abs(i - 10) - abs(j - 10)
        
        # Start snap from nearby position
        new_x, new_y = LocalMaxSnapper.snap_to_local_max(
            image, 9.0, 9.0, search_radius=3
        )
        
        # Should snap closer to peak at (10, 10)
        dist_before = abs(9.0 - 10.0) + abs(9.0 - 10.0)
        dist_after = abs(new_x - 10.0) + abs(new_y - 10.0)
        assert dist_after <= dist_before


class TestDeleteNearestCommand:
    """Tests for delete nearest annotation command."""
    
    def test_delete_nearest_command_execute(self):
        """Test deleting nearest annotation."""
        mock_controller = MagicMock()
        ann = MockKeypoint(100, 100, annotation_id="to_delete")
        mock_controller.session_state.annotations = {0: [ann]}
        
        cmd = DeleteNearestCommand(mock_controller, 0, 100, 100, radius=50)
        assert cmd.execute()
        
        # Annotation should be stored for potential undo
        assert cmd.deleted_annotation_id == "to_delete"
        assert cmd.deleted_annotation_data is not None
    
    def test_delete_nearest_no_annotations(self):
        """Test delete when no annotations exist."""
        mock_controller = MagicMock()
        mock_controller.session_state.annotations = {0: []}
        
        cmd = DeleteNearestCommand(mock_controller, 0, 0, 0, radius=50)
        assert not cmd.execute()
    
    def test_delete_nearest_out_of_radius(self):
        """Test delete when target is out of radius."""
        mock_controller = MagicMock()
        ann = MockKeypoint(200, 200)
        mock_controller.session_state.annotations = {0: [ann]}
        
        # Query far away with small radius
        cmd = DeleteNearestCommand(mock_controller, 0, 0, 0, radius=10)
        assert not cmd.execute()


class TestContextCommandStackRoundTrip:
    """Controller stack round-trip tests for context commands."""

    def test_delete_command_stack_undo_redo(self):
        """Delete command should survive serialized undo/redo reconstruction."""
        anns = [MockKeypoint(100, 100, annotation_id="a1")]
        harness = _ContextCommandHarness(anns)

        cmd = DeleteNearestCommand(harness, 0, 100, 100, radius=10)
        assert harness.execute_view_command(cmd)
        assert len(harness.session_state.annotations[0]) == 0

        assert harness.undo()
        assert len(harness.session_state.annotations[0]) == 1
        assert harness.session_state.annotations[0][0].annotation_id == "a1"

        assert harness.redo()
        assert len(harness.session_state.annotations[0]) == 0

    def test_edit_metadata_command_stack_undo_redo(self):
        """Metadata edit command should restore old/new metadata and label."""
        anns = [MockKeypoint(100, 100, label="old", annotation_id="a1")]
        anns[0].meta["uncertain"] = False
        harness = _ContextCommandHarness(anns)

        cmd = EditNearestMetadataCommand(
            harness,
            0,
            x=100,
            y=100,
            radius=10,
            annotation_id="a1",
            new_label="new",
            new_meta={"uncertain": True, "comment": "updated"},
        )
        assert harness.execute_view_command(cmd)
        assert anns[0].label == "new"
        assert anns[0].meta["uncertain"] is True

        assert harness.undo()
        assert anns[0].label == "old"
        assert anns[0].meta["uncertain"] is False

        assert harness.redo()
        assert anns[0].label == "new"
        assert anns[0].meta["uncertain"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
