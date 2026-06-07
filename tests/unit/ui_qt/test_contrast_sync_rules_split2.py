"""Split definitions from test_contrast_sync_rules.py."""


import numpy as np
import pytest
from dataclasses import dataclass
from typing import List, Tuple

from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.ui_qt.utils.visual_indicators import (
    SyncStateIndicator,
    ModalityIndicator,
    DisplaySettingsBadge,
    StatusIndicatorBar,
)


class TestSyncVisualization:
    """Test sync indicator display."""
    
    def test_sync_state_indicator_creates(self, qtbot):
        """SyncStateIndicator should be creatable."""
        indicator = SyncStateIndicator()
        qtbot.addWidget(indicator)
        assert indicator is not None
    
    def test_sync_state_indicator_updates(self, qtbot):
        """SyncStateIndicator should update when sync state changes."""
        indicator = SyncStateIndicator()
        qtbot.addWidget(indicator)
        
        # Initially no sync
        assert not indicator._sync_vmin
        assert not indicator._sync_vmax
        assert not indicator._sync_contrast
        
        # Update to enable sync
        indicator.set_sync_state(vmin=True, vmax=False, contrast=False)
        assert indicator._sync_vmin is True
        assert indicator._sync_vmax is False
        
        # Update again
        indicator.set_sync_state(vmin=True, vmax=True, contrast=False)
        assert indicator._sync_vmin is True
        assert indicator._sync_vmax is True
    
    def test_sync_state_indicator_renders(self, qtbot):
        """SyncStateIndicator should render without errors."""
        indicator = SyncStateIndicator()
        qtbot.addWidget(indicator)
        indicator.show()
        indicator.set_sync_state(vmin=True, vmax=True, contrast=False)
        # Rendering happens via paintEvent - just verify no exceptions
        assert indicator.isVisible()
    
    def test_modality_indicator_creates(self, qtbot):
        """ModalityIndicator should be creatable."""
        indicator = ModalityIndicator()
        qtbot.addWidget(indicator)
        assert indicator is not None
    
    def test_modality_indicator_updates(self, qtbot):
        """ModalityIndicator should update modality info."""
        indicator = ModalityIndicator()
        qtbot.addWidget(indicator)
        
        indicator.set_modality_info(
            name="Ch488",
            projection_type="Frame",
            is_active=True,
            is_linked=True
        )
        
        assert indicator._modality_name == "Ch488"
        assert indicator._projection_type == "Frame"
        assert indicator._is_active is True
        assert indicator._is_linked is True
    
    def test_display_settings_badge_creates(self, qtbot):
        """DisplaySettingsBadge should be creatable."""
        badge = DisplaySettingsBadge()
        qtbot.addWidget(badge)
        assert badge is not None
    
    def test_display_settings_badge_updates(self, qtbot):
        """DisplaySettingsBadge should update display mode."""
        badge = DisplaySettingsBadge()
        qtbot.addWidget(badge)
        
        badge.set_display_mode("Log", is_modified=True)
        assert badge._mode == "Log"
        assert badge._is_modified is True
    
    def test_status_indicator_bar_creates(self, qtbot):
        """StatusIndicatorBar should combine all indicators."""
        bar = StatusIndicatorBar()
        qtbot.addWidget(bar)
        
        assert bar.modality_indicator is not None
        assert bar.display_badge is not None
        assert bar.sync_indicator is not None
    
    def test_status_indicator_bar_updates(self, qtbot):
        """StatusIndicatorBar should update all indicators."""
        bar = StatusIndicatorBar()
        qtbot.addWidget(bar)
        
        bar.update_status(
            modality_name="Ch405",
            projection_type="Mean",
            is_active=True,
            is_linked=False,
            display_mode="Auto",
            is_modified=False,
            sync_vmin=False,
            sync_vmax=True,
            sync_contrast=False,
        )
        
        assert bar.modality_indicator._modality_name == "Ch405"
        assert bar.display_badge._mode == "Auto"
        assert bar.sync_indicator._sync_vmax is True
    
    def test_is_sync_enabled(self):
        """is_sync_enabled should correctly report sync state."""
        mapping = DisplayMapping(0.0, 1.0)
        
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=False)
        assert mapping.is_sync_enabled() is False
        
        mapping.set_sync_rules(sync_vmin=True)
        assert mapping.is_sync_enabled() is True
        
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=True)
        assert mapping.is_sync_enabled() is True
        
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=True)
        assert mapping.is_sync_enabled() is True

class TestSyncIntegration:
    """Integration tests for sync cascading through display controls."""
    
    def test_window_update_propagates_to_synced(self):
        """set_window should be propagatable to synced modalities."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up images
        img1 = mapping.mapping_for(1, "frame")
        img2 = mapping.mapping_for(2, "frame")
        img2.set_sync_rules(sync_vmin=True, sync_vmax=True)
        
        # Update image 1's window
        img1.set_window(0.2, 0.8)
        
        # Simulate propagation to image 2
        targets = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        assert (2, "frame") in targets
        
        # In actual use, caller would update image 2 as well
        img2.set_window(0.2, 0.8)
        assert img2.min_val == 0.2
        assert img2.max_val == 0.8
    
    def test_partial_sync_independence(self):
        """Images with partial sync rules should maintain independence on non-synced attributes."""
        mapping = DisplayMapping(0.0, 1.0)
        
        img1 = mapping.mapping_for(1, "frame")
        img2 = mapping.mapping_for(2, "frame")
        
        # Image 2 only syncs vmin
        img2.set_sync_rules(sync_vmin=True, sync_vmax=False, sync_contrast=False)
        
        img1.set_window(0.2, 0.8)
        img1.gamma = 2.0
        img1.lut = 5
        
        # Image 2 vmin should be available to sync
        targets = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        assert (2, "frame") in targets
        
        # But image 2 could independently set vmax and other properties
        img2.max_val = 0.95  # Different from img1
        img2.gamma = 1.5     # Different from img1
        assert img2.max_val != img1.max_val
        assert img2.gamma != img1.gamma
    
    def test_no_circular_sync(self):
        """Propagation should not create circular updates."""
        mapping = DisplayMapping(0.0, 1.0)
        
        img1 = mapping.mapping_for(1, "frame")
        img2 = mapping.mapping_for(2, "frame")
        
        # Both have sync enabled
        img1.set_sync_rules(sync_vmin=True)
        img2.set_sync_rules(sync_vmin=True)
        
        # When propagating from image 1
        targets_from_1 = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        
        # Should not include image 1 again (which would create circular sync)
        assert (1, "frame") not in targets_from_1
        assert (2, "frame") in targets_from_1
    
    def test_three_plus_modalities_cascade(self):
        """Should correctly handle 3+ modalities in cascade."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up 4 modalities
        modalities = [mapping.mapping_for(i, "frame") for i in range(1, 5)]
        
        # Configure sync: 2 and 3 sync to 1, 4 syncs to 1
        modalities[1].set_sync_rules(sync_vmin=True)  # Image 2
        modalities[2].set_sync_rules(sync_vmin=True)  # Image 3
        modalities[3].set_sync_rules(sync_vmin=True)  # Image 4
        
        # Propagate from image 1
        targets = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        
        # Should include 2, 3, 4
        assert (2, "frame") in targets
        assert (3, "frame") in targets
        assert (4, "frame") in targets
        assert (1, "frame") not in targets

class TestSyncPerformance:
    """Performance validation for sync operations."""
    
    def test_propagate_sync_updates_performance(self, benchmark):
        """propagate_sync_updates should complete efficiently even with many modalities."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Create 10 modalities
        for i in range(1, 11):
            mod = mapping.mapping_for(i, "frame")
            if i % 2 == 0:  # Every other modality has sync enabled
                mod.set_sync_rules(sync_vmin=True, sync_vmax=True)
        
        def call_propagate():
            """Run the call propagate workflow."""
            return mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        
        result = benchmark(call_propagate)
        
        # Should return 5 targets (images 2, 4, 6, 8, 10)
        assert len(result) == 5
    
    def test_set_sync_rules_performance(self, benchmark):
        """set_sync_rules should be fast."""
        mapping = DisplayMapping(0.0, 1.0)
        
        def set_rules():
            """Set rules for the current workflow."""
            mapping.set_sync_rules(sync_vmin=True, sync_vmax=True, sync_contrast=False)
        
        result = benchmark(set_rules)
        
        assert mapping.is_sync_enabled()
