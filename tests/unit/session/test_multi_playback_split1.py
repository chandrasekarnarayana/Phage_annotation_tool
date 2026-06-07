"""Split definitions from test_multi_playback.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.multi_playback import (
    PlaybackMode,
    ModalityPlaybackState,
    ModalityPlaybackManager,
)


@pytest.fixture
def playback_manager(qtbot):
    """Create a ModalityPlaybackManager for testing."""
    manager = ModalityPlaybackManager()
    # ModalityPlaybackManager is QObject, not QWidget, so don't use addWidget
    return manager

class TestPlaybackMode:
    """Test PlaybackMode enum."""
    
    def test_playback_modes_defined(self):
        """Verify all playback modes exist."""
        assert hasattr(PlaybackMode, 'SYNCHRONIZED')
        assert hasattr(PlaybackMode, 'INDEPENDENT')
        assert hasattr(PlaybackMode, 'SEQUENTIAL')
    
    def test_playback_mode_values(self):
        """Verify playback mode string values."""
        assert PlaybackMode.SYNCHRONIZED.value == "synchronized"
        assert PlaybackMode.INDEPENDENT.value == "independent"
        assert PlaybackMode.SEQUENTIAL.value == "sequential"

class TestModalityPlaybackState:
    """Test ModalityPlaybackState dataclass."""
    
    def test_state_initialization(self):
        """Test creating playback state."""
        state = ModalityPlaybackState(
            modality_idx=0,
            current_frame=5,
            is_playing=True,
            frame_count=100,
            fps=15.0,
            loop=False
        )
        
        assert state.modality_idx == 0
        assert state.current_frame == 5
        assert state.is_playing is True
        assert state.frame_count == 100
        assert state.fps == 15.0
        assert state.loop is False
    
    def test_advance_frame_normal(self):
        """Test advancing frame within range."""
        state = ModalityPlaybackState(modality_idx=0, frame_count=10)
        state.current_frame = 5
        
        advanced = state.advance_frame()
        assert advanced is True
        assert state.current_frame == 6
    
    def test_advance_frame_at_end_with_loop(self):
        """Test advancing frame at end with loop enabled."""
        state = ModalityPlaybackState(modality_idx=0, frame_count=10, loop=True)
        state.current_frame = 9
        
        advanced = state.advance_frame()
        assert advanced is True
        assert state.current_frame == 0  # Wrapped to start
    
    def test_advance_frame_at_end_without_loop(self):
        """Test advancing frame at end without loop."""
        state = ModalityPlaybackState(modality_idx=0, frame_count=10, loop=False)
        state.current_frame = 9
        state.is_playing = True
        
        advanced = state.advance_frame()
        assert advanced is False
        assert state.is_playing is False  # Auto-stopped
    
    def test_reset(self):
        """Test resetting playback to frame 0."""
        state = ModalityPlaybackState(modality_idx=0, frame_count=100)
        state.current_frame = 50
        
        state.reset()
        assert state.current_frame == 0
