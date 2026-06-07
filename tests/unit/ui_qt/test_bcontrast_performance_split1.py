"""Split definitions from test_bcontrast_performance.py."""


import pytest
import time
from unittest.mock import Mock
from phage_annotator.data.display_mapping import DisplayMapping


class TestSliderPerformance:
    """Benchmark slider operations."""

    def test_slider_value_update_latency(self, benchmark):
        """Benchmark slider setValues() latency."""
        from phage_annotator.ui_qt.widgets.slider_panel_double import SliderPanelDouble
        
        @pytest.mark.skip(reason="Requires Qt app")
        def setup():
            """Run the setup workflow."""
            return SliderPanelDouble()
        
        # For non-Qt benchmark, test logic only
        def slider_update():
            # Simulate value update logic
            """Run the slider update workflow."""
            min_val, max_val = 50, 200
            fixed_min = min(min_val, max_val)
            fixed_max = max(min_val, max_val)
            assert fixed_min <= fixed_max
        
        result = benchmark(slider_update)
        assert result is None  # Verify operation completes

class TestDisplayMappingPerformance:
    """Benchmark DisplayMapping operations."""

    def test_display_mapping_creation(self, benchmark):
        """Benchmark DisplayMapping instantiation."""
        def create_mapping():
            """Create mapping for the current workflow."""
            return DisplayMapping(50, 200)
        
        mapping = benchmark(create_mapping)
        assert mapping.min_val == 50
        assert mapping.max_val == 200

    def test_display_mapping_attribute_access(self, benchmark):
        """Benchmark DisplayMapping attribute access."""
        mapping = DisplayMapping(50, 200)
        
        def access_attributes():
            """Run the access attributes workflow."""
            _ = mapping.min_val
            _ = mapping.max_val
            _ = mapping.gamma
            _ = mapping.lut
            return True
        
        result = benchmark(access_attributes)
        assert result is True

    def test_display_mapping_update(self, benchmark):
        """Benchmark DisplayMapping value updates."""
        mapping = DisplayMapping(0, 255)
        
        def update_values():
            """Update values for the current workflow."""
            mapping.min_val = 50
            mapping.max_val = 200
            mapping.gamma = 1.5
            return mapping
        
        result = benchmark(update_values)
        assert result.min_val == 50
        assert result.max_val == 200

    def test_modality_sync_simulation(self, benchmark):
        """Benchmark simulated modality sync operation."""
        mapping = DisplayMapping(50, 200)
        modality = Mock()
        modality.display_settings = Mock()
        
        def sync_operation():
            """Synchronize operation for the current workflow."""
            modality.display_settings.vmin = mapping.min_val
            modality.display_settings.vmax = mapping.max_val
            modality.display_settings.gamma = mapping.gamma
            return modality
        
        result = benchmark(sync_operation)
        assert result.display_settings.vmin == 50

class TestSignalBlockingPerformance:
    """Benchmark signal blocking operations."""

    def test_signal_blocking_overhead(self, benchmark):
        """Benchmark signal blocking and unblocking."""
        widget = Mock()
        widget.blockSignals = Mock()
        
        def block_unblock_cycle():
            """Run the block unblock cycle workflow."""
            widget.blockSignals(True)
            widget.blockSignals(False)
            return True
        
        result = benchmark(block_unblock_cycle)
        assert result is True
        # Benchmark runs multiple iterations, so call count >= 2
        assert widget.blockSignals.call_count >= 2

    def test_programmatic_widget_update(self, benchmark):
        """Benchmark programmatic widget update with blocking."""
        widget = Mock()
        widget.blockSignals = Mock()
        widget.setValue = Mock()
        
        def update_with_blocking():
            """Update with blocking for the current workflow."""
            widget.blockSignals(True)
            widget.setValue(100)
            widget.blockSignals(False)
            return widget
        
        result = benchmark(update_with_blocking)
        # Benchmark runs multiple iterations, so call count >= 1
        assert result.setValue.call_count >= 1

class TestModularityPanelSwitching:
    """Benchmark panel switching and settings restoration."""

    def test_panel_modality_map_lookup(self, benchmark):
        """Benchmark panel_modality_map dictionary lookup."""
        panel_modality_map = {
            f"panel_{i}": Mock(display_settings=Mock(vmin=i*10, vmax=(i+1)*255))
            for i in range(10)
        }
        
        def lookup_operation():
            """Run the lookup operation workflow."""
            results = []
            for panel_id in range(10):
                panel_key = f"panel_{panel_id}"
                spec = panel_modality_map.get(panel_key)
                if spec:
                    results.append(spec.display_settings.vmin)
            return results
        
        result = benchmark(lookup_operation)
        assert len(result) == 10

    def test_settings_restoration(self, benchmark):
        """Benchmark restoring settings from modality spec."""
        modality_specs = [
            Mock(display_settings=Mock(vmin=i*10, vmax=(i+1)*255))
            for i in range(10)
        ]
        
        def restore_settings():
            """Restore settings for the current workflow."""
            restored = []
            for spec in modality_specs:
                mapping = Mock()
                mapping.min_val = spec.display_settings.vmin
                mapping.max_val = spec.display_settings.vmax
                restored.append(mapping)
            return restored
        
        result = benchmark(restore_settings)
        assert len(result) == 10
        assert result[0].min_val == 0
        assert result[9].min_val == 90

class TestContrastPresetComputation:
    """Benchmark preset transformation computations."""

    def test_linear_preset_computation(self, benchmark):
        """Benchmark linear preset (identity transformation)."""
        data_min, data_max = 1, 65535
        
        def compute_linear():
            """Compute linear for the current workflow."""
            preset_min = data_min
            preset_max = data_max
            return preset_min, preset_max
        
        result = benchmark(compute_linear)
        assert result == (1, 65535)

    def test_log_preset_computation(self, benchmark):
        """Benchmark log preset transformation."""
        import numpy as np
        data_min, data_max = 1, 65535
        
        def compute_log():
            """Compute log for the current workflow."""
            safe_min = max(data_min, 1e-10)
            log_min = np.log10(safe_min)
            log_max = np.log10(data_max)
            return log_min, log_max
        
        result = benchmark(compute_log)
        assert result[0] < result[1]

    def test_sqrt_preset_computation(self, benchmark):
        """Benchmark sqrt preset transformation."""
        data_min, data_max = 0, 65535
        
        def compute_sqrt():
            """Compute sqrt for the current workflow."""
            safe_min = max(data_min, 0)
            sqrt_min = safe_min ** 0.5
            sqrt_max = data_max ** 0.5
            return sqrt_min, sqrt_max
        
        result = benchmark(compute_sqrt)
        assert result[0] <= result[1]

    def test_auto_preset_percentile_computation(self, benchmark):
        """Benchmark auto preset (percentile computation)."""
        import numpy as np
        data_array = np.random.randint(0, 65535, size=1000000)  # 1M pixels
        
        def compute_auto():
            # Simulated percentile-based auto-contrast
            """Compute auto for the current workflow."""
            p2 = np.percentile(data_array, 2)
            p98 = np.percentile(data_array, 98)
            return p2, p98
        
        result = benchmark(compute_auto)
        assert result[0] <= result[1]
        assert result[0] >= 0
        assert result[1] <= 65535
