"""Migration utilities for upgrading sessions to multi-modality support.

This module handles backward compatibility when upgrading from the old
primary/support image system to the new dynamic modality system.

Phase α: Backward compatibility migration.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from phage_annotator.core.session_state import SessionState
    from phage_annotator.session.modality import ModalityManager


def upgrade_to_modalities(session_state: SessionState) -> None:
    """Upgrade old primary/support session to use modalities.
    
    This function converts a session using the old active_primary_id/active_support_id
    system to the new ModalityManager-based system. It maintains complete backward
    compatibility by:
    
    1. Creating Modality 1 from primary image
    2. Creating Modality 2 from support image (if exists)
    3. Preserving all display settings
    4. Setting migration_version=1
    
    After this operation, code can use either:
    - Old API: session_state.active_primary_id (still works)
    - New API: session_state.modality_manager.get_modality(0)
    
    Parameters
    ----------
    session_state : SessionState
        Session to upgrade in-place.
    
    Notes
    -----
    - Safe to call multiple times (idempotent)
    - Does not modify session_state.active_primary_id or active_support_id
    - All existing code continues to work unchanged
    """
    # Skip if already migrated
    if session_state.migration_version >= 1:
        return
    
    if session_state.modality_manager is not None:
        return
    
    # Import here to avoid circular dependency
    from phage_annotator.session.modality import ModalityManager
    
    # Create new modality manager
    manager = ModalityManager.create_from_primary_support(
        primary_img_id=session_state.active_primary_id,
        support_img_id=session_state.active_support_id
        if session_state.active_support_id != session_state.active_primary_id
        else None,
    )
    
    session_state.modality_manager = manager
    session_state.migration_version = 1


def downgrade_to_primary_support(session_state: SessionState) -> None:
    """Downgrade modality-based session to primary/support (compatibility fallback).
    
    This converts the modality manager back to primary/support IDs for compatibility
    with older code that doesn't understand modalities.
    
    Parameters
    ----------
    session_state : SessionState
        Session to downgrade in-place.
    
    Notes
    -----
    - Only preserves first two modalities
    - Additional modalities are lost
    - Useful for debugging or legacy code compatibility
    """
    if session_state.modality_manager is None:
        return
    
    modalities = session_state.modality_manager.get_all_modalities()
    
    if modalities:
        session_state.active_primary_id = modalities[0].image_id
    
    if len(modalities) > 1:
        session_state.active_support_id = modalities[1].image_id
    else:
        session_state.active_support_id = session_state.active_primary_id


def ensure_modality_system(session_state: SessionState) -> ModalityManager:
    """Ensure session has a modality manager, creating if necessary.
    
    Parameters
    ----------
    session_state : SessionState
        Session to check/update.
    
    Returns
    -------
    ModalityManager
        The session's modality manager (guaranteed non-None).
    """
    if session_state.modality_manager is None:
        upgrade_to_modalities(session_state)
    
    # Double-check after upgrade
    if session_state.modality_manager is None:
        raise RuntimeError("Failed to initialize modality manager")
    
    return session_state.modality_manager


def get_active_modality_idx(session_state: SessionState) -> int:
    """Get active (primary) modality index.
    
    Works with both old and new systems:
    - If modality system exists, returns modality 0 (first modality)
    - Otherwise falls back to active_primary_id
    
    Parameters
    ----------
    session_state : SessionState
        Session to query.
    
    Returns
    -------
    int
        Modality index or image index.
    """
    if session_state.modality_manager is not None:
        modalities = session_state.modality_manager.get_all_modalities()
        if modalities:
            return modalities[0].idx
    
    return session_state.active_primary_id


def get_support_modality_idx(session_state: SessionState) -> Optional[int]:
    """Get support (secondary) modality index.
    
    Works with both old and new systems:
    - If modality system exists and has 2+ modalities, returns modality 1
    - Otherwise falls back to active_support_id
    
    Parameters
    ----------
    session_state : SessionState
        Session to query.
    
    Returns
    -------
    int or None
        Modality index, image index, or None if no support modality.
    """
    if session_state.modality_manager is not None:
        modalities = session_state.modality_manager.get_all_modalities()
        if len(modalities) > 1:
            return modalities[1].idx
        return None
    
    # Fall back to old system if primary != support
    if session_state.active_support_id != session_state.active_primary_id:
        return session_state.active_support_id
    
    return None


class MigrationContext:
    """Context manager for safe migration operations.
    
    Ensures that if migration fails, the session is left in a consistent state.
    """
    
    def __init__(self, session_state: SessionState):
        """Initialize migration context.
        
        Parameters
        ----------
        session_state : SessionState
            Session to migrate.
        """
        self.session_state = session_state
        self.old_version = session_state.migration_version
        self.old_manager = session_state.modality_manager
        self.success = False
    
    def __enter__(self) -> "MigrationContext":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore old state if migration failed."""
        if not self.success and exc_type is not None:
            self.session_state.migration_version = self.old_version
            self.session_state.modality_manager = self.old_manager
    
    def mark_success(self):
        """Mark migration as successful."""
        self.success = True
