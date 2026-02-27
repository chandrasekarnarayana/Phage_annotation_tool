"""Tests for playback state persistence (serialization/deserialization)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("PyQt5.sip")

from phage_annotator.session.view_sync import ViewSyncManager
from phage_annotator.session.multi_playback import ModalityPlaybackManager, PlaybackMode


@pytest.fixture
def view_sync_manager():
    """Create a ViewSyncManager for testing."""
    manager = ViewSyncManager()
    manager.register_modality(0)
    manager.register_modality(1)
    manager.register_modality(2)
    return manager


@pytest.fixture
def playback_manager():
    """Create a ModalityPlaybackManager for testing."""
    manager = ModalityPlaybackManager()
    manager.register_modality(0, "TIRF", frame_count=100, fps=10.0)
    manager.register_modality(1, "Confocal", frame_count=150, fps=15.0)
    manager.register_modality(2, "DIC", frame_count=120, fps=12.0)
    return manager


class TestViewSyncSerialization:
    """Test view sync manager serialization/deserialization."""
    
    def test_empty_manager_serialization(self, view_sync_manager):
        """Test serializing empty manager."""
        data = view_sync_manager.to_dict()
        
        assert data["zoom_sync_enabled"] is False
        assert data["pan_sync_enabled"] is False
        assert data["t_sync_enabled"] is False
        assert data["z_sync_enabled"] is False
        assert data["crop_sync_enabled"] is False
        assert data["view_states"] == {
            "0": {"zoom_level": 1.0, "pan_x": 0.0, "pan_y": 0.0, "t_index": 0, "z_index": 0, "crop_rect": None},
            "1": {"zoom_level": 1.0, "pan_x": 0.0, "pan_y": 0.0, "t_index": 0, "z_index": 0, "crop_rect": None},
            "2": {"zoom_level": 1.0, "pan_x": 0.0, "pan_y": 0.0, "t_index": 0, "z_index": 0, "crop_rect": None},
        }
    
    def test_roundtrip_sync_flags(self, view_sync_manager):
        """Test sync flags persist through serialization."""
        view_sync_manager.enable_zoom_sync(True)
        view_sync_manager.enable_pan_sync(True)
        view_sync_manager.enable_t_sync(True)
        view_sync_manager.enable_z_sync(True)
        view_sync_manager.enable_crop_sync(True)
        
        data = view_sync_manager.to_dict()
        
        # Create new manager and restore
        restored = ViewSyncManager()
        restored.register_modality(0)
        restored.register_modality(1)
        restored.register_modality(2)
        restored.from_dict(data)
        
        assert restored.zoom_sync_enabled is True
        assert restored.pan_sync_enabled is True
        assert restored.t_sync_enabled is True
        assert restored.z_sync_enabled is True
        assert restored.crop_sync_enabled is True
    
    def test_roundtrip_view_states(self, view_sync_manager):
        """Test view state values persist through serialization."""
        view_sync_manager.set_zoom(0, 2.5)
        view_sync_manager.set_pan(1, 100.0, 50.0)
        view_sync_manager.set_slice_indices(2, 10, 5)
        view_sync_manager.set_crop_rect(0, (10.0, 20.0, 100.0, 150.0))
        
        data = view_sync_manager.to_dict()
        
        # Create new manager and restore
        restored = ViewSyncManager()
        restored.register_modality(0)
        restored.register_modality(1)
        restored.register_modality(2)
        restored.from_dict(data)
        
        assert restored.get_view_state(0).zoom_level == 2.5
        assert restored.get_view_state(1).pan_x == 100.0
        assert restored.get_view_state(1).pan_y == 50.0
        assert restored.get_view_state(2).t_index == 10
        assert restored.get_view_state(2).z_index == 5
        assert restored.get_view_state(0).crop_rect == (10.0, 20.0, 100.0, 150.0)
    
    def test_roundtrip_link_groups(self, view_sync_manager):
        """Test link groups persist through serialization."""
        view_sync_manager.create_link_group({0, 1})
        view_sync_manager.create_link_group({2})
        
        data = view_sync_manager.to_dict()
        
        # Create new manager and restore
        restored = ViewSyncManager()
        restored.register_modality(0)
        restored.register_modality(1)
        restored.register_modality(2)
        restored.from_dict(data)
        
        # Verify groups were restored
        assert 0 in restored._modality_to_group
        assert 1 in restored._modality_to_group
        assert 2 in restored._modality_to_group
        
        # Verify group assignments
        group_0 = restored._modality_to_group[0]
        group_1 = restored._modality_to_group[1]
        group_2 = restored._modality_to_group[2]
        
        assert group_0 == group_1  # 0 and 1 in same group
        assert group_2 != group_0  # 2 in different group
    
    def test_crop_rect_none_serialization(self, view_sync_manager):
        """Test None crop_rect is preserved."""
        view_sync_manager.set_crop_rect(0, None)
        view_sync_manager.set_crop_rect(1, (10.0, 20.0, 100.0, 150.0))
        
        data = view_sync_manager.to_dict()
        
        assert data["view_states"]["0"]["crop_rect"] is None
        # Crop rect can be tuple or list from serialization
        assert data["view_states"]["1"]["crop_rect"] == (10.0, 20.0, 100.0, 150.0) or \
               data["view_states"]["1"]["crop_rect"] == [10.0, 20.0, 100.0, 150.0]


class TestPlaybackSerialization:
    """Test playback manager serialization/deserialization."""
    
    def test_fps_serialization(self, playback_manager):
        """Test FPS values persist through serialization."""
        playback_manager.set_fps(0, 20.0)
        playback_manager.set_fps(1, 25.0)
        playback_manager.set_fps(2, 15.0)
        
        data = playback_manager.to_dict()
        
        # Verify FPS in serialized data
        assert data["modality_states"]["0"]["fps"] == 20.0
        assert data["modality_states"]["1"]["fps"] == 25.0
        assert data["modality_states"]["2"]["fps"] == 15.0
    
    def test_loop_state_serialization(self, playback_manager):
        """Test loop settings persist through serialization."""
        playback_manager.set_loop(0, False)
        playback_manager.set_loop(1, True)
        
        data = playback_manager.to_dict()
        
        assert data["modality_states"]["0"]["loop"] is False
        assert data["modality_states"]["1"]["loop"] is True
    
    def test_mode_serialization(self, playback_manager):
        """Test playback mode persists through serialization."""
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        
        data = playback_manager.to_dict()
        assert data["mode"] == "synchronized"
        
        # Test INDEPENDENT
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        data = playback_manager.to_dict()
        assert data["mode"] == "independent"
        
        # Test SEQUENTIAL
        playback_manager.set_mode(PlaybackMode.SEQUENTIAL)
        data = playback_manager.to_dict()
        assert data["mode"] == "sequential"
    
    def test_roundtrip_playback_state(self, playback_manager):
        """Test complete playback state roundtrip."""
        # Set various states
        playback_manager.set_mode(PlaybackMode.SYNCHRONIZED)
        playback_manager.set_fps(0, 18.0)
        playback_manager.set_fps(1, 22.0)
        playback_manager.set_loop(0, False)
        playback_manager.set_sync_group({0, 1})
        
        data = playback_manager.to_dict()
        
        # Create new manager and restore
        restored = ModalityPlaybackManager()
        restored.register_modality(0, "TIRF", frame_count=100)
        restored.register_modality(1, "Confocal", frame_count=150)
        restored.register_modality(2, "DIC", frame_count=120)
        restored.from_dict(data)
        
        # Verify restoration
        assert restored.mode == PlaybackMode.SYNCHRONIZED
        assert restored.get_state(0).fps == 18.0
        assert restored.get_state(1).fps == 22.0
        assert restored.get_state(0).loop is False
        assert restored._sync_group == {0, 1}
    
    def test_sync_group_serialization(self, playback_manager):
        """Test sync group persists through serialization."""
        playback_manager.set_sync_group({0, 2})
        
        data = playback_manager.to_dict()
        assert set(data["sync_group"]) == {0, 2}
    
    def test_none_sync_group_serialization(self, playback_manager):
        """Test None sync group is preserved."""
        playback_manager.set_sync_group(None)
        
        data = playback_manager.to_dict()
        assert data["sync_group"] is None


class TestIntegratedStatePersistence:
    """Integration tests for combined view and playback persistence."""
    
    def test_full_system_roundtrip(self, view_sync_manager, playback_manager):
        """Test saving and restoring complete multi-modality state."""
        # Configure view sync
        view_sync_manager.enable_zoom_sync(True)
        view_sync_manager.enable_crop_sync(True)
        view_sync_manager.set_zoom(0, 2.5)
        view_sync_manager.set_crop_rect(1, (10.0, 20.0, 100.0, 150.0))
        view_sync_manager.set_slice_indices(2, 8, 3)
        
        # Configure playback
        playback_manager.set_mode(PlaybackMode.INDEPENDENT)
        playback_manager.set_fps(0, 20.0)
        playback_manager.set_fps(1, 25.0)
        playback_manager.set_loop(0, False)
        
        # Serialize
        view_data = view_sync_manager.to_dict()
        playback_data = playback_manager.to_dict()
        
        # Create new managers and restore
        restored_view = ViewSyncManager()
        restored_view.register_modality(0)
        restored_view.register_modality(1)
        restored_view.register_modality(2)
        restored_view.from_dict(view_data)
        
        restored_playback = ModalityPlaybackManager()
        restored_playback.register_modality(0, "TIRF", frame_count=100)
        restored_playback.register_modality(1, "Confocal", frame_count=150)
        restored_playback.register_modality(2, "DIC", frame_count=120)
        restored_playback.from_dict(playback_data)
        
        # Verify view sync restoration
        assert restored_view.zoom_sync_enabled is True
        assert restored_view.crop_sync_enabled is True
        assert restored_view.get_view_state(0).zoom_level == 2.5
        assert restored_view.get_view_state(1).crop_rect == (10.0, 20.0, 100.0, 150.0)
        assert restored_view.get_view_state(2).t_index == 8
        assert restored_view.get_view_state(2).z_index == 3
        
        # Verify playback restoration
        assert restored_playback.mode == PlaybackMode.INDEPENDENT
        assert restored_playback.get_state(0).fps == 20.0
        assert restored_playback.get_state(1).fps == 25.0
        assert restored_playback.get_state(0).loop is False
    
    def test_missing_data_handling(self, view_sync_manager, playback_manager):
        """Test graceful handling of missing or malformed data."""
        # Empty view manager, minimal data
        empty_data = {}
        view_sync_manager.from_dict(empty_data)
        # Should not crash, use defaults
        
        # Minimal playback data
        minimal_data = {"mode": "synchronized"}
        playback_manager.from_dict(minimal_data)
        # Should not crash, mode restored
        assert playback_manager.mode == PlaybackMode.SYNCHRONIZED
    
    def test_partial_state_restoration(self, view_sync_manager):
        """Test restoring only partial state."""
        # Original
        view_sync_manager.set_zoom(0, 1.5)
        view_sync_manager.set_zoom(1, 2.0)
        
        # Serialize only modality 0
        data = view_sync_manager.to_dict()
        
        # Create new manager with missing modality
        partial = ViewSyncManager()
        partial.register_modality(0)  # Only 0, missing 1 and 2
        partial.from_dict(data)
        
        # Should restore what it can
        assert partial.get_view_state(0).zoom_level == 1.5
