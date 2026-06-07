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
