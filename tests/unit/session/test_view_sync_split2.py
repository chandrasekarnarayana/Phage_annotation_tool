"""Split definitions from test_view_sync.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

from phage_annotator.session.view_sync import (
    ViewState,
    ViewSyncManager,
)


from tests.unit.session.test_view_sync_split1 import sync_manager

class TestViewSyncManager:
    """Test ViewSyncManager class."""
    
    def test_initialization(self, sync_manager):
        """Test manager initializes correctly."""
        assert sync_manager._zoom_sync_enabled is False
        assert sync_manager._pan_sync_enabled is False
        assert len(sync_manager._states) == 0
    
    def test_register_modality(self, sync_manager):
        """Test registering a modality."""
        sync_manager.register_modality(0)
        
        assert 0 in sync_manager._states
        state = sync_manager._states[0]
        assert state.modality_idx == 0
        assert state.zoom_level == 1.0
        assert state.pan_x == 0.0
        assert state.pan_y == 0.0
    
    def test_unregister_modality(self, sync_manager):
        """Test unregistering a modality."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.unregister_modality(0)
        
        assert 0 not in sync_manager._states
        assert 1 in sync_manager._states
    
    def test_enable_zoom_sync(self, sync_manager, qtbot):
        """Test enabling zoom sync."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.zoom_sync_changed, timeout=1000) as blocker:
            sync_manager.enable_zoom_sync(True)
        
        assert sync_manager._zoom_sync_enabled is True
        assert blocker.args == [True]
    
    def test_enable_pan_sync(self, sync_manager, qtbot):
        """Test enabling pan sync."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.pan_sync_changed, timeout=1000) as blocker:
            sync_manager.enable_pan_sync(True)
        
        assert sync_manager._pan_sync_enabled is True
        assert blocker.args == [True]
    
    def test_set_zoom(self, sync_manager, qtbot):
        """Test setting zoom for a modality."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.view_changed, timeout=1000) as blocker:
            sync_manager.set_zoom(0, 2.0)
        
        assert sync_manager._states[0].zoom_level == 2.0
        assert blocker.args[0] == 0  # modality_idx
        assert blocker.args[1] == 2.0  # zoom
    
    def test_set_zoom_clamps(self, sync_manager):
        """Test zoom level clamping."""
        sync_manager.register_modality(0)
        
        # Below minimum
        sync_manager.set_zoom(0, 0.05)
        assert sync_manager._states[0].zoom_level >= 0.1
        
        # Above maximum
        sync_manager.set_zoom(0, 25.0)
        assert sync_manager._states[0].zoom_level <= 20.0
    
    def test_set_pan(self, sync_manager, qtbot):
        """Test setting pan for a modality."""
        sync_manager.register_modality(0)
        
        with qtbot.waitSignal(sync_manager.view_changed, timeout=1000) as blocker:
            sync_manager.set_pan(0, 100.0, 50.0)
        
        assert sync_manager._states[0].pan_x == 100.0
        assert sync_manager._states[0].pan_y == 50.0
        assert blocker.args[2] == 100.0  # pan_x
        assert blocker.args[3] == 50.0  # pan_y
    
    def test_set_view(self, sync_manager):
        """Test setting both zoom and pan."""
        sync_manager.register_modality(0)
        
        sync_manager.set_view(0, 1.5, 25.0, 30.0)
        
        state = sync_manager._states[0]
        assert state.zoom_level == 1.5
        assert state.pan_x == 25.0
        assert state.pan_y == 30.0
    
    def test_zoom_sync_propagation(self, sync_manager):
        """Test zoom sync propagates to all modalities."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        sync_manager.enable_zoom_sync(True)
        sync_manager.set_zoom(0, 2.5)
        
        # All should have same zoom
        assert sync_manager._states[0].zoom_level == 2.5
        assert sync_manager._states[1].zoom_level == 2.5
        assert sync_manager._states[2].zoom_level == 2.5
    
    def test_pan_sync_propagation(self, sync_manager):
        """Test pan sync propagates to all modalities."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.enable_pan_sync(True)
        sync_manager.set_pan(0, 100.0, 200.0)
        
        # All should have same pan
        assert sync_manager._states[0].pan_x == 100.0
        assert sync_manager._states[0].pan_y == 200.0
        assert sync_manager._states[1].pan_x == 100.0
        assert sync_manager._states[1].pan_y == 200.0
    
    def test_independent_zoom_no_sync(self, sync_manager):
        """Test independent zoom without sync enabled."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        # Sync disabled
        sync_manager.enable_zoom_sync(False)
        
        sync_manager.set_zoom(0, 2.0)
        sync_manager.set_zoom(1, 1.5)
        
        # Should be independent
        assert sync_manager._states[0].zoom_level == 2.0
        assert sync_manager._states[1].zoom_level == 1.5
    
    def test_create_link_group(self, sync_manager):
        """Test creating a link group."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        group_id = sync_manager.create_link_group({0, 1})
        
        assert group_id in sync_manager._link_groups
        assert 0 in sync_manager._link_groups[group_id]
        assert 1 in sync_manager._link_groups[group_id]
    
    def test_link_group_zoom_sync(self, sync_manager):
        """Test zoom syncs within link group."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        # Link 0 and 1, leave 2 independent
        sync_manager.create_link_group({0, 1})
        
        sync_manager.set_zoom(0, 3.0)
        
        # 0 and 1 should sync, 2 should not
        assert sync_manager._states[0].zoom_level == 3.0
        assert sync_manager._states[1].zoom_level == 3.0
        assert sync_manager._states[2].zoom_level == 1.0  # Default
    
    def test_link_group_pan_sync(self, sync_manager):
        """Test pan syncs within link group."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        sync_manager.register_modality(2)
        
        sync_manager.create_link_group({0, 1})
        
        sync_manager.set_pan(0, 50.0, 75.0)
        
        # 0 and 1 should sync, 2 should not
        assert sync_manager._states[0].pan_x == 50.0
        assert sync_manager._states[1].pan_x == 50.0
        assert sync_manager._states[2].pan_x == 0.0  # Default
    
    def test_remove_link_group(self, sync_manager):
        """Test removing a link group."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        group_id = sync_manager.create_link_group({0, 1})
        sync_manager.remove_link_group(group_id)
        
        assert group_id not in sync_manager._link_groups
        assert 0 not in sync_manager._modality_to_group
        assert 1 not in sync_manager._modality_to_group
    
    def test_get_view_state(self, sync_manager):
        """Test getting view state."""
        sync_manager.register_modality(0)
        sync_manager.set_view(0, 2.0, 100.0, 200.0)
        
        state = sync_manager.get_view_state(0)
        
        assert state is not None
        assert state.zoom_level == 2.0
        assert state.pan_x == 100.0
        assert state.pan_y == 200.0
    
    def test_get_view_state_nonexistent(self, sync_manager):
        """Test getting state for non-existent modality."""
        state = sync_manager.get_view_state(999)
        assert state is None
    
    def test_reset_view(self, sync_manager):
        """Test resetting view to defaults."""
        sync_manager.register_modality(0)
        sync_manager.set_view(0, 3.0, 150.0, 250.0)
        
        sync_manager.reset_view(0)
        
        state = sync_manager._states[0]
        assert state.zoom_level == 1.0
        assert state.pan_x == 0.0
        assert state.pan_y == 0.0
    
    def test_reset_all_views(self, sync_manager):
        """Test resetting all views."""
        sync_manager.register_modality(0)
        sync_manager.register_modality(1)
        
        sync_manager.set_zoom(0, 2.0)
        sync_manager.set_zoom(1, 3.0)
        
        sync_manager.reset_all_views()
        
        assert sync_manager._states[0].zoom_level == 1.0
        assert sync_manager._states[1].zoom_level == 1.0
    
    def test_zoom_sync_property(self, sync_manager):
        """Test zoom_sync_enabled property."""
        assert sync_manager.zoom_sync_enabled is False
        
        sync_manager.enable_zoom_sync(True)
        assert sync_manager.zoom_sync_enabled is True
    
    def test_pan_sync_property(self, sync_manager):
        """Test pan_sync_enabled property."""
        assert sync_manager.pan_sync_enabled is False
        
        sync_manager.enable_pan_sync(True)
        assert sync_manager.pan_sync_enabled is True
