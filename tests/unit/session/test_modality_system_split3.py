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
