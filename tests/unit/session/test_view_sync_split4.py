"""Split definitions from test_view_sync.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.view_sync import (
    ViewState,
    ViewSyncManager,
)


from tests.unit.session.test_view_sync_split1 import sync_manager

class TestCombinedSliceSynchronization:
    """Test combinations of T and Z slice synchronization."""
    
    def test_set_slice_indices(self, sync_manager):
        """Test setting both T and Z indices together."""
        sync_manager.register_modality(0)
        sync_manager.set_slice_indices(0, 5, 3)
        
        assert sync_manager._states[0].t_index == 5
        assert sync_manager._states[0].z_index == 3
    
    def test_slice_indices_sync_together(self, sync_manager):
        """Test T and Z sync together."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_t_sync(True)
        sync_manager.enable_z_sync(True)
        
        sync_manager.set_slice_indices(0, 7, 4)
        
        assert sync_manager._states[1].t_index == 7
        assert sync_manager._states[1].z_index == 4
    
    def test_t_sync_without_z_sync(self, sync_manager):
        """Test T sync independent of Z sync."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.set_z_index(0, 5)
        sync_manager.set_z_index(1, 3)
        
        sync_manager.enable_t_sync(True)
        sync_manager.set_t_index(0, 10)
        
        # T should sync, Z should not
        assert sync_manager._states[1].t_index == 10
        assert sync_manager._states[1].z_index == 3
    
    def test_z_sync_without_t_sync(self, sync_manager):
        """Test Z sync independent of T sync."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.set_t_index(0, 5)
        sync_manager.set_t_index(1, 2)
        
        sync_manager.enable_z_sync(True)
        sync_manager.set_z_index(0, 8)
        
        # Z should sync, T should not
        assert sync_manager._states[1].z_index == 8
        assert sync_manager._states[1].t_index == 2
    
    def test_view_changed_signal_includes_slices(self, sync_manager, qtbot):
        """Test view_changed signal includes T and Z indices."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.view_changed, timeout=1000) as blocker:
            sync_manager.set_slice_indices(0, 10, 5)
        
        # Signal should have 6 args: idx, zoom, pan_x, pan_y, t_idx, z_idx
        assert len(blocker.args) == 6
        assert blocker.args == [0, 1.0, 0.0, 0.0, 10, 5]
    
    def test_reset_view_resets_slices(self, sync_manager):
        """Test reset_view resets T and Z indices."""
        sync_manager.register_modality(0)
        sync_manager.set_slice_indices(0, 15, 10)
        
        sync_manager.reset_view(0)
        
        assert sync_manager._states[0].t_index == 0
        assert sync_manager._states[0].z_index == 0

class TestCropRectangleSynchronization:
    """Test crop rectangle synchronization across modalities."""
    
    def test_crop_rect_initialization(self, sync_manager):
        """Test crop rect initializes as None."""
        sync_manager.register_modality(0)
        
        assert sync_manager._states[0].crop_rect is None
    
    def test_set_crop_rect_without_sync(self, sync_manager):
        """Test setting crop rect without sync enabled."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        crop_rect = (10.0, 20.0, 100.0, 150.0)
        sync_manager.set_crop_rect(0, crop_rect)
        
        assert sync_manager._states[0].crop_rect == crop_rect
        assert sync_manager._states[1].crop_rect is None
    
    def test_enable_crop_sync(self, sync_manager, qtbot):
        """Test enabling crop synchronization."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.crop_sync_changed, timeout=1000) as blocker:
            sync_manager.enable_crop_sync(True)
        
        assert blocker.args == [True]
        assert sync_manager.crop_sync_enabled is True
    
    def test_disable_crop_sync(self, sync_manager, qtbot):
        """Test disabling crop synchronization."""
        sync_manager.register_modality(0)
        sync_manager.enable_crop_sync(True)
        
        with qtbot.waitSignal(sync_manager.crop_sync_changed, timeout=1000) as blocker:
            sync_manager.enable_crop_sync(False)
        
        assert blocker.args == [False]
        assert sync_manager.crop_sync_enabled is False
    
    def test_crop_rect_sync_all_modalities(self, sync_manager):
        """Test crop rect syncs to all modalities."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        sync_manager.enable_crop_sync(True)
        
        crop_rect = (5.0, 15.0, 200.0, 250.0)
        sync_manager.set_crop_rect(0, crop_rect)
        
        assert sync_manager._states[0].crop_rect == crop_rect
        assert sync_manager._states[1].crop_rect == crop_rect
        assert sync_manager._states[2].crop_rect == crop_rect
    
    def test_crop_rect_changed_signal(self, sync_manager, qtbot):
        """Test crop_changed signal emitted."""
        sync_manager.register_modality(0)
        
        crop_rect = (10.0, 20.0, 100.0, 150.0)
        with qtbot.waitSignal(sync_manager.crop_changed, timeout=1000) as blocker:
            sync_manager.set_crop_rect(0, crop_rect)
        
        assert blocker.args[0] == 0  # modality_idx
        assert blocker.args[1] == crop_rect
    
    def test_crop_sync_with_multiple_modalities(self, sync_manager):
        """Test crop sync propagates to all modalities."""
        for i in range(4):
            sync_manager.register_modality(i)
        
        sync_manager.enable_crop_sync(True)
        
        crop_rect = (25.0, 35.0, 300.0, 400.0)
        sync_manager.set_crop_rect(1, crop_rect)
        
        for i in range(4):
            assert sync_manager._states[i].crop_rect == crop_rect
    
    def test_clear_crop_rect_with_sync(self, sync_manager):
        """Test clearing crop rect syncs to all modalities."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_crop_sync(True)
        
        # First set a crop rect
        crop_rect = (10.0, 20.0, 100.0, 150.0)
        sync_manager.set_crop_rect(0, crop_rect)
        assert sync_manager._states[1].crop_rect == crop_rect
        
        # Then clear it
        sync_manager.set_crop_rect(0, None)
        assert sync_manager._states[0].crop_rect is None
        assert sync_manager._states[1].crop_rect is None
    
    def test_crop_sync_with_different_values(self, sync_manager, qtbot):
        """Test switching between different crop rectangles with sync."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_crop_sync(True)
        
        # Set first crop rect
        crop1 = (10.0, 10.0, 100.0, 100.0)
        sync_manager.set_crop_rect(0, crop1)
        assert sync_manager._states[1].crop_rect == crop1
        
        # Switch to different crop rect
        crop2 = (20.0, 30.0, 200.0, 300.0)
        sync_manager.set_crop_rect(1, crop2)
        
        # Both should have the new crop rect
        assert sync_manager._states[0].crop_rect == crop2
        assert sync_manager._states[1].crop_rect == crop2
    
    def test_enable_crop_sync_propagates_existing(self, sync_manager):
        """Test enabling crop sync propagates existing crop rect."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        # Set crop on modality 0 before enabling sync
        crop_rect = (15.0, 25.0, 150.0, 200.0)
        sync_manager.set_crop_rect(0, crop_rect)
        assert sync_manager._states[1].crop_rect is None
        
        # Enable sync - should propagate existing crop from mod 0
        sync_manager.enable_crop_sync(True)
        
        # Note: Implementation finds first non-None crop_rect
        assert sync_manager._states[0].crop_rect == crop_rect
        assert sync_manager._states[1].crop_rect == crop_rect
