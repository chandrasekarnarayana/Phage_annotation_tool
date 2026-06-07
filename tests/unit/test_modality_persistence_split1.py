"""Split definitions from test_modality_persistence.py."""


import pytest
import json
import tempfile
from pathlib import Path
from phage_annotator.session.modality import ModalityManager, ProjectionType, ModalitySpec
from phage_annotator.io.projects.base import SCHEMA_VERSION, save_project, load_project


class TestModalityPersistence:
    """Test modality configuration save/load."""
    
    def test_modality_manager_to_dict(self):
        """ModalityManager should serialize to dict."""
        manager = ModalityManager()
        mod0 = manager.add_modality(image_id=0, custom_name="TIRF")
        mod1 = manager.add_modality(image_id=1, custom_name="Confocal")
        
        data = manager.to_dict()
        
        assert "modalities" in data
        assert len(data["modalities"]) == 2
        assert data["modalities"][0]["display_name"] == "TIRF"
        assert data["modalities"][1]["display_name"] == "Confocal"
        assert "links" in data
        assert "_next_idx" in data
    
    def test_modality_manager_from_dict_reconstruction(self):
        """ModalityManager should reconstruct from dict."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="TIRF")
        manager.add_modality(image_id=1, custom_name="Confocal")
        
        data = manager.to_dict()
        restored = ModalityManager.from_dict(data)
        
        assert restored.modality_count() == 2
        assert restored.get_modality(0).display_name == "TIRF"
        assert restored.get_modality(1).display_name == "Confocal"
    
    def test_modality_spec_serialization(self):
        """ModalitySpec should serialize display_settings."""
        spec = ModalitySpec(
            idx=0,
            image_id=5,
            display_name="Test Mode",
            projection_type=ProjectionType.MEAN,
        )
        spec.display_settings.vmin = 100.0
        spec.display_settings.vmax = 500.0
        spec.display_settings.gamma = 1.5
        
        data = spec.to_dict()
        
        assert data["display_name"] == "Test Mode"
        assert data["projection_type"] == "mean"
        assert data["display_settings"]["vmin"] == 100.0
        assert data["display_settings"]["vmax"] == 500.0
        assert data["display_settings"]["gamma"] == 1.5
    
    def test_modality_spec_deserialization(self):
        """ModalitySpec should restore from dict."""
        data = {
            "idx": 0,
            "image_id": 5,
            "display_name": "Test Mode",
            "projection_type": "mean",
            "display_settings": {
                "vmin": 100.0,
                "vmax": 500.0,
                "lut": 2,
                "projection_axis": "z",
                "gamma": 1.5,
            },
        }
        
        spec = ModalitySpec.from_dict(data)
        
        assert spec.display_name == "Test Mode"
        assert spec.projection_type == ProjectionType.MEAN
        assert spec.display_settings.vmin == 100.0
        assert spec.display_settings.vmax == 500.0
        assert spec.display_settings.gamma == 1.5

class TestProjectPersistence:
    """Test modality persistence in .phageproj files."""
    
    def test_save_project_with_modality_manager(self, tmp_path):
        """save_project should include modality_manager in JSON."""
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="TIRF")
        manager.add_modality(image_id=1, custom_name="Confocal")
        
        project_path = tmp_path / "test.phageproj"
        
        # Create mock image
        class MockImage:
            def __init__(self):
                """Initialize the object and prepare its runtime state."""
                self.id = 0
                self.path = str(tmp_path / "test.tif")
        
        images = [MockImage()]
        
        save_project(
            project_path,
            images=images,
            annotations={},
            settings={"fps": 10},
            modality_manager=manager,
        )
        
        # Verify file structure
        with project_path.open("r") as f:
            data = json.load(f)
        
        assert "modality_manager" in data
        assert "schema_version" in data
        assert data["schema_version"] == SCHEMA_VERSION
        assert len(data["modality_manager"]["modalities"]) == 2
    
    def test_load_project_with_modality_manager(self, tmp_path):
        """load_project should restore modality_manager."""
        # Create project with modality_manager
        manager = ModalityManager()
        manager.add_modality(image_id=0, custom_name="TIRF")
        manager.add_modality(image_id=1, custom_name="Confocal")
        
        project_path = tmp_path / "test.phageproj"
        
        class MockImage:
            def __init__(self):
                """Initialize the object and prepare its runtime state."""
                self.id = 0
                self.path = str(tmp_path / "test.tif")
        
        images = [MockImage()]
        
        save_project(
            project_path,
            images=images,
            annotations={},
            settings={"fps": 10},
            modality_manager=manager,
        )
        
        # Load project
        (
            image_entries,
            settings,
            ann_map,
            roi_map,
            thr_map,
            part_map,
            import_map,
            modality_manager_data,
            channel_display_settings,
        ) = load_project(project_path)
        
        assert modality_manager_data is not None
        assert len(modality_manager_data["modalities"]) == 2
        
        # Reconstruct ModalityManager
        restored_manager = ModalityManager.from_dict(modality_manager_data)
        assert restored_manager.modality_count() == 2
        assert restored_manager.get_modality(0).display_name == "TIRF"
        assert restored_manager.get_modality(1).display_name == "Confocal"
    
    def test_load_legacy_project_without_modality_manager(self, tmp_path):
        """Loading legacy project should gracefully handle missing modality_manager."""
        # Create legacy project file (schema v1, no modality_manager)
        project_path = tmp_path / "legacy.phageproj"
        legacy_data = {
            "tool": "PhageAnnotator",
            "version": "0.8.0",
            "images": [],
            "settings": {"fps": 12},
        }
        
        with project_path.open("w") as f:
            json.dump(legacy_data, f)
        
        # Load should succeed with modality_manager_data=None
        (
            image_entries,
            settings,
            ann_map,
            roi_map,
            thr_map,
            part_map,
            import_map,
            modality_manager_data,
            channel_display_settings,
        ) = load_project(project_path)
        
        assert modality_manager_data is None  # Backward compatible
        assert settings["fps"] == 12
    
    def test_save_project_without_modality_manager(self, tmp_path):
        """save_project should work when modality_manager=None."""
        project_path = tmp_path / "no_modality.phageproj"
        
        class MockImage:
            def __init__(self):
                """Initialize the object and prepare its runtime state."""
                self.id = 0
                self.path = str(tmp_path / "test.tif")
        
        images = [MockImage()]
        
        save_project(
            project_path,
            images=images,
            annotations={},
            settings={"fps": 10},
            modality_manager=None,
        )
        
        # Verify modality_manager not in file
        with project_path.open("r") as f:
            data = json.load(f)
        
        # Should still save schema_version but no modality_manager
        assert "schema_version" in data
        assert "modality_manager" not in data
