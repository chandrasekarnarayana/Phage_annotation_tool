"""Split definitions from test_multi_playback.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.multi_playback import (
    PlaybackMode,
    ModalityPlaybackState,
    ModalityPlaybackManager,
)


from tests.unit.session.test_multi_playback_split1 import playback_manager

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

    def test_empty_sync_group_does_not_fallback_to_all_modalities(self, playback_manager):
        """An explicitly empty selected group should not start playback on every modality."""
        playback_manager.register_modality(0, "TIRF", 100)
        playback_manager.register_modality(1, "Confocal", 100)
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        playback_manager.set_sync_group(set())

        playback_manager.start_playback()

        assert playback_manager._states[0].is_playing is False
        assert playback_manager._states[1].is_playing is False
    
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
