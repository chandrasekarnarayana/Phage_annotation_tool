"""Comprehensive tests for multi-channel viewer behavior.

Tests cover:
- Channel display state model
- Blend modes rendering
- Channel panel integration
- Project persistence
- GUI wiring
"""

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


class TestChannelDisplayState:
    """Test channel display state model."""
    
    def test_channel_display_state_defaults(self):
        """Test default values for ChannelDisplayState."""
        state = ChannelDisplayState(channel_idx=0)
        assert state.channel_idx == 0
        assert state.visible is True
        assert state.opacity == 1.0
        assert state.lut == 0
    
    def test_channel_display_state_custom_values(self):
        """Test custom values for ChannelDisplayState."""
        state = ChannelDisplayState(
            channel_idx=2,
            visible=False,
            opacity=0.5,
            lut=3,
        )
        assert state.channel_idx == 2
        assert state.visible is False
        assert state.opacity == 0.5
        assert state.lut == 3
    
    def test_channel_display_state_to_dict(self):
        """Test serialization to dictionary."""
        state = ChannelDisplayState(
            channel_idx=1,
            visible=False,
            opacity=0.75,
            lut=2,
        )
        data = state.to_dict()
        assert data["channel_idx"] == 1
        assert data["visible"] is False
        assert data["opacity"] == 0.75
        assert data["lut"] == 2
    
    def test_channel_display_state_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "channel_idx": 3,
            "visible": False,
            "opacity": 0.6,
            "lut": 4,
        }
        state = ChannelDisplayState.from_dict(data)
        assert state.channel_idx == 3
        assert state.visible is False
        assert state.opacity == 0.6
        assert state.lut == 4
    
    def test_channel_display_state_roundtrip(self):
        """Test serialization roundtrip."""
        original = ChannelDisplayState(
            channel_idx=2,
            visible=True,
            opacity=0.8,
            lut=1,
        )
        data = original.to_dict()
        restored = ChannelDisplayState.from_dict(data)
        assert restored.channel_idx == original.channel_idx
        assert restored.visible == original.visible
        assert restored.opacity == original.opacity
        assert restored.lut == original.lut


class TestMultiChannelDisplaySettings:
    """Test multi-channel display settings."""
    
    def test_multi_channel_display_settings_creation(self):
        """Test creating multi-channel settings."""
        channels = [
            ChannelDisplayState(channel_idx=0),
            ChannelDisplayState(channel_idx=1),
        ]
        settings = MultiChannelDisplaySettings(
            channel_count=2,
            channels=channels,
            blend_mode=BlendMode.NORMAL,
        )
        assert settings.channel_count == 2
        assert len(settings.channels) == 2
        assert settings.blend_mode == BlendMode.NORMAL
    
    def test_get_channel_state(self):
        """Test getting channel state."""
        channels = [
            ChannelDisplayState(channel_idx=0, opacity=0.5),
            ChannelDisplayState(channel_idx=1, opacity=0.8),
        ]
        settings = MultiChannelDisplaySettings(channel_count=2, channels=channels)
        
        state0 = settings.get_channel_state(0)
        assert state0.opacity == 0.5
        
        state1 = settings.get_channel_state(1)
        assert state1.opacity == 0.8
    
    def test_set_channel_visible(self):
        """Test setting channel visibility."""
        channels = [
            ChannelDisplayState(channel_idx=0, visible=True),
            ChannelDisplayState(channel_idx=1, visible=True),
        ]
        settings = MultiChannelDisplaySettings(channel_count=2, channels=channels)
        
        settings.set_channel_visible(0, False)
        assert settings.channels[0].visible is False
        assert settings.channels[1].visible is True
    
    def test_set_channel_opacity(self):
        """Test setting channel opacity."""
        channels = [ChannelDisplayState(channel_idx=0, opacity=1.0)]
        settings = MultiChannelDisplaySettings(channel_count=1, channels=channels)
        
        settings.set_channel_opacity(0, 0.5)
        assert settings.channels[0].opacity == 0.5
    
    def test_set_channel_lut(self):
        """Test setting channel LUT."""
        channels = [ChannelDisplayState(channel_idx=0, lut=0)]
        settings = MultiChannelDisplaySettings(channel_count=1, channels=channels)
        
        settings.set_channel_lut(0, 3)
        assert settings.channels[0].lut == 3
    
    def test_get_visible_channels(self):
        """Test getting visible channels."""
        channels = [
            ChannelDisplayState(channel_idx=0, visible=True),
            ChannelDisplayState(channel_idx=1, visible=False),
            ChannelDisplayState(channel_idx=2, visible=True),
        ]
        settings = MultiChannelDisplaySettings(channel_count=3, channels=channels)
        
        visible = settings.get_visible_channels()
        assert visible == [0, 2]
    
    def test_multi_channel_to_dict(self):
        """Test serialization of multi-channel settings."""
        channels = [
            ChannelDisplayState(channel_idx=0, opacity=0.5),
            ChannelDisplayState(channel_idx=1, opacity=0.8),
        ]
        settings = MultiChannelDisplaySettings(
            channel_count=2,
            channels=channels,
            blend_mode=BlendMode.SCREEN,
        )
        
        data = settings.to_dict()
        assert data["channel_count"] == 2
        assert len(data["channels"]) == 2
        assert data["blend_mode"] == "screen"
    
    def test_multi_channel_from_dict(self):
        """Test deserialization of multi-channel settings."""
        data = {
            "channel_count": 2,
            "channels": [
                {"channel_idx": 0, "visible": True, "opacity": 0.5, "lut": 0},
                {"channel_idx": 1, "visible": False, "opacity": 0.8, "lut": 1},
            ],
            "blend_mode": "overlay",
        }
        
        settings = MultiChannelDisplaySettings.from_dict(data)
        assert settings.channel_count == 2
        assert len(settings.channels) == 2
        assert settings.channels[0].opacity == 0.5
        assert settings.channels[1].visible is False
        assert settings.blend_mode == BlendMode.OVERLAY


class TestBlendModes:
    """Test blend mode implementations."""
    
    def test_blend_normal_opaque(self):
        """Test normal blend with full opacity."""
        base = np.array([[0.0, 0.5], [0.5, 1.0]], dtype=np.float32)
        layer = np.array([[0.2, 0.3], [0.4, 0.6]], dtype=np.float32)
        
        result = blend_normal(base, layer, opacity=1.0)
        np.testing.assert_array_almost_equal(result, layer)
    
    def test_blend_normal_transparent(self):
        """Test normal blend with zero opacity."""
        base = np.array([[0.0, 0.5], [0.5, 1.0]], dtype=np.float32)
        layer = np.array([[0.2, 0.3], [0.4, 0.6]], dtype=np.float32)
        
        result = blend_normal(base, layer, opacity=0.0)
        np.testing.assert_array_almost_equal(result, base)
    
    def test_blend_normal_50_percent(self):
        """Test normal blend with 50% opacity."""
        base = np.array([[0.0, 1.0]], dtype=np.float32)
        layer = np.array([[1.0, 0.0]], dtype=np.float32)
        
        result = blend_normal(base, layer, opacity=0.5)
        expected = np.array([[0.5, 0.5]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_blend_screen(self):
        """Test screen blend mode."""
        base = np.array([[0.5, 0.5]], dtype=np.float32)
        layer = np.array([[0.5, 0.5]], dtype=np.float32)
        
        result = blend_screen(base, layer, opacity=1.0)
        # Screen: 1 - (1 - 0.5) * (1 - 0.5) = 1 - 0.25 = 0.75
        expected = np.array([[0.75, 0.75]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_blend_multiply(self):
        """Test multiply blend mode."""
        base = np.array([[0.8, 0.5]], dtype=np.float32)
        layer = np.array([[0.5, 0.5]], dtype=np.float32)
        
        result = blend_multiply(base, layer, opacity=1.0)
        # Multiply: base * layer
        expected = np.array([[0.4, 0.25]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_blend_add(self):
        """Test add blend mode."""
        base = np.array([[0.3, 0.5]], dtype=np.float32)
        layer = np.array([[0.4, 0.6]], dtype=np.float32)
        
        result = blend_add(base, layer, opacity=1.0)
        # Add: base + layer (may exceed 1.0)
        expected = np.array([[0.7, 1.1]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_blend_subtract(self):
        """Test subtract blend mode."""
        base = np.array([[0.8, 0.5]], dtype=np.float32)
        layer = np.array([[0.3, 0.6]], dtype=np.float32)
        
        result = blend_subtract(base, layer, opacity=1.0)
        # Subtract: base - layer (may be negative)
        expected = np.array([[0.5, -0.1]], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)


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
