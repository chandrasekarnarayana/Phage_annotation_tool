"""Split definitions from test_contrast_lut.py."""


import numpy as np
import pytest
from phage_annotator.ui_qt.utils.contrast_lut import (
    ConverterSetup,
    MinMaxGroup,
    computeHistogram,
    autoScaleHistogram,
)


class TestContrastIntegration:
    """Integration tests for contrast system."""
    
    def test_converter_with_histogram(self):
        """Use histogram to auto-scale converter."""
        # Create test image with known range
        data = np.random.randint(1000, 5000, (100, 100), dtype=np.uint16)
        
        # Auto-scale
        min_val, max_val = autoScaleHistogram(data, "percentile")
        
        # Create converter
        converter = ConverterSetup()
        converter.setMinMax(min_val, max_val)
        
        # Apply to data
        output = converter.convertArray(data)
        
        assert output.min() >= 0
        assert output.max() <= 255
        assert output.dtype == np.uint8
    
    def test_minmax_group_with_converter(self):
        """MinMaxGroup controlling converter updates."""
        group = MinMaxGroup(100, 200)
        converter = ConverterSetup()
        
        update_count = [0]
        
        def on_change():
            """Run the on change workflow."""
            update_count[0] += 1
        
        converter.addListener(on_change)
        
        # Update group → should trigger converter updates
        group.min = 150
        # (Manually connect since real UI would do this)
        converter.setMinMax(group.min, group.max)
        
        assert converter.minInput == 150
        assert converter.maxInput == 200
