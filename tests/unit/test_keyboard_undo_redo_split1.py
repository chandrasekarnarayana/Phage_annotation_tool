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

class TestJumpToFrameCommand:
    """Tests for JumpToFrameCommand."""
    
    def test_jump_to_frame_executes_successfully(self, mock_controller, mock_session):
        """Test that jump-to-frame command executes and updates T index."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 0
        
        cmd = JumpToFrameCommand(mock_controller, 0, target_t=5)
        assert cmd.execute()
        assert mock_controller.view_state.t == 5
    
    def test_jump_to_frame_out_of_bounds_fails(self, mock_controller, mock_session):
        """Test that jumping to out-of-bounds frame fails."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 0
        
        cmd = JumpToFrameCommand(mock_controller, 0, target_t=20)
        assert not cmd.execute()  # Target T=20 but max is 10
    
    def test_jump_to_frame_undo_redo(self, mock_controller, mock_session):
        """Test undo/redo for jump-to-frame."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.t = 2
        
        cmd = JumpToFrameCommand(mock_controller, 0, target_t=7)
        assert cmd.execute()
        assert mock_controller.view_state.t == 7
        
        # Undo
        assert cmd.undo()
        assert mock_controller.view_state.t == 2
        
        # Redo
        assert cmd.redo()
        assert mock_controller.view_state.t == 7
    
    def test_jump_to_frame_negative_index_fails(self, mock_controller, mock_session):
        """Test that negative frame index fails."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        
        cmd = JumpToFrameCommand(mock_controller, 0, target_t=-1)
        assert not cmd.execute()

class TestJumpToZCommand:
    """Tests for JumpToZCommand."""
    
    def test_jump_to_z_executes_successfully(self, mock_controller, mock_session):
        """Test that jump-to-z command executes and updates Z index."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.z = 0
        
        cmd = JumpToZCommand(mock_controller, 0, target_z=3)
        assert cmd.execute()
        assert mock_controller.view_state.z == 3
    
    def test_jump_to_z_out_of_bounds_fails(self, mock_controller, mock_session):
        """Test that jumping to out-of-bounds Z fails."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.z = 0
        
        cmd = JumpToZCommand(mock_controller, 0, target_z=10)
        assert not cmd.execute()  # Target Z=10 but max is 5
    
    def test_jump_to_z_undo_redo(self, mock_controller, mock_session):
        """Test undo/redo for jump-to-z."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 5, 512, 512)})()]
        mock_controller.view_state.z = 1
        
        cmd = JumpToZCommand(mock_controller, 0, target_z=4)
        assert cmd.execute()
        assert mock_controller.view_state.z == 4
        
        # Undo
        assert cmd.undo()
        assert mock_controller.view_state.z == 1
        
        # Redo
        assert cmd.redo()
        assert mock_controller.view_state.z == 4
    
    def test_jump_to_z_single_z_stack(self, mock_controller, mock_session):
        """Test jump-to-z on single-Z stack fails for any non-zero index."""
        mock_controller.session_state = mock_session
        mock_controller.session_state.images = [type('Image', (), {'shape': (10, 1, 512, 512)})()]
        mock_controller.view_state.z = 0
        
        # Z=0 should work
        cmd = JumpToZCommand(mock_controller, 0, target_z=0)
        assert cmd.execute()
        
        # Z=1 should fail
        cmd2 = JumpToZCommand(mock_controller, 0, target_z=1)
        assert not cmd2.execute()

class TestKeyboardShortcutManager:
    """Tests for KeyboardShortcutManager."""
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_register_and_retrieve_shortcut(self):
        """Test basic shortcut registration and retrieval."""
        manager = KeyboardShortcutManager()
        
        # Manager should have defaults
        assert len(manager.get_all_shortcuts()) > 0
        
        # Retrieve existing shortcut
        shortcut = manager.get_shortcut("nav.jump_to_frame")
        assert shortcut is not None
        assert shortcut.description == "Jump to frame (T)"
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_register_custom_shortcut(self):
        """Test registering a custom shortcut."""
        manager = KeyboardShortcutManager()
        
        custom = ShortcutDefinition(
            id="custom.test",
            category="test",
            description="Test shortcut",
            default_sequence="Ctrl+T",
        )
        
        assert manager.register_shortcut(custom)
        assert manager.get_shortcut("custom.test") == custom
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_cannot_register_duplicate_without_override(self):
        """Test that duplicate IDs are rejected without override."""
        manager = KeyboardShortcutManager()
        
        custom = ShortcutDefinition(
            id="custom.test",
            category="test",
            description="Test",
            default_sequence="Ctrl+T",
        )
        
        manager.register_shortcut(custom)
        
        # Try to register again without override
        assert not manager.register_shortcut(custom)
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_override_existing_shortcut(self):
        """Test overriding an existing shortcut."""
        manager = KeyboardShortcutManager()
        
        original = manager.get_shortcut("nav.jump_to_frame")
        assert original.default_sequence == "Ctrl+G"
        
        modified = ShortcutDefinition(
            id="nav.jump_to_frame",
            category="navigation",
            description="Jump to frame (T)",
            default_sequence="F5",
        )
        
        assert manager.register_shortcut(modified, override=True)
        assert manager.get_shortcut("nav.jump_to_frame").default_sequence == "F5"
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_unregister_shortcut(self):
        """Test unregistering a shortcut."""
        manager = KeyboardShortcutManager()
        
        custom = ShortcutDefinition(
            id="custom.removeme",
            category="test",
            description="Removable",
            default_sequence="Ctrl+R",
        )
        
        manager.register_shortcut(custom)
        assert manager.get_shortcut("custom.removeme") is not None
        
        assert manager.unregister_shortcut("custom.removeme")
        assert manager.get_shortcut("custom.removeme") is None
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_get_shortcuts_by_category(self):
        """Test retrieving shortcuts by category."""
        manager = KeyboardShortcutManager()
        
        nav_shortcuts = manager.get_shortcuts_by_category("navigation")
        assert len(nav_shortcuts) > 0
        assert all(s.category == "navigation" for s in nav_shortcuts)
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_get_shortcuts_for_sequence(self):
        """Test finding shortcuts by key sequence."""
        manager = KeyboardShortcutManager()
        
        shortcuts = manager.get_shortcuts_for_sequence("Ctrl+G")
        assert len(shortcuts) > 0
        assert any(s.id == "nav.jump_to_frame" for s in shortcuts)
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_all_sequences_includes_alternatives(self):
        """Test that all_sequences includes primary and alternatives."""
        shortcut = ShortcutDefinition(
            id="test.multi",
            category="test",
            description="Multi-sequence",
            default_sequence="Ctrl+A",
            alternative_sequences=["Ctrl+B", "Ctrl+C"],
        )
        
        all_seqs = shortcut.all_sequences()
        assert "Ctrl+A" in all_seqs
        assert "Ctrl+B" in all_seqs
        assert "Ctrl+C" in all_seqs
        assert len(all_seqs) == 3
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_shortcut_equality_by_id(self):
        """Test that shortcuts are equal if they have same ID."""
        s1 = ShortcutDefinition(
            id="test.eq",
            category="test",
            description="First",
            default_sequence="Ctrl+A",
        )
        
        s2 = ShortcutDefinition(
            id="test.eq",
            category="different",
            description="Different",
            default_sequence="Ctrl+B",
        )
        
        assert s1 == s2  # Same ID means equal
    
    @pytest.mark.skipif(not _has_qt, reason="Qt not available")
    def test_context_disabling(self):
        """Test context enable/disable."""
        manager = KeyboardShortcutManager()
        
        assert manager.is_context_active(ShortcutContext.EDITING)
        
        manager.set_context_disabled(ShortcutContext.EDITING, disabled=True)
        assert not manager.is_context_active(ShortcutContext.EDITING)
        
        manager.set_context_disabled(ShortcutContext.EDITING, disabled=False)
        assert manager.is_context_active(ShortcutContext.EDITING)
