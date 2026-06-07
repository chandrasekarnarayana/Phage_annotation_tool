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


@pytest.fixture
def mock_controller():
    """Create a mock SessionController."""
    class MockViewState:
        def __init__(self):
            """Initialize the object and prepare its runtime state."""
            self.t = 0
            self.z = 0
    
    class MockController:
        def __init__(self):
            """Initialize the object and prepare its runtime state."""
            self.session_state = None
            self.view_state = MockViewState()
        
        def set_t(self, t_index):
            """Set t for the current workflow."""
            if self.view_state:
                self.view_state.t = t_index
        
        def set_z(self, z_index):
            """Set z for the current workflow."""
            if self.view_state:
                self.view_state.z = z_index
    
    return MockController()

@pytest.fixture
def mock_session():
    """Create a mock SessionState."""
    class MockSessionState:
        def __init__(self):
            """Initialize the object and prepare its runtime state."""
            self.images = []
    
    return MockSessionState()
