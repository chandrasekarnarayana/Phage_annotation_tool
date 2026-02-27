"""Tests for contrast LUT (Look-Up Table) engine.

Comprehensive testing of brightness mapping and contrast adjustment functionality,
including histogram computation, LUT generation, and real-time preview updates.
"""

import numpy as np
import pytest
from phage_annotator.ui_qt.utils.contrast_lut import (
    ConverterSetup,
    MinMaxGroup,
    computeHistogram,
    autoScaleHistogram,
)


class TestConverterSetup:
    """Test ConverterSetup LUT pre-computation."""
    
    def test_create_default_converter(self):
        """Create converter with defaults."""
        converter = ConverterSetup()
        assert converter.minInput == 0.0
        assert converter.maxInput == 255.0
        assert converter.minOutput == 0.0
        assert converter.maxOutput == 255.0
    
    def test_set_min_max_and_update_lut(self):
        """Set min/max and verify LUT is created."""
        converter = ConverterSetup()
        converter.setMinMax(100, 200)
        
        assert converter.minInput == 100
        assert converter.maxInput == 200
        assert converter.lut is not None
        assert len(converter.lut) == 65536
    
    def test_lut_black_threshold(self):
        """Values below min should map to black output."""
        converter = ConverterSetup()
        converter.setMinMax(1000, 5000)
        
        # Values below 1000 should be black (0)
        assert converter.convert(0) == 0
        assert converter.convert(500) == 0
        assert converter.convert(999) == 0
    
    def test_lut_white_threshold(self):
        """Values above max should map to white output."""
        converter = ConverterSetup()
        converter.setMinMax(1000, 5000)
        
        # Values above 5000 should be white (255)
        assert converter.convert(5001) == 255
        assert converter.convert(10000) == 255
        assert converter.convert(65535) == 255
    
    def test_lut_linear_mapping(self):
        """Values within range should map linearly."""
        converter = ConverterSetup()
        converter.setMinMax(1000, 5000)
        
        # Exact boundaries
        assert converter.convert(1000) == 0  # Min thresh → black
        assert converter.convert(5000) == 255  # Max thresh → white
        
        # Midpoint
        mid = (1000 + 5000) // 2  # 3000
        mid_brightness = converter.convert(mid)
        # Should be approximately 127/128 (mid-gray)
        assert mid_brightness >= 125 and mid_brightness <= 130
    
    def test_lut_correctness_formula(self):
        """Verify LUT follows mathematical formula."""
        converter = ConverterSetup()
        converter.setMinMax(100, 900)
        
        # Test various points
        for input_val in [100, 200, 300, 500, 900]:
            output = converter.convert(input_val)
            # Calculate expected from formula
            normalized = (input_val - 100) / (900 - 100)
            expected = int(normalized * 255)
            assert output == expected, f"At {input_val}: got {output}, expected {expected}"
    
    def test_set_min_validation(self):
        """Invalid min/max should raise error."""
        converter = ConverterSetup()
        
        with pytest.raises(ValueError):
            converter.setMinMax(500, 500)  # min == max
        
        with pytest.raises(ValueError):
            converter.setMinMax(500, 400)  # min > max
    
    def test_convert_array(self):
        """Apply LUT to entire image array."""
        converter = ConverterSetup()
        converter.setMinMax(100, 200)
        
        # Create test data
        data = np.array([[50, 100, 150, 200, 250]], dtype=np.uint16)
        
        output = converter.convertArray(data)
        
        assert output.shape == data.shape
        assert output.dtype == np.uint8
        assert output[0, 0] == 0    # 50 < 100 → black
        assert output[0, 1] == 0    # 100 = min → black
        assert output[0, 2] == 127  # 150 = mid → mid-gray
        assert output[0, 3] == 255  # 200 = max → white
        assert output[0, 4] == 255  # 250 > 200 → white
    
    def test_listener_notification(self):
        """Listeners should be called on value changes."""
        converter = ConverterSetup()
        call_count = [0]
        
        def listener():
            call_count[0] += 1
        
        converter.addListener(listener)
        
        converter.setMinMax(100, 200)
        assert call_count[0] == 1
        
        converter.setMinMax(150, 250)
        assert call_count[0] == 2
    
    def test_serialization(self):
        """Serialize and deserialize converter."""
        original = ConverterSetup(minInput=50, maxInput=200)
        
        data = original.toDict()
        restored = ConverterSetup.fromDict(data)
        
        assert restored.minInput == 50
        assert restored.maxInput == 200
        assert restored.lut is not None


class TestMinMaxGroup:
    """Test MinMaxGroup coupled value management."""
    
    def test_create_min_max_group(self):
        """Create group with values."""
        group = MinMaxGroup(10, 100)
        assert group.min == 10
        assert group.max == 100
    
    def test_min_max_invariant(self):
        """Enforce min < max invariant."""
        group = MinMaxGroup(10, 100)
        
        # Can't set min >= max
        with pytest.raises(ValueError):
            group.min = 100
        
        with pytest.raises(ValueError):
            group.min = 150
    
    def test_max_min_invariant(self):
        """Enforce max > min invariant."""
        group = MinMaxGroup(10, 100)
        
        # Can't set max <= min
        with pytest.raises(ValueError):
            group.max = 10
        
        with pytest.raises(ValueError):
            group.max = 5
    
    def test_set_values_synchronously(self):
        """Set both values without triggering intermediate invalid state."""
        group = MinMaxGroup(10, 100)
        
        group.setValues(200, 300)
        assert group.min == 200
        assert group.max == 300
    
    def test_listener_on_min_change(self):
        """Listener called when min changes."""
        group = MinMaxGroup(10, 100)
        events = []
        
        def listener(change_type, value):
            events.append((change_type, value))
        
        group.addListener(listener)
        
        group.min = 20
        assert len(events) == 1
        assert events[0] == ("min", 20)
    
    def test_listener_on_max_change(self):
        """Listener called when max changes."""
        group = MinMaxGroup(10, 100)
        events = []
        
        def listener(change_type, value):
            events.append((change_type, value))
        
        group.addListener(listener)
        
        group.max = 150
        assert len(events) == 1
        assert events[0] == ("max", 150)
    
    def test_listener_on_both_change(self):
        """Listener called when both values change."""
        group = MinMaxGroup(10, 100)
        events = []
        
        def listener(change_type, value):
            events.append((change_type, value))
        
        group.addListener(listener)
        
        group.setValues(20, 150)
        assert len(events) == 1
        assert events[0] == ("range", (20, 150))


class TestHistogramFunctions:
    """Test histogram computation utilities."""
    
    def test_compute_histogram_basic(self):
        """Compute histogram from simple data."""
        data = np.array([0, 50, 100, 150, 200, 255])
        hist, edges = computeHistogram(data, bins=256)
        
        assert len(hist) == 256
        assert np.sum(hist) == 6  # Total count
    
    def test_auto_scale_minmax(self):
        """Auto-scale with min/max method."""
        data = np.array([[10, 50, 100, 200, 250]])
        
        min_val, max_val = autoScaleHistogram(data, "minmax")
        
        assert min_val == 10
        assert max_val == 250
    
    def test_auto_scale_percentile(self):
        """Auto-scale with percentile method."""
        # Create data with outliers
        data = np.array([0, 1, 2, 50, 100, 150, 200, 254, 255, 256])
        
        min_val, max_val = autoScaleHistogram(data, "percentile")
        
        # 2%-98% range should exclude extreme outliers
        assert min_val > 0
        assert max_val < 256
    
    def test_auto_scale_std(self):
        """Auto-scale with standard deviation method."""
        # Normal distribution
        data = np.random.normal(128, 30, 1000).astype(np.uint8)
        
        min_val, max_val = autoScaleHistogram(data, "std")
        
        # Range should be reasonable (mean ± 2σ)
        mean = np.mean(data)
        assert min_val < mean
        assert max_val > mean


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
            update_count[0] += 1
        
        converter.addListener(on_change)
        
        # Update group → should trigger converter updates
        group.min = 150
        # (Manually connect since real UI would do this)
        converter.setMinMax(group.min, group.max)
        
        assert converter.minInput == 150
        assert converter.maxInput == 200
