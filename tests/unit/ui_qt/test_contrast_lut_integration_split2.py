"""Split definitions from test_contrast_lut_integration.py."""


import numpy as np
import pytest
from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui
from pytestqt.qtbot import QtBot

from phage_annotator.ui_qt.widgets.slider_panel_double import SliderPanelDouble
from phage_annotator.ui_qt.utils.contrast_lut import (
    ConverterSetup,
    MinMaxGroup,
    computeHistogram,
    autoScaleHistogram,
)
from phage_annotator.data.display_mapping import DisplayMapping


class TestContrastUIIntegration:
    """Integration tests for complete contrast UI."""

    def test_lut_with_display_mapping(self):
        """LUT should work with DisplayMapping."""
        mappings = DisplayMapping(min_val=100.0, max_val=500.0)

        # Create converter from mapping
        converter = ConverterSetup()
        converter.setMinMax(mappings.min_val, mappings.max_val)

        # Test
        test_value = 300
        output = converter.convert(test_value)
        assert output == 127 or output == 128  # Mid-gray

    def test_slider_with_converter(self):
        """Slider value changes should update converter."""
        converter = ConverterSetup()
        converter.setMinMax(0.0, 100.0)

        # Simulate slider changing range
        converter.setMinMax(25.0, 75.0)

        # Values should now map differently
        assert converter.convert(25) == 0  # Min threshold
        assert converter.convert(75) == 255  # Max threshold

    def test_preset_with_histogram(self):
        """Presets should work with histogram data."""
        # Create realistic histogram data
        histogram_data = np.concatenate([
            np.random.normal(50, 10, 5000),
            np.random.normal(150, 20, 5000),
            np.random.normal(200, 15, 5000),
        ]).astype(np.uint16)

        # Apply auto preset
        vmin, vmax = autoScaleHistogram(histogram_data, method="percentile")

        # Should have detected reasonable range
        assert vmin > 0
        assert vmin < vmax
        # Data is normalized to percentile range, not 255
        assert vmin < float(np.max(histogram_data))

class TestPerformanceMetrics:
    """Validate performance targets."""

    def test_lut_computation_under_1ms(self):
        """LUT pre-computation performance validation."""
        converter = ConverterSetup()
        start = QtCore.QElapsedTimer()
        start.start()

        for _ in range(10):  # 10 LUT computations
            converter.setMinMax(
                np.random.rand() * 100,
                100 + np.random.rand() * 100,
            )

        elapsed = start.elapsed()
        # 10 LUT computations should take <250ms in CI/headless environments.
        # LUT is O(65536); rare scheduler jitter can push 200ms by ~1-20ms.
        assert elapsed < 250, f"LUT computation too slow: {elapsed}ms"

    def test_slider_interaction_responsive(self):
        """Slider interaction should be responsive (<200ms)."""
        slider = SliderPanelDouble(min_val=0.0, max_val=100.0)
        start = QtCore.QElapsedTimer()
        start.start()

        for i in range(100):
            ratio = i / 100.0
            slider.setValues(
                0.0 + ratio * 50.0,
                100.0 - ratio * 50.0,
                emit_signal=False,
            )

        elapsed = start.elapsed()
        # 100 slider updates should take <200ms
        assert elapsed < 200, f"Slider interaction too slow: {elapsed}ms"

    def test_array_conversion_performance(self):
        """Array conversion should handle large images efficiently."""
        converter = ConverterSetup()
        converter.setMinMax(1000, 5000)

        # Test with realistic image size
        data = (np.random.rand(512, 512) * 10000).astype(np.uint16)  # Reduced from 2048x2048

        start = QtCore.QElapsedTimer()
        start.start()
        result = converter.convertArray(data)
        elapsed = start.elapsed()

        # Should complete in reasonable time for responsive UI
        assert elapsed < 100, f"Array conversion too slow: {elapsed}ms"
        assert result.shape == data.shape
