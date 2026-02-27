"""Tests for per-modality FPS control widget."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore, QtWidgets

from phage_annotator.ui_qt.widgets.modality_fps_control import ModalityFpsControl
from phage_annotator.session.multi_playback import ModalityPlaybackManager


@pytest.fixture
def fps_control(qtbot):
    """Create a ModalityFpsControl for testing."""
    widget = ModalityFpsControl()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def playback_manager():
    """Create a ModalityPlaybackManager for testing."""
    manager = ModalityPlaybackManager()
    manager.register_modality(0, "TIRF", frame_count=100, fps=10.0)
    manager.register_modality(1, "Confocal", frame_count=100, fps=20.0)
    return manager


class TestModalityFpsControl:
    """Test ModalityFpsControl widget."""
    
    def test_initialization(self, fps_control):
        """Test FPS control initializes correctly."""
        assert fps_control.fps_spinbox.value() == 10.0
        assert fps_control._current_modality_idx is None
        assert len(fps_control._modality_fps) == 0
    
    def test_fps_spinbox_bounds(self, fps_control):
        """Test FPS spinbox has correct bounds."""
        assert fps_control.fps_spinbox.minimum() == 0.1
        assert fps_control.fps_spinbox.maximum() == 120.0
    
    def test_set_active_modality_updates_spinbox(self, fps_control):
        """Test setting active modality updates spinbox."""
        fps_control.set_active_modality(0, "TIRF")
        
        assert fps_control._current_modality_idx == 0
        assert fps_control.fps_spinbox.value() == 10.0
        assert "TIRF" in fps_control.label.text()
    
    def test_set_active_modality_with_custom_fps(self, fps_control):
        """Test setting active modality with custom FPS."""
        fps_control.set_fps(0, 25.0)
        fps_control.set_active_modality(0, "TIRF")
        
        assert fps_control.fps_spinbox.value() == 25.0
    
    def test_fps_changed_signal(self, fps_control, qtbot):
        """Test fps_changed signal emitted when spinbox changes."""
        fps_control.set_active_modality(0, "TIRF")
        
        with qtbot.waitSignal(fps_control.fps_changed, timeout=1000) as blocker:
            fps_control.fps_spinbox.setValue(15.0)
        
        assert blocker.args == [0, 15.0]
    
    def test_fps_changed_stores_value(self, fps_control):
        """Test FPS value is stored when changed."""
        fps_control.set_active_modality(0, "TIRF")
        fps_control.fps_spinbox.setValue(30.0)
        
        assert fps_control._modality_fps[0] == 30.0
    
    def test_switch_between_modalities(self, fps_control):
        """Test switching between modalities updates UI."""
        fps_control.set_fps(0, 15.0)
        fps_control.set_fps(1, 25.0)
        
        # Switch to modality 0
        fps_control.set_active_modality(0, "TIRF")
        assert fps_control.fps_spinbox.value() == 15.0
        
        # Switch to modality 1
        fps_control.set_active_modality(1, "Confocal")
        assert fps_control.fps_spinbox.value() == 25.0
    
    def test_register_modality(self, fps_control):
        """Test registering modality with initial FPS."""
        fps_control.register_modality(0, fps=12.0)
        
        assert fps_control._modality_fps[0] == 12.0
    
    def test_get_fps(self, fps_control):
        """Test getting stored FPS value."""
        fps_control.set_fps(0, 18.0)
        
        assert fps_control.get_fps(0) == 18.0
    
    def test_get_fps_default(self, fps_control):
        """Test getting default FPS for unregistered modality."""
        assert fps_control.get_fps(99) == 10.0
    
    def test_reset_fps_button(self, fps_control):
        """Test reset button restores default FPS."""
        fps_control.set_active_modality(0, "TIRF")
        fps_control.fps_spinbox.setValue(50.0)
        
        fps_control.reset_btn.click()
        
        assert fps_control.fps_spinbox.value() == 10.0
    
    def test_fps_clamping_minimum(self, fps_control):
        """Test FPS is clamped to minimum value."""
        fps_control.set_active_modality(0, "TIRF")
        fps_control.fps_spinbox.setValue(0.05)  # Below minimum
        
        # Spinbox should clamp it
        assert fps_control.fps_spinbox.value() == 0.1
    
    def test_fps_clamping_maximum(self, fps_control):
        """Test FPS is clamped to maximum value."""
        fps_control.set_active_modality(0, "TIRF")
        fps_control.fps_spinbox.setValue(150.0)  # Above maximum
        
        # Spinbox should clamp it
        assert fps_control.fps_spinbox.value() == 120.0
    
    def test_set_playback_manager(self, fps_control, playback_manager):
        """Test setting playback manager reference."""
        fps_control.set_playback_manager(playback_manager)
        
        assert fps_control._playback_manager is playback_manager
    
    def test_fps_update_with_playback_manager(self, fps_control, playback_manager):
        """Test FPS updates playback manager when changed."""
        fps_control.set_playback_manager(playback_manager)
        fps_control.set_active_modality(0, "TIRF")
        
        fps_control.fps_spinbox.setValue(22.0)
        
        # Check manager was updated
        state = playback_manager.get_state(0)
        assert state.fps == 22.0
    
    def test_set_active_modality_reads_from_manager(self, fps_control, playback_manager):
        """Test set_active_modality reads FPS from manager."""
        fps_control.set_playback_manager(playback_manager)
        
        # Modality 1 was registered with fps=20.0
        fps_control.set_active_modality(1, "Confocal")
        
        assert fps_control.fps_spinbox.value() == 20.0


class TestModalityFpsIntegration:
    """Integration tests for FPS control with playback manager."""
    
    def test_multiple_modalities_independent_fps(self, fps_control, playback_manager):
        """Test each modality can have independent FPS values."""
        fps_control.set_playback_manager(playback_manager)
        
        # Register and set different FPS values
        for idx in range(3):
            fps_control.register_modality(idx, fps=10.0 + idx * 5)
        
        for idx in range(3):
            expected = 10.0 + idx * 5
            assert fps_control.get_fps(idx) == expected
    
    def test_fps_changes_persisted_across_switches(self, fps_control, playback_manager):
        """Test FPS values persist when switching modalities."""
        fps_control.set_playback_manager(playback_manager)
        
        # Set different FPS for each modality
        fps_control.register_modality(0, fps=10.0)
        fps_control.register_modality(1, fps=25.0)
        fps_control.register_modality(2, fps=15.0)
        
        # Switch and verify values persist
        fps_control.set_active_modality(0, "M0")
        fps_control.fps_spinbox.setValue(12.0)
        
        fps_control.set_active_modality(1, "M1")
        fps_control.set_active_modality(0, "M0")
        
        # Original modification should persist
        assert fps_control.fps_spinbox.value() == 12.0
    
    def test_fps_control_with_synchronized_playback(self, fps_control, playback_manager):
        """Test FPS works with synchronized playback mode."""
        from phage_annotator.session.multi_playback import PlaybackMode
        
        fps_control.set_playback_manager(playback_manager)
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        
        # Set different FPS for modalities
        fps_control.set_fps(0, 20.0)
        fps_control.set_fps(1, 15.0)
        
        # In synchronized mode, fastest FPS should be used
        playback_manager.start_playback(0)
        assert playback_manager._timer.interval() == int(1000 / 20.0)
        playback_manager.stop_playback()
    
    def test_fps_control_with_independent_playback(self, fps_control, playback_manager):
        """Test FPS works with independent playback mode."""
        from phage_annotator.session.multi_playback import PlaybackMode
        
        fps_control.set_playback_manager(playback_manager)
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        
        # Set FPS for modality
        fps_control.set_fps(0, 18.0)
        fps_control.set_active_modality(0, "TIRF")
        
        # In independent mode, modality's FPS should be used
        playback_manager.start_playback(0)
        assert playback_manager._timer.interval() == int(1000 / 18.0)
        playback_manager.stop_playback()
