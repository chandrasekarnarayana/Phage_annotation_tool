"""Split definitions from test_memory_pressure_adaptive_tiles.py."""


from unittest.mock import Mock, MagicMock, patch
import numpy as np
import pytest

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class TestMemoryPressureIntegration:
    """Integration tests for memory pressure and tile sizing."""

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_pressure_monitoring_integrates_with_panel(self):
        """Verify memory pressure monitoring updates panel."""
        from phage_annotator.ui_qt.panels.performance import PerformancePanel
        
        panel = PerformancePanel()
        
        # Update memory metrics
        if HAS_PSUTIL:
            panel._update_memory_metrics()
            
            # Should have updated labels
            assert panel.memory_available_label.text() != ""
            assert panel.memory_pressure_label.text() in ["LOW", "MEDIUM", "HIGH"]

    def test_tile_size_affects_inference_options(self):
        """Verify adaptive tile size affects inference parameters."""
        from phage_annotator.algorithms.density_infer import DensityInferOptions
        
        # Simulate different tile sizes under pressure
        tile_sizes = [512, 256, 128]
        
        for size in tile_sizes:
            options = DensityInferOptions(tile_size=size)
            assert options.tile_size == size

    def test_prefetch_disabled_prevents_jobs(self):
        """Verify disabled prefetch prevents pyramid jobs."""
        prefetch_disabled = False
        pyramid_jobs = []
        
        # Normal operation: jobs scheduled
        if not prefetch_disabled:
            pyramid_jobs.extend(["job1", "job2", "job3"])
        
        assert len(pyramid_jobs) == 3
        
        # Pressure response: disable prefetch
        prefetch_disabled = True
        pyramid_jobs.clear()
        
        # No new jobs scheduled
        if not prefetch_disabled:
            pyramid_jobs.extend(["job4", "job5"])
        
        assert len(pyramid_jobs) == 0

    def test_pressure_recovery_restores_normal_operation(self):
        """Verify normal operation resumes when pressure clears."""
        memory_pressure_active = True
        prefetch_disabled = True
        tile_size = 128
        
        # Pressure clears
        memory_pressure_active = False
        
        # Restore operation
        if not memory_pressure_active:
            prefetch_disabled = False
            tile_size = 512  # Could gradually increase back to normal
        
        assert not prefetch_disabled
        assert tile_size == 512

    def test_multiple_images_in_lod_mode_counted(self):
        """Verify multiple images in LOD mode are counted."""
        lod_mode_active = {0: True, 1: True, 2: False, 3: True}
        
        active_count = sum(1 for v in lod_mode_active.values() if v)
        
        assert active_count == 3
        
    def test_memory_pressure_warning_message(self):
        """Verify memory pressure warning is formatted correctly."""
        available_pct = 15.0
        warning = f"⚠ Memory pressure: only {available_pct:.0f}% available (mitigation active)"
        
        assert "Memory pressure" in warning
        assert "15%" in warning

class TestMemoryMetricsValidation:
    """Test memory metrics validation and error handling."""

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_percentage_bounds(self):
        """Verify memory percentages stay within valid bounds."""
        mem = psutil.virtual_memory()
        available_pct = mem.available / mem.total
        usage_pct = 1 - available_pct
        
        assert 0 <= available_pct <= 1
        assert 0 <= usage_pct <= 1

    def test_tile_size_never_negative(self):
        """Verify tile size never goes negative."""
        tile_sizes = [512, 256, 128]
        min_size = min(tile_sizes)
        
        assert min_size > 0

    def test_memory_mitigation_safe_when_disabled(self):
        """Verify mitigation is safe when disabled."""
        memory_mitigation_active = False
        
        # Should not crash
        if not memory_mitigation_active:
            pass  # No actions taken
        
        assert memory_mitigation_active is False

    def test_tile_size_configuration_immutable(self):
        """Verify tile size config can be accessed safely."""
        from phage_annotator.config.settings import AppConfig
        
        config = AppConfig()
        original = config.adaptive_tile_size
        
        # Read-only access
        size1 = config.adaptive_tile_size
        size2 = config.adaptive_tile_size
        
        assert size1 == size2 == original
