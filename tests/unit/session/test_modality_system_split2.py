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
