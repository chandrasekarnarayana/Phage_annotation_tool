"""Split definitions from test_view_sync.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.view_sync import (
    ViewState,
    ViewSyncManager,
)


from tests.unit.session.test_view_sync_split1 import sync_manager

class TestCropWithLinkGroups:
    """Test crop synchronization with link groups."""
    
    def test_crop_sync_respects_link_groups(self, sync_manager):
        """Test crop sync only applies within link groups."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        sync_manager.register_modality(3)
        
        # Create link group for modalities 0 and 1
        group_id = sync_manager.create_link_group({0, 1})
        
        sync_manager.enable_crop_sync(True)
        
        crop_rect = (10.0, 10.0, 100.0, 100.0)
        sync_manager.set_crop_rect(0, crop_rect)
        
        # Should sync within group
        assert sync_manager._states[0].crop_rect == crop_rect
        assert sync_manager._states[1].crop_rect == crop_rect
        
        # Should NOT sync outside group
        assert sync_manager._states[2].crop_rect is None
        assert sync_manager._states[3].crop_rect is None
    
    def test_multiple_link_groups_independent_crops(self, sync_manager):
        """Test multiple link groups can have different crops."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        sync_manager.register_modality(3)
        
        # Create two groups
        group1 = sync_manager.create_link_group({0, 1})
        group2 = sync_manager.create_link_group({2, 3})
        
        sync_manager.enable_crop_sync(True)
        
        # Set different crops for each group
        crop1 = (10.0, 10.0, 100.0, 100.0)
        crop2 = (20.0, 20.0, 200.0, 200.0)
        
        sync_manager.set_crop_rect(0, crop1)
        sync_manager.set_crop_rect(2, crop2)
        
        # Group 1 should have crop1
        assert sync_manager._states[0].crop_rect == crop1
        assert sync_manager._states[1].crop_rect == crop1
        
        # Group 2 should have crop2
        assert sync_manager._states[2].crop_rect == crop2
        assert sync_manager._states[3].crop_rect == crop2
    
    def test_crop_independent_without_groups(self, sync_manager):
        """Test crop can be independent for modalities not in groups."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        # Create link group for 0 and 1, leave 2 independent
        group_id = sync_manager.create_link_group({0, 1})
        
        sync_manager.enable_crop_sync(True)
        
        crop1 = (10.0, 10.0, 100.0, 100.0)
        sync_manager.set_crop_rect(0, crop1)
        
        # Modalities in group should sync
        assert sync_manager._states[1].crop_rect == crop1

class TestCropAndSliceSync:
    """Test crop and slice synchronization working together."""
    
    def test_crop_and_t_sync_independent(self, sync_manager):
        """Test crop and T slice sync operate independently."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_crop_sync(True)
        sync_manager.enable_t_sync(True)
        
        crop_rect = (10.0, 20.0, 100.0, 150.0)
        sync_manager.set_crop_rect(0, crop_rect)
        sync_manager.set_t_index(0, 5)
        
        # Both should sync
        assert sync_manager._states[1].crop_rect == crop_rect
        assert sync_manager._states[1].t_index == 5
    
    def test_crop_and_z_sync_independent(self, sync_manager):
        """Test crop and Z slice sync operate independently."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_crop_sync(True)
        sync_manager.enable_z_sync(True)
        
        crop_rect = (5.0, 15.0, 50.0, 75.0)
        sync_manager.set_crop_rect(0, crop_rect)
        sync_manager.set_z_index(0, 8)
        
        # Both should sync
        assert sync_manager._states[1].crop_rect == crop_rect
        assert sync_manager._states[1].z_index == 8
    
    def test_all_sync_types_together(self, sync_manager):
        """Test zoom, pan, slice, and crop sync all together."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        # Enable all sync types
        sync_manager.enable_zoom_sync(True)
        sync_manager.enable_pan_sync(True)
        sync_manager.enable_t_sync(True)
        sync_manager.enable_z_sync(True)
        sync_manager.enable_crop_sync(True)
        
        # Update modality 0
        crop_rect = (10.0, 20.0, 100.0, 150.0)
        sync_manager.set_zoom(0, 2.5)
        sync_manager.set_pan(0, 50.0, 75.0)
        sync_manager.set_slice_indices(0, 5, 3)
        sync_manager.set_crop_rect(0, crop_rect)
        
        # Check all synced to modality 1
        state1 = sync_manager._states[1]
        assert state1.zoom_level == 2.5
        assert state1.pan_x == 50.0
        assert state1.pan_y == 75.0
        assert state1.t_index == 5
        assert state1.z_index == 3
        assert state1.crop_rect == crop_rect
    
    def test_crop_preserved_during_slice_changes(self, sync_manager):
        """Test crop rect preserved when slices change."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_crop_sync(True)
        sync_manager.enable_t_sync(True)
        
        crop_rect = (10.0, 20.0, 100.0, 150.0)
        sync_manager.set_crop_rect(0, crop_rect)
        sync_manager.set_t_index(0, 5)
        
        # Change T index again
        sync_manager.set_t_index(0, 10)
        
        # Crop should still be there
        assert sync_manager._states[1].crop_rect == crop_rect
        assert sync_manager._states[1].t_index == 10
