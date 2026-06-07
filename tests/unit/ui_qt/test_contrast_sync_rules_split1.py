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


@dataclass
class MockImage:
    """Mock image for testing."""
    id: int
    array: np.ndarray

class TestSyncRulesEngine:
    """Test sync rule propagation logic in DisplayMapping."""
    
    def test_propagate_sync_updates_returns_list(self):
        """propagate_sync_updates should return list of (image_id, panel) tuples."""
        mapping = DisplayMapping(0.0, 1.0)
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], int)
            assert isinstance(item[1], str)
    
    def test_no_sync_returns_empty(self):
        """With no sync rules, should return empty list."""
        mapping = DisplayMapping(0.0, 1.0)
        # Ensure no sync rules are enabled
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=False)
        
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        assert result == []
    
    def test_sync_vmin_propagation(self):
        """With sync_vmin enabled, should include images with sync_vmin."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up two images
        image1_mapping = mapping.mapping_for(1, "frame")
        image2_mapping = mapping.mapping_for(2, "frame")
        
        # Enable sync on image 2
        image2_mapping.set_sync_rules(sync_vmin=True, sync_vmax=False, sync_contrast=False)
        
        # Propagate from image 1
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        # Image 2 should be in results because it has sync_vmin enabled
        assert (2, "frame") in result
    
    def test_sync_vmax_propagation(self):
        """With sync_vmax enabled, should include images with sync_vmax."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up two images
        image1_mapping = mapping.mapping_for(1, "frame")
        image2_mapping = mapping.mapping_for(2, "frame")
        
        # Enable sync on image 2
        image2_mapping.set_sync_rules(sync_vmin=False, sync_vmax=True, sync_contrast=False)
        
        # Propagate from image 1
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        # Image 2 should be in results because it has sync_vmax enabled
        assert (2, "frame") in result
    
    def test_sync_contrast_propagation(self):
        """With sync_contrast enabled, should include images with sync_contrast."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up two images
        image1_mapping = mapping.mapping_for(1, "frame")
        image2_mapping = mapping.mapping_for(2, "frame")
        
        # Enable sync on image 2
        image2_mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=True)
        
        # Propagate from image 1
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        # Image 2 should be in results because it has sync_contrast enabled
        assert (2, "frame") in result
    
    def test_multiple_modalities_sync(self):
        """Should handle multiple modalities with different sync states."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up multiple images
        img1_frame = mapping.mapping_for(1, "frame")
        img2_frame = mapping.mapping_for(2, "frame")
        img3_frame = mapping.mapping_for(3, "frame")
        img4_frame = mapping.mapping_for(4, "frame")
        
        # Enable different sync rules
        img2_frame.set_sync_rules(sync_vmin=True, sync_vmax=False)
        img3_frame.set_sync_rules(sync_vmin=False, sync_vmax=True)
        img4_frame.set_sync_rules(sync_vmin=False, sync_vmax=False)  # No sync
        
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        
        # Should include image 2 and 3 (they have sync rules)
        # Should not include image 4 (no sync rules)
        assert (2, "frame") in result
        assert (3, "frame") in result
        assert (4, "frame") not in result
    
    def test_source_image_excluded(self):
        """Source image should not be in propagation targets."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up images
        img1 = mapping.mapping_for(1, "frame")
        img2 = mapping.mapping_for(2, "frame")
        img1.set_sync_rules(sync_vmin=True)
        img2.set_sync_rules(sync_vmin=True)
        
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        
        # Source image 1 should not be in results
        assert (1, "frame") not in result
        # Image 2 should be
        assert (2, "frame") in result
    
    def test_panel_specific_propagation(self):
        """Should handle different panels separately."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Set up frame and mean panels for two images
        img1_frame = mapping.mapping_for(1, "frame")
        img1_mean = mapping.mapping_for(1, "mean")
        img2_frame = mapping.mapping_for(2, "frame")
        img2_mean = mapping.mapping_for(2, "mean")
        
        # Enable sync on image 2 frame panel only
        img2_frame.set_sync_rules(sync_vmin=True)
        img2_mean.set_sync_rules(sync_vmin=False)
        
        result = mapping.propagate_sync_updates(source_image_id=1, panel="frame")
        
        # Should include image 2 frame but not mean
        assert (2, "frame") in result
        assert (2, "mean") not in result
    
    def test_sync_state_code_accuracy(self):
        """sync_state_code should return correct state representation."""
        mapping = DisplayMapping(0.0, 1.0)
        
        # Test all states
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=False)
        assert mapping.sync_state_code() == "NONE"
        
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=False, sync_contrast=False)
        assert mapping.sync_state_code() == "VMIN"
        
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=True, sync_contrast=False)
        assert mapping.sync_state_code() == "VMAX"
        
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True, sync_contrast=False)
        assert mapping.sync_state_code() == "VMIN+VMAX"
        
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=True)
        assert mapping.sync_state_code() == "CONTRAST"
