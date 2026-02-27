"""Tests for modality configuration persistence.

This module validates:
- Saving modality_manager to .phageproj files
- Loading modality_manager from .phageproj files
- Backward compatibility (projects without modality_manager)
- Schema versioning
"""

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
