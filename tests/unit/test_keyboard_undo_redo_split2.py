"""Split definitions from test_keyboard_undo_redo.py."""


import pytest
from typing import List
from unittest.mock import MagicMock, Mock

from phage_annotator.session.navigation_commands import (
    JumpToFrameCommand,
    JumpToZCommand,
)
from phage_annotator.session.commands import TransactionCommand

# Skip keyboard shortcut tests if Qt not available
try:
    from phage_annotator.ui_qt.keyboard_shortcuts import (
        KeyboardShortcutManager,
        ShortcutDefinition,
        ShortcutContext,
        ShortcutConflict,
    )
    _has_qt = True
except ImportError:
    _has_qt = False


from tests.unit.test_keyboard_undo_redo_split3 import mock_controller, mock_session

class TestShortcutConflictDetection:
    """Tests for shortcut conflict detection."""
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_detect_global_conflicts(self):
        """Test that global context shortcuts conflict."""
        manager = KeyboardShortcutManager()
        
        s1 = ShortcutDefinition(
            id="test.global1",
            category="test",
            description="Global 1",
            default_sequence="Ctrl+X",
            context=ShortcutContext.GLOBAL,
        )
        
        s2 = ShortcutDefinition(
            id="test.global2",
            category="test",
            description="Global 2",
            default_sequence="Ctrl+X",
            context=ShortcutContext.GLOBAL,
        )
        
        manager.register_shortcut(s1)
        manager.register_shortcut(s2)
        
        conflicts = manager.detect_conflicts()
        assert len(conflicts) > 0
        # Check for conflict in either order
        assert any(
            (c.shortcut_a.id == "test.global1" and c.shortcut_b.id == "test.global2") or
            (c.shortcut_a.id == "test.global2" and c.shortcut_b.id == "test.global1")
            for c in conflicts
        )
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_editing_browsing_no_conflict(self):
        """Test that editing and browsing context shortcuts don't conflict."""
        manager = KeyboardShortcutManager()
        
        s1 = ShortcutDefinition(
            id="test.edit",
            category="test",
            description="Editing action",
            default_sequence="Ctrl+E",
            context=ShortcutContext.EDITING,
        )
        
        s2 = ShortcutDefinition(
            id="test.browse",
            category="test",
            description="Browsing action",
            default_sequence="Ctrl+E",
            context=ShortcutContext.BROWSING,
        )
        
        manager.register_shortcut(s1)
        manager.register_shortcut(s2)
        
        # Should be no conflict (mutually exclusive contexts)
        conflicts = manager.detect_conflicts()
        editing_browsing_conflicts = [
            c for c in conflicts
            if {c.shortcut_a.id, c.shortcut_b.id} == {"test.edit", "test.browse"}
        ]
        assert len(editing_browsing_conflicts) == 0
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_text_input_no_conflict(self):
        """Test that text input context shortcuts don't conflict."""
        manager = KeyboardShortcutManager()
        
        s1 = ShortcutDefinition(
            id="test.global",
            category="test",
            description="Global action",
            default_sequence="Ctrl+A",
            context=ShortcutContext.GLOBAL,
        )
        
        s2 = ShortcutDefinition(
            id="test.text",
            category="test",
            description="Text input",
            default_sequence="Ctrl+A",
            context=ShortcutContext.TEXT_INPUT,
        )
        
        manager.register_shortcut(s1)
        manager.register_shortcut(s2)
        
        # Should be no conflict (text input disables all others)
        conflicts = manager.detect_conflicts()
        text_conflicts = [
            c for c in conflicts
            if {c.shortcut_a.id, c.shortcut_b.id} == {"test.global", "test.text"}
        ]
        assert len(text_conflicts) == 0
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_same_context_conflicts(self):
        """Test that same-context shortcuts conflict when sharing sequence."""
        manager = KeyboardShortcutManager()
        
        s1 = ShortcutDefinition(
            id="test.mod1",
            category="test",
            description="Modality 1",
            default_sequence="Ctrl+M",
            context=ShortcutContext.MODALITY_VIEW,
        )
        
        s2 = ShortcutDefinition(
            id="test.mod2",
            category="test",
            description="Modality 2",
            default_sequence="Ctrl+M",
            context=ShortcutContext.MODALITY_VIEW,
        )
        
        manager.register_shortcut(s1)
        manager.register_shortcut(s2)
        
        conflicts = manager.detect_conflicts()
        assert len(conflicts) > 0
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_disabled_shortcuts_no_conflict(self):
        """Test that disabled shortcuts don't register conflicts."""
        manager = KeyboardShortcutManager()
        
        s1 = ShortcutDefinition(
            id="test.disabled",
            category="test",
            description="Disabled",
            default_sequence="Ctrl+D",
            enabled=False,
        )
        
        s2 = ShortcutDefinition(
            id="test.enabled",
            category="test",
            description="Enabled",
            default_sequence="Ctrl+D",
            enabled=True,
        )
        
        manager.register_shortcut(s1)
        manager.register_shortcut(s2)
        
        # No conflict because s1 is disabled
        conflicts = manager.detect_conflicts()
        assert len(conflicts) == 0

class TestTransactionCommand:
    """Tests for TransactionCommand."""
    
    def test_empty_transaction(self, mock_controller):
        """Test transaction with no commands."""
        txn = TransactionCommand(mock_controller, 0, "Empty Transaction")
        assert txn.execute()
    
    def test_single_command_transaction(self, mock_controller, mock_session):
        """Test transaction with a single command."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 0
        
        txn = TransactionCommand(mock_controller, 0, "Jump Transaction")
        txn.add_command(JumpToFrameCommand(mock_controller, 0, target_t=5))
        
        assert txn.execute()
        assert mock_controller.view_state.t == 5
    
    def test_multiple_commands_transaction(self, mock_controller, mock_session):
        """Test transaction with multiple commands."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 0
        mock_controller.view_state.z = 0
        
        txn = TransactionCommand(mock_controller, 0, "Multi-step Navigation")
        txn.add_command(JumpToFrameCommand(mock_controller, 0, target_t=7))
        txn.add_command(JumpToZCommand(mock_controller, 0, target_z=2))
        
        assert txn.execute()
        assert mock_controller.view_state.t == 7
        assert mock_controller.view_state.z == 2
    
    def test_transaction_undo_all(self, mock_controller, mock_session):
        """Test that transaction undo reverses all commands."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 1
        mock_controller.view_state.z = 1
        
        txn = TransactionCommand(mock_controller, 0, "Multi-step Navigation")
        txn.add_command(JumpToFrameCommand(mock_controller, 0, target_t=7))
        txn.add_command(JumpToZCommand(mock_controller, 0, target_z=3))
        
        assert txn.execute()
        assert mock_controller.view_state.t == 7
        assert mock_controller.view_state.z == 3
        
        # Undo
        assert txn.undo()
        assert mock_controller.view_state.t == 1
        assert mock_controller.view_state.z == 1
    
    def test_transaction_redo_all(self, mock_controller, mock_session):
        """Test that transaction redo restores all commands."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 1
        mock_controller.view_state.z = 1
        
        txn = TransactionCommand(mock_controller, 0, "Multi-step Navigation")
        txn.add_command(JumpToFrameCommand(mock_controller, 0, target_t=7))
        txn.add_command(JumpToZCommand(mock_controller, 0, target_z=3))
        
        assert txn.execute()
        assert txn.undo()
        assert txn.redo()
        
        assert mock_controller.view_state.t == 7
        assert mock_controller.view_state.z == 3
    
    def test_cannot_add_after_execution(self, mock_controller):
        """Test that adding commands after execution raises error."""
        txn = TransactionCommand(mock_controller, 0, "Test")
        assert txn.execute()
        
        with pytest.raises(RuntimeError):
            txn.add_command(JumpToFrameCommand(mock_controller, 0, target_t=1))
    
    def test_transaction_mementos(self, mock_controller, mock_session):
        """Test that transaction creates proper mementos."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 0
        
        txn = TransactionCommand(mock_controller, 0, "Test Transaction")
        txn.add_command(JumpToFrameCommand(mock_controller, 0, target_t=5))
        
        assert txn.execute()
        
        assert txn.memento_before is not None
        assert txn.memento_after is not None
        assert txn.memento_before.command_type == "transaction"
        assert txn.memento_after.command_type == "transaction"
        assert txn.memento_before.data["name"] == "Test Transaction"
