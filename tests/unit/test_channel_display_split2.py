"""Split definitions from test_channel_display.py."""


import json
import pytest
import numpy as np
from pathlib import Path

from phage_annotator.data.channel_display import (
    BlendMode,
    ChannelDisplayState,
    MultiChannelDisplaySettings,
    BLEND_MODE_NAMES,
)
from phage_annotator.ui_qt.rendering.blend_modes import (
    blend_normal,
    blend_overlay,
    blend_screen,
    blend_multiply,
    blend_add,
    blend_subtract,
    composite_channels,
    apply_per_channel_opacity,
)
from phage_annotator.io.projects.base import load_project, save_project


class TestCompositeChannels:
    """Test channel compositing."""
    
    def test_composite_single_channel(self):
        """Test compositing a single channel."""
        ch1 = np.array([[0.5, 0.7]], dtype=np.float32)
        
        result = composite_channels([(ch1, 1.0)], blend_mode=BlendMode.NORMAL)
        np.testing.assert_array_almost_equal(result, ch1)
    
    def test_composite_two_channels_normal(self):
        """Test compositing two channels with normal blend."""
        ch1 = np.array([[0.2, 0.3]], dtype=np.float32)
        ch2 = np.array([[0.5, 0.6]], dtype=np.float32)
        
        result = composite_channels(
            [(ch1, 1.0), (ch2, 1.0)],
            blend_mode=BlendMode.NORMAL,
        )
        # With normal blend and both at full opacity, result should be ch2
        np.testing.assert_array_almost_equal(result, ch2)

    def test_composite_screen_with_data_enum(self):
        """Data-layer BlendMode should resolve to rendering screen blend."""
        ch1 = np.array([[0.5, 0.5]], dtype=np.float32)
        ch2 = np.array([[0.5, 0.5]], dtype=np.float32)

        result = composite_channels(
            [(ch1, 1.0), (ch2, 1.0)],
            blend_mode=BlendMode.SCREEN,
        )
        expected = np.array([[0.75, 0.75]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_composite_with_opacity(self):
        """Test compositing with per-channel opacity."""
        ch1 = np.array([[0.0]], dtype=np.float32)
        ch2 = np.array([[1.0]], dtype=np.float32)
        
        result = composite_channels(
            [(ch1, 1.0), (ch2, 0.5)],
            blend_mode=BlendMode.NORMAL,
        )
        # Result should be 0.5 (0.0 + 1.0 * 0.5)
        expected = np.array([[0.5]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_composite_normalization(self):
        """Test that normalize_output clips to [0, 1]."""
        ch1 = np.array([[0.8]], dtype=np.float32)
        ch2 = np.array([[0.8]], dtype=np.float32)
        
        result = composite_channels(
            [(ch1, 1.0), (ch2, 1.0)],
            blend_mode=BlendMode.ADD,
            normalize_output=True,
        )
        # Should be clipped to 1.0
        assert np.all(result <= 1.0)
        assert np.all(result >= 0.0)
    
    def test_apply_per_channel_opacity(self):
        """Test applying per-channel opacity."""
        channels = [
            np.array([[1.0, 1.0]], dtype=np.float32),
            np.array([[1.0, 1.0]], dtype=np.float32),
            np.array([[1.0, 1.0]], dtype=np.float32),
        ]
        opacities = [1.0, 0.5, 0.0]
        
        result = apply_per_channel_opacity(channels, opacities)
        assert len(result) == 3
        np.testing.assert_array_almost_equal(result[0], channels[0])
        np.testing.assert_array_almost_equal(result[1], 0.5 * channels[1])
        np.testing.assert_array_almost_equal(result[2], 0.0 * channels[2])

class TestProjectPersistence:
    """Test project save/load with channel display settings."""
    
    def test_save_and_load_channel_settings(self, tmp_path):
        """Test that channel settings are persisted in projects."""
        project_path = tmp_path / "test.phageproj"
        
        # Create mock image
        class MockImage:
            def __init__(self):
                """Initialize the object and prepare its runtime state."""
                self.id = 0
                self.path = str(tmp_path / "test.tif")
        
        # Create channel settings
        channels = [
            ChannelDisplayState(channel_idx=0, opacity=0.5, lut=1),
            ChannelDisplayState(channel_idx=1, opacity=0.8, lut=2),
        ]
        channel_settings = MultiChannelDisplaySettings(
            channel_count=2,
            channels=channels,
            blend_mode=BlendMode.SCREEN,
        )
        
        # Save project
        save_project(
            project_path,
            images=[MockImage()],
            annotations={},
            settings={},
            channel_display_settings=channel_settings.to_dict(),
        )
        
        # Load project
        (
            images,
            settings,
            ann_map,
            roi_map,
            thr_map,
            part_map,
            import_map,
            modality_manager_data,
            loaded_channel_settings,
        ) = load_project(project_path)
        
        # Verify channel settings were loaded
        assert loaded_channel_settings is not None
        assert loaded_channel_settings["channel_count"] == 2
        assert len(loaded_channel_settings["channels"]) == 2
        assert loaded_channel_settings["blend_mode"] == "screen"
    
    def test_load_project_without_channel_settings(self, tmp_path):
        """Test loading legacy project without channel settings."""
        project_path = tmp_path / "legacy.phageproj"
        
        # Create legacy project (no channel_display_settings)
        legacy_data = {
            "tool": "PhageAnnotator",
            "version": "0.9.0",
            "schema_version": 3,
            "images": [{"path": "test.tif"}],
            "settings": {},
        }
        
        with project_path.open("w") as f:
            json.dump(legacy_data, f)
        
        # Load should succeed with None for channel_display_settings
        (
            images,
            settings,
            ann_map,
            roi_map,
            thr_map,
            part_map,
            import_map,
            modality_manager_data,
            loaded_channel_settings,
        ) = load_project(project_path)
        
        assert loaded_channel_settings is None

class TestBlendModeNames:
    """Test blend mode enumeration and naming."""
    
    def test_all_blend_modes_have_names(self):
        """Test that all blend modes have display names."""
        for mode in BlendMode:
            assert mode in BLEND_MODE_NAMES
            assert BLEND_MODE_NAMES[mode]  # Non-empty string
    
    def test_blend_mode_values(self):
        """Test blend mode enum values."""
        assert BlendMode.NORMAL.value == "normal"
        assert BlendMode.OVERLAY.value == "overlay"
        assert BlendMode.SCREEN.value == "screen"
        assert BlendMode.MULTIPLY.value == "multiply"
        assert BlendMode.ADD.value == "add"
        assert BlendMode.SUBTRACT.value == "subtract"
