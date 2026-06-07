"""Split definitions from test_modality_system.py."""


import pytest
from pathlib import Path
from phage_annotator.session.modality import (
    ModalitySpec,
    ModalityDisplaySettings,
    ModalityManager,
    ModalityLinks,
    ProjectionType,
)
from phage_annotator.session.migration import (
    upgrade_to_modalities,
    downgrade_to_primary_support,
    ensure_modality_system,
    get_active_modality_idx,
    get_support_modality_idx,
    MigrationContext,
)
from phage_annotator.core.session_state import SessionState, ImageState


class TestProjectionType:
    """Test ProjectionType enum."""
    
    def test_projection_type_values(self):
        """Verify all projection types are defined."""
        assert ProjectionType.RAW.value == "raw"
        assert ProjectionType.MEAN.value == "mean"
        assert ProjectionType.STD.value == "std"
        assert ProjectionType.MIN.value == "min"
        assert ProjectionType.MAX.value == "max"

class TestModalityDisplaySettings:
    """Test ModalityDisplaySettings dataclass."""
    
    def test_default_settings(self):
        """Default settings should be reasonable."""
        settings = ModalityDisplaySettings()
        assert settings.vmin == 0.0
        assert settings.vmax == 255.0
        assert settings.lut == 0
        assert settings.projection_axis == "t"
        assert settings.gamma == 1.0
    
    def test_custom_settings(self):
        """Custom settings should be preserved."""
        settings = ModalityDisplaySettings(
            vmin=10.0,
            vmax=200.0,
            lut=3,
            projection_axis="z",
            gamma=2.2,
        )
        assert settings.vmin == 10.0
        assert settings.vmax == 200.0
        assert settings.lut == 3
        assert settings.projection_axis == "z"
        assert settings.gamma == 2.2

class TestModalitySpec:
    """Test ModalitySpec dataclass."""
    
    def test_create_modality_spec(self):
        """Create a basic modality spec."""
        spec = ModalitySpec(
            idx=0,
            image_id=0,
            display_name="Modality 1",
        )
        assert spec.idx == 0
        assert spec.image_id == 0
        assert spec.display_name == "Modality 1"
        assert spec.projection_type == ProjectionType.RAW
    
    def test_clone_modality_spec(self):
        """Cloning should create independent copy."""
        original = ModalitySpec(
            idx=1,
            image_id=2,
            display_name="TIRF",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(vmin=50, vmax=200),
        )
        cloned = original.clone()
        
        assert cloned.idx == original.idx
        assert cloned.image_id == original.image_id
        assert cloned.display_name == original.display_name
        assert cloned.projection_type == original.projection_type
        
        # Verify independence (modify clone)
        cloned.display_settings.vmin = 100
        assert original.display_settings.vmin == 50
    
    def test_modality_spec_to_dict(self):
        """Serialization to dict."""
        spec = ModalitySpec(
            idx=0,
            image_id=1,
            display_name="Test",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(vmin=20, vmax=230),
        )
        data = spec.to_dict()
        
        assert data["idx"] == 0
        assert data["image_id"] == 1
        assert data["display_name"] == "Test"
        assert data["projection_type"] == "mean"
        assert data["display_settings"]["vmin"] == 20
        assert data["display_settings"]["vmax"] == 230
    
    def test_modality_spec_from_dict(self):
        """Deserialization from dict."""
        data = {
            "idx": 2,
            "image_id": 3,
            "display_name": "Confocal",
            "projection_type": "std",
            "display_settings": {
                "vmin": 100,
                "vmax": 250,
                "lut": 2,
                "projection_axis": "z",
                "gamma": 2.0,
            },
        }
        spec = ModalitySpec.from_dict(data)
        
        assert spec.idx == 2
        assert spec.image_id == 3
        assert spec.display_name == "Confocal"
        assert spec.projection_type == ProjectionType.STD
        assert spec.display_settings.vmin == 100
        assert spec.display_settings.vmax == 250
        assert spec.display_settings.lut == 2
        assert spec.display_settings.projection_axis == "z"
        assert spec.display_settings.gamma == 2.0
    
    def test_modality_spec_roundtrip(self):
        """Serialization roundtrip should be lossless."""
        original = ModalitySpec(
            idx=5,
            image_id=10,
            display_name="Test Modality",
            projection_type=ProjectionType.MAX,
            display_settings=ModalityDisplaySettings(
                vmin=50,
                vmax=200,
                lut=1,
                projection_axis="t",
                gamma=1.5,
            ),
        )
        
        data = original.to_dict()
        restored = ModalitySpec.from_dict(data)
        
        assert restored.idx == original.idx
        assert restored.image_id == original.image_id
        assert restored.display_name == original.display_name
        assert restored.projection_type == original.projection_type
        assert restored.display_settings.vmin == original.display_settings.vmin
