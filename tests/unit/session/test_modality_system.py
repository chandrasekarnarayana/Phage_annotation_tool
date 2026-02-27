"""Tests for multi-modality system and backward compatibility.

Phase α: Comprehensive testing of modality spec, manager, and migration.
"""

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


class TestModalityManager:
    """Test ModalityManager core functionality."""
    
    def test_create_empty_manager(self):
        """Create empty manager."""
        manager = ModalityManager()
        assert manager.modality_count() == 0
        assert manager.get_all_modalities() == []
    
    def test_add_single_modality(self):
        """Add single image as modality."""
        manager = ModalityManager()
        modality = manager.add_modality(0, "Test Modality")
        
        assert modality.idx == 0
        assert modality.image_id == 0
        assert modality.display_name == "Test Modality"
        assert manager.modality_count() == 1
    
    def test_add_multiple_modalities(self):
        """Add multiple modalities."""
        manager = ModalityManager()
        mod1 = manager.add_modality(0, "Modality 1")
        mod2 = manager.add_modality(1, "Modality 2")
        mod3 = manager.add_modality(2, "Modality 3")
        
        assert manager.modality_count() == 3
        assert mod1.idx == 0
        assert mod2.idx == 1
        assert mod3.idx == 2
    
    def test_auto_name_generation(self):
        """Auto-generate modality names if not provided."""
        manager = ModalityManager()
        mod1 = manager.add_modality(0)
        mod2 = manager.add_modality(1)
        
        assert mod1.display_name == "Modality 1"
        assert mod2.display_name == "Modality 2"
    
    def test_get_modality_by_idx(self):
        """Retrieve modality by index."""
        manager = ModalityManager()
        added = manager.add_modality(0, "Test")
        
        retrieved = manager.get_modality(0)
        assert retrieved is not None
        assert retrieved.display_name == "Test"
        
        not_found = manager.get_modality(999)
        assert not_found is None
    
    def test_remove_modality(self):
        """Remove modality."""
        manager = ModalityManager()
        manager.add_modality(0, "Mod 1")
        manager.add_modality(1, "Mod 2")
        manager.add_modality(2, "Mod 3")
        
        assert manager.modality_count() == 3
        
        success = manager.remove_modality(1)
        assert success is True
        assert manager.modality_count() == 2
        assert manager.get_modality(1) is None
        
        success = manager.remove_modality(999)
        assert success is False
        assert manager.modality_count() == 2
    
    def test_rename_modality(self):
        """Rename modality."""
        manager = ModalityManager()
        manager.add_modality(0, "Old Name")
        
        success = manager.rename_modality(0, "New Name")
        assert success is True
        assert manager.get_modality(0).display_name == "New Name"
        
        success = manager.rename_modality(0, "New Name")
        assert success is True  # Same name is allowed
    
    def test_reserved_name_rejection(self):
        """Reserved names should be rejected."""
        manager = ModalityManager()
        
        for reserved in ["Primary", "Support", "Frame", "Stack"]:
            with pytest.raises(ValueError):
                manager.add_modality(0, reserved)
    
    def test_duplicate_name_rejection(self):
        """Duplicate names should be rejected."""
        manager = ModalityManager()
        manager.add_modality(0, "Unique Name")
        
        with pytest.raises(ValueError):
            manager.add_modality(1, "Unique Name")
    
    def test_invalid_name_validation(self):
        """Invalid names should be rejected."""
        manager = ModalityManager()
        
        with pytest.raises(ValueError):
            manager.add_modality(0, "")
        
        # None is acceptable - auto-generates "Modality N"
        manager2 = ModalityManager()
        mod = manager2.add_modality(0)
        assert mod.display_name == "Modality 1"
    
    def test_zoom_pan_linking(self):
        """Test zoom/pan synchronization linking."""
        manager = ModalityManager()
        manager.add_modality(0, "Mod 1")
        manager.add_modality(1, "Mod 2")
        
        assert not manager.are_zoom_pan_linked(0, 1)
        
        manager.set_zoom_pan_link(0, 1, True)
        assert manager.are_zoom_pan_linked(0, 1)
        
        manager.set_zoom_pan_link(0, 1, False)
        assert not manager.are_zoom_pan_linked(0, 1)
    
    def test_playback_linking(self):
        """Test playback synchronization linking."""
        manager = ModalityManager()
        manager.add_modality(0, "Mod 1")
        manager.add_modality(1, "Mod 2")
        
        assert not manager.are_playback_linked(0, 1)
        
        manager.set_playback_link(0, 1, True)
        assert manager.are_playback_linked(0, 1)
        
        manager.set_playback_link(0, 1, False)
        assert not manager.are_playback_linked(0, 1)
    
    def test_contrast_sync_options(self):
        """Test contrast synchronization options."""
        manager = ModalityManager()
        
        assert not manager.get_contrast_sync_option("sync_vmin")
        assert not manager.get_contrast_sync_option("sync_vmax")
        assert not manager.get_contrast_sync_option("sync_contrast")
        
        manager.set_contrast_sync_option("sync_vmin", True)
        assert manager.get_contrast_sync_option("sync_vmin")
        
        manager.set_contrast_sync_option("sync_contrast", True)
        assert manager.get_contrast_sync_option("sync_contrast")
    
    def test_manager_serialization(self):
        """Serialization and deserialization."""
        manager = ModalityManager()
        mod1 = manager.add_modality(0, "Mod 1")
        mod2 = manager.add_modality(1, "Mod 2")
        manager.set_zoom_pan_link(0, 1, True)
        manager.set_contrast_sync_option("sync_vmin", True)
        
        data = manager.to_dict()
        restored = ModalityManager.from_dict(data)
        
        assert restored.modality_count() == 2
        assert restored.get_modality(0).display_name == "Mod 1"
        assert restored.get_modality(1).display_name == "Mod 2"
        assert restored.are_zoom_pan_linked(0, 1)
        assert restored.get_contrast_sync_option("sync_vmin")
    
    def test_create_from_primary_support(self):
        """Create manager from legacy primary/support IDs."""
        manager = ModalityManager.create_from_primary_support(0, 1)
        
        assert manager.modality_count() == 2
        assert manager.get_modality(0).image_id == 0
        assert manager.get_modality(1).image_id == 1
        assert manager.get_modality(0).display_name == "Modality 1"
        assert manager.get_modality(1).display_name == "Modality 2"
    
    def test_create_from_single_image(self):
        """Create manager with only primary image."""
        manager = ModalityManager.create_from_primary_support(0)
        
        assert manager.modality_count() == 1
        assert manager.get_modality(0).image_id == 0


class TestMigration:
    """Test migration utilities."""
    
    def _create_old_session(self) -> SessionState:
        """Create old-style session for testing."""
        return SessionState(
            project_path=None,
            project_save_time=None,
            dirty=False,
            last_folder=None,
            recent_images=[],
            active_primary_id=0,
            active_support_id=1,
            images=[],
            image_states={},
            annotations={},
            labels=["Point"],
            current_label="Point",
        )
    
    def test_upgrade_to_modalities(self):
        """Upgrade old session to modalities."""
        session = self._create_old_session()
        
        upgrade_to_modalities(session)
        
        assert session.migration_version == 1
        assert session.modality_manager is not None
        assert session.modality_manager.modality_count() == 2
        assert session.modality_manager.get_modality(0).image_id == 0
        assert session.modality_manager.get_modality(1).image_id == 1
    
    def test_upgrade_idempotent(self):
        """Upgrade should be safe to call multiple times."""
        session = self._create_old_session()
        
        upgrade_to_modalities(session)
        first_manager = session.modality_manager
        
        upgrade_to_modalities(session)
        second_manager = session.modality_manager
        
        # Same manager instance
        assert first_manager is second_manager
    
    def test_downgrade_to_primary_support(self):
        """Downgrade modality session to primary/support."""
        session = self._create_old_session()
        upgrade_to_modalities(session)
        
        downgrade_to_primary_support(session)
        
        assert session.active_primary_id == 0
        assert session.active_support_id == 1
    
    def test_ensure_modality_system(self):
        """Ensure session has modality manager."""
        session = self._create_old_session()
        
        manager = ensure_modality_system(session)
        
        assert manager is not None
        assert session.modality_manager is not None
        assert session.migration_version == 1
    
    def test_get_active_modality_idx_from_modalities(self):
        """Get active modality index from manager."""
        session = self._create_old_session()
        session.modality_manager = ModalityManager.create_from_primary_support(5, 10)
        session.migration_version = 1
        
        idx = get_active_modality_idx(session)
        assert idx == 0  # First modality
    
    def test_get_active_modality_idx_from_legacy(self):
        """Get active modality index from legacy primary_id."""
        session = self._create_old_session()
        session.active_primary_id = 3
        
        idx = get_active_modality_idx(session)
        assert idx == 3
    
    def test_get_support_modality_idx_from_modalities(self):
        """Get support modality index from manager."""
        session = self._create_old_session()
        session.modality_manager = ModalityManager.create_from_primary_support(5, 10)
        session.migration_version = 1
        
        idx = get_support_modality_idx(session)
        assert idx == 1  # Second modality
    
    def test_get_support_modality_idx_from_legacy(self):
        """Get support modality index from legacy support_id."""
        session = self._create_old_session()
        session.active_primary_id = 0
        session.active_support_id = 2
        
        idx = get_support_modality_idx(session)
        assert idx == 2
    
    def test_migration_context(self):
        """Test migration context manager."""
        session = self._create_old_session()
        
        with MigrationContext(session) as ctx:
            session.migration_version = 1
            ctx.mark_success()
        
        assert session.migration_version == 1
