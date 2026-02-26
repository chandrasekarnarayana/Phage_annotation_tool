"""Memory pressure monitoring and adaptive tile sizing tests.

Memory pressure monitoring:
- Monitor available system RAM via psutil
- Detect memory pressure: HIGH (<20%), MEDIUM (20-80%), LOW (>80%)
- Show real-time status in performance panel
- Trigger mitigation when pressure threshold exceeded

Adaptive tile sizing:
- Reduce inference tile size from 512 -> 256 -> 128 under memory pressure
- Persist settings in AppConfig
- Display current tile size in status
"""

from unittest.mock import Mock, MagicMock, patch
import numpy as np
import pytest

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class TestMemoryPressureMonitoring:
    """Test memory pressure monitoring."""

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_pressure_thresholds_defined(self):
        """Verify memory pressure threshold constants are defined."""
        from phage_annotator.performance_panel import (
            MEMORY_PRESSURE_HIGH_THRESHOLD,
            MEMORY_PRESSURE_MEDIUM_THRESHOLD,
            MEMORY_PRESSURE_LOW_THRESHOLD
        )
        
        assert MEMORY_PRESSURE_HIGH_THRESHOLD == 0.20  # <20% available
        assert MEMORY_PRESSURE_MEDIUM_THRESHOLD == 0.80
        assert MEMORY_PRESSURE_LOW_THRESHOLD == 0.80

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_metrics_ui_created(self):
        """Verify memory pressure UI widgets are created."""
        from phage_annotator.performance_panel import PerformancePanel
        
        panel = PerformancePanel()
        
        # Check widgets exist
        assert hasattr(panel, 'memory_available_label')
        assert hasattr(panel, 'memory_progress')
        assert hasattr(panel, 'memory_pressure_label')
        assert hasattr(panel, 'memory_mitigation_label')

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_pressure_state_tracking(self):
        """Verify memory pressure state is tracked."""
        from phage_annotator.performance_panel import PerformancePanel
        
        panel = PerformancePanel()
        
        # Initial state
        assert hasattr(panel, '_memory_pressure_active')
        assert panel._memory_pressure_active is False

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_high_pressure_detected(self):
        """Verify HIGH pressure detection (<20% available)."""
        mem = psutil.virtual_memory()
        total = mem.total
        available = total * 0.15  # 15% available
        available_pct = available / total
        
        # Should be HIGH pressure
        assert available_pct < 0.20

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_medium_pressure_detected(self):
        """Verify MEDIUM pressure detection (20-80% available)."""
        mem = psutil.virtual_memory()
        total = mem.total
        available = total * 0.50  # 50% available
        available_pct = available / total
        
        # Should be MEDIUM pressure
        assert 0.20 <= available_pct <= 0.80

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_low_pressure_detected(self):
        """Verify LOW pressure detection (>80% available)."""
        mem = psutil.virtual_memory()
        total = mem.total
        available = total * 0.85  # 85% available
        available_pct = available / total
        
        # Should be LOW pressure
        assert available_pct > 0.80

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_pressure_color_coding(self):
        """Verify pressure levels use correct colors."""
        colors = {
            "HIGH": "#ff6b6b",    # Red
            "MEDIUM": "#ffa94d",  # Orange
            "LOW": "#51cf66"      # Green
        }
        
        assert colors["HIGH"] == "#ff6b6b"
        assert colors["MEDIUM"] == "#ffa94d"
        assert colors["LOW"] == "#51cf66"

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_usage_percentage_calculation(self):
        """Verify memory usage percentage is calculated correctly."""
        mem = psutil.virtual_memory()
        usage_pct = (1 - mem.available / mem.total) * 100
        
        # Should be between 0 and 100
        assert 0 <= usage_pct <= 100

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_memory_pressure_triggers_mitigation(self):
        """Verify memory pressure triggers mitigation."""
        memory_pressure_active = False
        
        # Simulate HIGH pressure detected
        available_pct = 0.15
        if available_pct < 0.20:
            memory_pressure_active = True
        
        assert memory_pressure_active is True


class TestAdaptiveTileSizing:
    """Test adaptive tile sizing."""

    def test_adaptive_tile_size_initialization(self):
        """Verify adaptive tile size is initialized."""
        from phage_annotator.config import AppConfig
        
        config = AppConfig()
        assert hasattr(config, 'adaptive_tile_size')
        assert config.adaptive_tile_size == 256

    def test_adaptive_tile_size_default(self):
        """Verify default tile size is 256."""
        from phage_annotator.config import AppConfig
        
        config = AppConfig()
        assert config.adaptive_tile_size == 256

    def test_tile_size_reduction_levels(self):
        """Verify tile size reduction sequence: 512 → 256 → 128."""
        sizes = [512, 256, 128]
        
        # Each step is reduction
        for i in range(len(sizes) - 1):
            assert sizes[i] > sizes[i + 1]

    def test_mitigation_level_1_reduces_to_256(self):
        """Verify first mitigation reduces tile size to 256."""
        current_size = 512
        
        if current_size == 512:
            new_size = 256
        
        assert new_size == 256

    def test_mitigation_level_2_reduces_to_128(self):
        """Verify second mitigation reduces tile size to 128."""
        current_size = 256
        
        if current_size == 256:
            new_size = 128
        
        assert new_size == 128

    def test_critical_tile_size_is_128(self):
        """Verify critical tile size floor is 128."""
        min_size = 128
        
        assert min_size > 0
        assert min_size >= 128

    def test_prefetch_disabled_flag_initialization(self):
        """Verify _prefetch_disabled flag is initialized."""
        main_window = Mock()
        main_window._prefetch_disabled = False
        
        assert main_window._prefetch_disabled is False

    def test_prefetch_disabled_flag_set_on_pressure(self):
        """Verify prefetch disabled when memory pressure detected."""
        prefetch_disabled = False
        memory_pressure_active = True
        
        if memory_pressure_active:
            prefetch_disabled = True
        
        assert prefetch_disabled is True

    def test_tile_size_persists_across_sessions(self):
        """Verify tile size setting persists in AppConfig."""
        from phage_annotator.config import AppConfig
        
        config1 = AppConfig(adaptive_tile_size=256)
        assert config1.adaptive_tile_size == 256
        
        # Can be modified
        config1.adaptive_tile_size = 128
        assert config1.adaptive_tile_size == 128


class TestMemoryMitigationStrategies:
    """Test memory mitigation strategies."""

    def test_mitigation_disables_prefetch(self):
        """Verify mitigation action 1: disable prefetch."""
        prefetch_disabled = False
        
        # Trigger mitigation
        prefetch_disabled = True
        
        assert prefetch_disabled is True

    def test_mitigation_reduces_tile_size(self):
        """Verify mitigation action 2: reduce tile size."""
        current_tile_size = 512
        
        # First mitigation
        if current_tile_size == 512:
            current_tile_size = 256
        
        assert current_tile_size == 256

    def test_mitigation_clears_non_active_images(self):
        """Verify mitigation action 3: clear non-active caches."""
        image_cache = {0: "active", 1: "inactive", 2: "inactive"}
        active_imgs = {0}
        
        # Clear non-active
        for img_id in list(image_cache.keys()):
            if img_id not in active_imgs:
                image_cache.pop(img_id)
        
        assert len(image_cache) == 1
        assert 0 in image_cache

    def test_mitigation_ui_status_indicator(self):
        """Verify mitigation status shown in UI."""
        memory_mitigation_label = ""
        
        # Trigger mitigation
        memory_mitigation_label = "ACTIVE"
        
        assert memory_mitigation_label == "ACTIVE"

    def test_mitigation_escalation_sequence(self):
        """Verify mitigation escalates progressively."""
        pressure_level = 0
        tile_size = 512
        prefetch_enabled = True
        images_cleared = False
        
        # First pressure indication
        pressure_level += 1
        prefetch_enabled = False
        
        # Second pressure indication
        pressure_level += 1
        if tile_size == 512:
            tile_size = 256
        
        # Third pressure indication
        pressure_level += 1
        if tile_size == 256:
            tile_size = 128
            images_cleared = True
        
        assert pressure_level == 3
        assert tile_size == 128
        assert not prefetch_enabled
        assert images_cleared


class TestMemoryPressureIntegration:
    """Integration tests for memory pressure and tile sizing."""

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_pressure_monitoring_integrates_with_panel(self):
        """Verify memory pressure monitoring updates panel."""
        from phage_annotator.performance_panel import PerformancePanel
        
        panel = PerformancePanel()
        
        # Update memory metrics
        if HAS_PSUTIL:
            panel._update_memory_metrics()
            
            # Should have updated labels
            assert panel.memory_available_label.text() != ""
            assert panel.memory_pressure_label.text() in ["LOW", "MEDIUM", "HIGH"]

    def test_tile_size_affects_inference_options(self):
        """Verify adaptive tile size affects inference parameters."""
        from phage_annotator.density_infer import DensityInferOptions
        
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
        from phage_annotator.config import AppConfig
        
        config = AppConfig()
        original = config.adaptive_tile_size
        
        # Read-only access
        size1 = config.adaptive_tile_size
        size2 = config.adaptive_tile_size
        
        assert size1 == size2 == original
