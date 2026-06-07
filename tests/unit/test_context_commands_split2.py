"""Split definitions from test_context_commands.py."""


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


from tests.unit.test_context_commands_split1 import MockKeypoint, _ContextCommandHarness

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
