"""Split definitions from test_modality_persistence.py."""


import pytest
import json
import tempfile
from pathlib import Path
from phage_annotator.session.modality import ModalityManager, ProjectionType, ModalitySpec
from phage_annotator.io.projects.base import SCHEMA_VERSION, save_project, load_project


class TestModalityRoundtrip:
    """Test full save/load roundtrip for modality configurations."""
    
    def test_roundtrip_preserves_modality_settings(self, tmp_path):
        """Full save/load should preserve all modality settings."""
        # Create complex modality setup
        manager = ModalityManager()
        
        mod0 = manager.add_modality(
            image_id=0, custom_name="TIRF", projection_type=ProjectionType.MEAN
        )
        mod0.display_settings.vmin = 50.0
        mod0.display_settings.vmax = 250.0
        mod0.display_settings.gamma = 1.8
        mod0.display_settings.lut = 3
        
        mod1 = manager.add_modality(
            image_id=1, custom_name="Confocal", projection_type=ProjectionType.MAX
        )
        mod1.display_settings.vmin = 0.0
        mod1.display_settings.vmax = 1000.0
        mod1.display_settings.gamma = 1.0
        
        # Link zoom/pan
        manager.set_zoom_pan_link(0, 1, True)
        
        # Save
        project_path = tmp_path / "complex.phageproj"
        
        class MockImage:
            def __init__(self, idx):
                """Initialize the object and prepare its runtime state."""
                self.id = idx
                self.path = str(tmp_path / f"test{idx}.tif")
        
        images = [MockImage(0), MockImage(1)]
        
        save_project(
            project_path,
            images=images,
            annotations={},
            settings={},
            modality_manager=manager,
        )
        
        # Load
        (
            _,
            _,
            _,
            _,
            _,
            _,
            _,
            modality_manager_data,
            channel_display_settings,
        ) = load_project(project_path)
        
        restored = ModalityManager.from_dict(modality_manager_data)
        
        # Verify modality 0
        mod0_restored = restored.get_modality(0)
        assert mod0_restored.display_name == "TIRF"
        assert mod0_restored.projection_type == ProjectionType.MEAN
        assert mod0_restored.display_settings.vmin == 50.0
        assert mod0_restored.display_settings.vmax == 250.0
        assert mod0_restored.display_settings.gamma == 1.8
        assert mod0_restored.display_settings.lut == 3
        
        # Verify modality 1
        mod1_restored = restored.get_modality(1)
        assert mod1_restored.display_name == "Confocal"
        assert mod1_restored.projection_type == ProjectionType.MAX
        assert mod1_restored.display_settings.vmin == 0.0
        assert mod1_restored.display_settings.vmax == 1000.0
        
        # Verify links
        assert restored.are_zoom_pan_linked(0, 1)
    
    def test_roundtrip_with_multiple_modalities(self, tmp_path):
        """Roundtrip with 5+ modalities."""
        manager = ModalityManager()
        
        for i in range(5):
            manager.add_modality(
                image_id=i, custom_name=f"Modality{i}", projection_type=ProjectionType.RAW
            )
        
        project_path = tmp_path / "multi.phageproj"
        
        class MockImage:
            def __init__(self, idx):
                """Initialize the object and prepare its runtime state."""
                self.id = idx
                self.path = str(tmp_path / f"test{idx}.tif")
        
        images = [MockImage(i) for i in range(5)]
        
        save_project(
            project_path,
            images=images,
            annotations={},
            settings={},
            modality_manager=manager,
        )
        
        (
            _,
            _,
            _,
            _,
            _,
            _,
            _,
            modality_manager_data,
            channel_display_settings,
        ) = load_project(project_path)
        
        restored = ModalityManager.from_dict(modality_manager_data)
        assert restored.modality_count() == 5
        
        for i in range(5):
            assert restored.get_modality(i).display_name == f"Modality{i}"
