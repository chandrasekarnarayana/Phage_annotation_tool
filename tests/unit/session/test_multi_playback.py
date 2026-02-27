"""Tests for multi-modality playback synchronization."""

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


class TestModalityPlaybackManager:
    """Test ModalityPlaybackManager class."""
    
    def test_initialization(self, playback_manager):
        """Test manager initializes correctly."""
        assert playback_manager._mode == PlaybackMode.INDEPENDENT
        assert len(playback_manager._states) == 0
        assert playback_manager._timer is not None
    
    def test_register_modality(self, playback_manager):
        """Test registering a modality."""
        playback_manager.register_modality(0, "TIRF", frame_count=100, fps=10.0)
        
        assert 0 in playback_manager._states
        state = playback_manager._states[0]
        assert state.modality_idx == 0
        assert state.frame_count == 100
        assert state.fps == 10.0
    
    def test_register_multiple_modalities(self, playback_manager):
        """Test registering multiple modalities."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 150)
        playback_manager.register_modality(2, "Brightfield", 80)
        
        assert len(playback_manager._states) == 3
        assert playback_manager._states[0].frame_count == 100
        assert playback_manager._states[1].frame_count == 150
        assert playback_manager._states[2].frame_count == 80
    
    def test_unregister_modality(self, playback_manager):
        """Test unregistering a modality."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        
        playback_manager.unregister_modality(0)
        
        assert 0 not in playback_manager._states
        assert 1 in playback_manager._states
    
    def test_set_mode(self, playback_manager, qtbot):
        """Test setting playback mode."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        with qtbot.waitSignal(playback_manager.mode_changed, timeout=1000) as blocker:
            playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        
        assert playback_manager._mode == PlaybackMode.SYNCHRONIZED
        assert blocker.args == ["synchronized"]
    
    def test_set_mode_no_redundant_emit(self, playback_manager):
        """Test setting same mode doesn't emit signal."""
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        # Setting same mode again shouldn't do anything
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        # Just verify no exception raised
    
    def test_start_playback_independent(self, playback_manager, qtbot):
        """Test starting independent playback."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        
        with qtbot.waitSignal(playback_manager.playback_started, timeout=1000) as blocker:
            playback_manager.start_playback(0)
        
        assert blocker.args == [0]
        assert playback_manager._states[0].is_playing is True
    
    def test_start_playback_synchronized(self, playback_manager, qtbot):
        """Test starting synchronized playback starts all."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        
        playback_manager.start_playback()
        
        assert playback_manager._states[0].is_playing is True
        assert playback_manager._states[1].is_playing is True
    
    def test_stop_playback(self, playback_manager, qtbot):
        """Test stopping playback."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.start_playback(0)
        
        with qtbot.waitSignal(playback_manager.playback_stopped, timeout=1000) as blocker:
            playback_manager.stop_playback(0)
        
        assert blocker.args == [0]
        assert playback_manager._states[0].is_playing is False
    
    def test_stop_all_playback(self, playback_manager):
        """Test stopping all modalities."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        playback_manager.start_playback()
        
        playback_manager.stop_playback()  # None = stop all
        
        assert playback_manager._states[0].is_playing is False
        assert playback_manager._states[1].is_playing is False
    
    def test_toggle_playback(self, playback_manager):
        """Test toggling playback on/off."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        playback_manager.toggle_playback(0)
        assert playback_manager._states[0].is_playing is True
        
        playback_manager.toggle_playback(0)
        assert playback_manager._states[0].is_playing is False
    
    def test_set_frame(self, playback_manager, qtbot):
        """Test setting current frame."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        with qtbot.waitSignal(playback_manager.frame_changed, timeout=1000) as blocker:
            playback_manager.set_frame(0, 50)
        
        assert blocker.args == [0, 50]
        assert playback_manager._states[0].current_frame == 50
    
    def test_set_frame_clamps(self, playback_manager):
        """Test set_frame clamps to valid range."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        # Beyond end
        playback_manager.set_frame(0, 200)
        assert playback_manager._states[0].current_frame == 99
        
        # Before start
        playback_manager.set_frame(0, -10)
        assert playback_manager._states[0].current_frame == 0
    
    def test_get_frame(self, playback_manager):
        """Test getting current frame."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.set_frame(0, 42)
        
        frame = playback_manager.get_frame(0)
        assert frame == 42
    
    def test_get_frame_nonexistent(self, playback_manager):
        """Test getting frame for non-existent modality."""
        frame = playback_manager.get_frame(999)
        assert frame is None
    
    def test_is_playing(self, playback_manager):
        """Test checking if modality is playing."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        assert playback_manager.is_playing(0) is False
        
        playback_manager.start_playback(0)
        assert playback_manager.is_playing(0) is True
    
    def test_set_fps(self, playback_manager):
        """Test setting FPS."""
        playback_manager.register_modality(0, "TIRF", 100, fps=10.0)
        
        playback_manager.set_fps(0, 20.0)
        assert playback_manager._states[0].fps == 20.0
    
    def test_set_fps_clamps_minimum(self, playback_manager):
        """Test FPS has minimum value."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        playback_manager.set_fps(0, 0.01)
        assert playback_manager._states[0].fps >= 0.1  # Minimum enforced
    
    def test_set_loop(self, playback_manager):
        """Test setting loop mode."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        playback_manager.set_loop(0, False)
        assert playback_manager._states[0].loop is False
        
        playback_manager.set_loop(0, True)
        assert playback_manager._states[0].loop is True
    
    def test_reset_all(self, playback_manager):
        """Test resetting all modalities."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        
        playback_manager.set_frame(0, 50)
        playback_manager.set_frame(1, 75)
        
        playback_manager.reset_all()
        
        assert playback_manager._states[0].current_frame == 0
        assert playback_manager._states[1].current_frame == 0
    
    def test_get_state(self, playback_manager):
        """Test getting playback state."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        state = playback_manager.get_state(0)
        assert state is not None
        assert state.modality_idx == 0
    
    def test_get_state_nonexistent(self, playback_manager):
        """Test getting state for non-existent modality."""
        state = playback_manager.get_state(999)
        assert state is None
    
    def test_mode_property(self, playback_manager):
        """Test mode property accessor."""
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        assert playback_manager.mode == PlaybackMode.SYNCHRONIZED


class TestPlaybackIntegration:
    """Integration tests for playback manager."""
    
    def test_synchronized_playback_advances_together(self, playback_manager, qtbot):
        """Test synchronized mode advances all modalities together."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        
        playback_manager.start_playback()
        
        # Simulate timer tick
        playback_manager._on_timer_tick()
        
        # Both should advance
        assert playback_manager._states[0].current_frame == 1
        assert playback_manager._states[1].current_frame == 1
    
    def test_independent_playback_advances_separately(self, playback_manager):
        """Test independent mode advances modalities separately."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        
        playback_manager.start_playback(0)
        # Don't start modality 1
        
        playback_manager._on_timer_tick()
        
        # Only 0 should advance
        assert playback_manager._states[0].current_frame == 1
        assert playback_manager._states[1].current_frame == 0
    
    def test_sequential_playback_order(self, playback_manager):
        """Test sequential mode plays modalities in order."""
        # Create modalities with loop=False for testing
        playback_manager.register_modality(0, "TIRF", 5)
        playback_manager.register_modality(1, "Confocal", 5)
        playback_manager.set_mode(PlaybackMode.SEQUENTIAL)
        
        # Disable loop so it moves to next modality
        playback_manager.set_loop(0, False)
        playback_manager.set_loop(1, False)
        
        playback_manager.start_playback()
        
        # Should start with first modality
        assert playback_manager._states[0].is_playing is True
        assert playback_manager._states[1].is_playing is False
        
        # Advance through all frames of first modality
        for _ in range(5):
            playback_manager._on_timer_tick()
        
        # Should move to second modality
        assert playback_manager._states[0].is_playing is False
        assert playback_manager._states[1].is_playing is True
    
    def test_frame_changed_signal(self, playback_manager, qtbot):
        """Test frame_changed signal emission."""
        playback_manager.register_modality(0, "TIRF", 100)
        
        with qtbot.waitSignal(playback_manager.frame_changed, timeout=1000) as blocker:
            playback_manager.set_frame(0, 25)
        
        assert blocker.args == [0, 25]
    
    def test_mode_changed_signal(self, playback_manager, qtbot):
        """Test mode_changed signal emission."""
        with qtbot.waitSignal(playback_manager.mode_changed, timeout=1000) as blocker:
            playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        
        assert blocker.args == ["synchronized"]
