"""Split definitions from test_view_sync.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.view_sync import (
    ViewState,
    ViewSyncManager,
)


@pytest.fixture
def sync_manager():
    """Create a ViewSyncManager for testing."""
    manager = ViewSyncManager()
    return manager

class TestViewState:
    """Test ViewState dataclass."""
    
    def test_view_state_initialization(self):
        """Test creating view state."""
        state = ViewState(
            modality_idx=0,
            zoom_level=2.0,
            pan_x=100.0,
            pan_y=50.0
        )
        
        assert state.modality_idx == 0
        assert state.zoom_level == 2.0
        assert state.pan_x == 100.0
        assert state.pan_y == 50.0
    
    def test_view_state_clone(self):
        """Test cloning view state."""
        state = ViewState(modality_idx=0, zoom_level=1.5, pan_x=10, pan_y=20)
        cloned = state.clone()
        
        assert cloned.modality_idx == state.modality_idx
        assert cloned.zoom_level == state.zoom_level
        assert cloned.pan_x == state.pan_x
        assert cloned.pan_y == state.pan_y
        assert cloned is not state  # Deep copy
