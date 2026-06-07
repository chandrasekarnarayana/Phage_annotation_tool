"""Split definitions from test_view_sync.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.view_sync import (
    ViewState,
    ViewSyncManager,
)


from tests.unit.session.test_view_sync_split1 import sync_manager

class TestViewSyncIntegration:
    """Integration tests for view synchronization."""
    
    def test_enable_zoom_sync_synchronizes_existing(self, sync_manager):
        """Test enabling zoom sync synchronizes current states."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        # Set different zooms
        sync_manager.set_zoom(0, 2.0)
        sync_manager.set_zoom(1, 1.5)
        
        # Enable sync - should sync all to first modality
        sync_manager.enable_zoom_sync(True)
        
        assert sync_manager._states[0].zoom_level == 2.0
        assert sync_manager._states[1].zoom_level == 2.0
    
    def test_enable_pan_sync_synchronizes_existing(self, sync_manager):
        """Test enabling pan sync synchronizes current states."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        # Set different pans
        sync_manager.set_pan(0, 100.0, 50.0)
        sync_manager.set_pan(1, 200.0, 150.0)
        
        # Enable sync - should sync all to first modality
        sync_manager.enable_pan_sync(True)
        
        assert sync_manager._states[0].pan_x == 100.0
        assert sync_manager._states[1].pan_x == 100.0
    
    def test_view_changed_signal(self, sync_manager, qtbot):
        """Test view_changed signal emission."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.view_changed, timeout=1000) as blocker:
            sync_manager.set_zoom(0, 1.5)
        
        assert blocker.args == [0, 1.5, 0.0, 0.0, 0, 0]
    
    def test_no_recursive_updates(self, sync_manager):
        """Test manager prevents recursive update loops."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_zoom_sync(True)
        
        # This should not cause infinite loop
        sync_manager.set_zoom(0, 2.0)
        
        # Both should be updated
        assert sync_manager._states[0].zoom_level == 2.0
        assert sync_manager._states[1].zoom_level == 2.0

class TestTSliceSynchronization:
    """Test T (time) slice index synchronization."""
    
    def test_t_index_initialization(self, sync_manager):
        """Test T index initializes to 0."""
        sync_manager.register_modality(0)
        assert sync_manager._states[0].t_index == 0
    
    def test_set_t_index(self, sync_manager):
        """Test setting T index on single modality."""
        sync_manager.register_modality(0)
        sync_manager.set_t_index(0, 10)
        assert sync_manager._states[0].t_index == 10
    
    def test_t_sync_disabled_no_propagation(self, sync_manager):
        """Test T changes don't propagate when sync disabled."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.set_t_index(0, 5)
        # Modality 1 should not change
        assert sync_manager._states[1].t_index == 0
    
    def test_enable_t_sync(self, sync_manager):
        """Test enabling T sync."""
        assert sync_manager.t_sync_enabled is False
        sync_manager.enable_t_sync(True)
        assert sync_manager.t_sync_enabled is True
    
    def test_enable_t_sync_synchronizes_all(self, sync_manager):
        """Test enabling T sync synchronizes all modalities."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        sync_manager.set_t_index(0, 15)
        sync_manager.enable_t_sync(True)
        
        # All should be synced to first
        assert sync_manager._states[1].t_index == 15
        assert sync_manager._states[2].t_index == 15
    
    def test_t_sync_propagates_changes(self, sync_manager):
        """Test T changes propagate when sync enabled."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_t_sync(True)
        sync_manager.set_t_index(0, 20)
        
        assert sync_manager._states[0].t_index == 20
        assert sync_manager._states[1].t_index == 20
    
    def test_t_sync_signal_emission(self, sync_manager, qtbot):
        """Test t_sync_changed signal."""
        with qtbot.waitSignal(sync_manager.t_sync_changed, timeout=1000) as blocker:
            sync_manager.enable_t_sync(True)
        assert blocker.args == [True]
    
    def test_negative_t_index_clamped(self, sync_manager):
        """Test negative T index clamped to 0."""
        sync_manager.register_modality(0)
        sync_manager.set_t_index(0, -5)
        assert sync_manager._states[0].t_index == 0
    
    def test_t_index_in_link_group(self, sync_manager):
        """Test T sync within link group."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        group_id = sync_manager.create_link_group({0, 1})
        
        # Set different T indices
        sync_manager.set_t_index(0, 5)
        sync_manager.set_t_index(2, 10)
        
        # Change in group should only affect group members
        sync_manager.set_t_index(0, 8)
        
        assert sync_manager._states[0].t_index == 8
        assert sync_manager._states[1].t_index == 8
        assert sync_manager._states[2].t_index == 10  # Not in group

class TestZSliceSynchronization:
    """Test Z (depth) slice index synchronization."""
    
    def test_z_index_initialization(self, sync_manager):
        """Test Z index initializes to 0."""
        sync_manager.register_modality(0)
        assert sync_manager._states[0].z_index == 0
    
    def test_set_z_index(self, sync_manager):
        """Test setting Z index on single modality."""
        sync_manager.register_modality(0)
        sync_manager.set_z_index(0, 7)
        assert sync_manager._states[0].z_index == 7
    
    def test_z_sync_disabled_no_propagation(self, sync_manager):
        """Test Z changes don't propagate when sync disabled."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.set_z_index(0, 3)
        # Modality 1 should not change
        assert sync_manager._states[1].z_index == 0
    
    def test_enable_z_sync(self, sync_manager):
        """Test enabling Z sync."""
        assert sync_manager.z_sync_enabled is False
        sync_manager.enable_z_sync(True)
        assert sync_manager.z_sync_enabled is True
    
    def test_enable_z_sync_synchronizes_all(self, sync_manager):
        """Test enabling Z sync synchronizes all modalities."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        sync_manager.set_z_index(0, 12)
        sync_manager.enable_z_sync(True)
        
        # All should be synced to first
        assert sync_manager._states[1].z_index == 12
        assert sync_manager._states[2].z_index == 12
    
    def test_z_sync_propagates_changes(self, sync_manager):
        """Test Z changes propagate when sync enabled."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_z_sync(True)
        sync_manager.set_z_index(0, 9)
        
        assert sync_manager._states[0].z_index == 9
        assert sync_manager._states[1].z_index == 9
    
    def test_z_sync_signal_emission(self, sync_manager, qtbot):
        """Test z_sync_changed signal."""
        with qtbot.waitSignal(sync_manager.z_sync_changed, timeout=1000) as blocker:
            sync_manager.enable_z_sync(True)
        assert blocker.args == [True]
    
    def test_negative_z_index_clamped(self, sync_manager):
        """Test negative Z index clamped to 0."""
        sync_manager.register_modality(0)
        sync_manager.set_z_index(0, -3)
        assert sync_manager._states[0].z_index == 0
    
    def test_z_index_in_link_group(self, sync_manager):
        """Test Z sync within link group."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        group_id = sync_manager.create_link_group({0, 1})
        
        # Set different Z indices
        sync_manager.set_z_index(0, 4)
        sync_manager.set_z_index(2, 8)
        
        # Change in group should only affect group members
        sync_manager.set_z_index(0, 6)
        
        assert sync_manager._states[0].z_index == 6
        assert sync_manager._states[1].z_index == 6
        assert sync_manager._states[2].z_index == 8  # Not in group
