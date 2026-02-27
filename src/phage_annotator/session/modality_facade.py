"""Backward-compatible facade for modality-based sessions.

Provides transparent integration of the modality system with existing code
that still uses primary/support image IDs. This allows gradual migration
from the old system to the new multi-modality system.

Phase α: Transparent bridging of legacy and new systems.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from phage_annotator.core.session_state import SessionState
    from phage_annotator.session.modality import ModalityManager


class ModalityFacade:
    """Transparent facade bridging legacy primary/support with modalities.
    
    Allows existing code to work with both systems:
    - Automatic upgrade to modalities on first access
    - Fallback to primary/support if needed
    - Transparent synchronization
    
    Usage
    -----
    session = load_session()  # Old or new session
    facade = ModalityFacade(session)
    
    # Works with both old and new sessions:
    active_idx = facade.get_active_modality_idx()
    modality = facade.get_active_modality()
    
    facade.set_active_modality(0)  # Works regardless of system version
    """
    
    def __init__(self, session_state: SessionState):
        """Initialize facade.
        
        Parameters
        ----------
        session_state : SessionState
            The session to bridge.
        """
        self.session_state = session_state
        self._ensure_modalities()
    
    def _ensure_modalities(self) -> None:
        """Ensure session has modality manager (auto-upgrade if needed)."""
        from phage_annotator.session.migration import ensure_modality_system
        ensure_modality_system(self.session_state)
    
    def get_manager(self) -> ModalityManager:
        """Get the session's modality manager.
        
        Returns
        -------
        ModalityManager
            The manager (guaranteed non-None).
        """
        if self.session_state.modality_manager is None:
            self._ensure_modalities()
        return self.session_state.modality_manager
    
    def get_active_modality_idx(self) -> int:
        """Get active (primary) modality index.
        
        Returns
        -------
        int
            Modality index (0 = first/primary modality).
        """
        manager = self.get_manager()
        modalities = manager.get_all_modalities()
        if modalities:
            return modalities[0].idx
        return self.session_state.active_primary_id
    
    def get_support_modality_idx(self) -> Optional[int]:
        """Get support (secondary) modality index if exists.
        
        Returns
        -------
        int or None
            Modality index (1 = second/support modality) or None.
        """
        manager = self.get_manager()
        modalities = manager.get_all_modalities()
        if len(modalities) > 1:
            return modalities[1].idx
        return None
    
    def set_active_modality(self, modality_idx: int) -> None:
        """Set active modality.
        
        Note: In legacy 2-modality mode, only supports setting primary.
        
        Parameters
        ----------
        modality_idx : int
            Modality index to activate.
        """
        # For now, map to primary_id (future: support arbitrary modality selection)
        manager = self.get_manager()
        modality = manager.get_modality(modality_idx)
        if modality:
            self.session_state.active_primary_id = modality.image_id
    
    def get_active_modality(self):
        """Get active modality spec.
        
        Returns
        -------
        ModalitySpec or None
        """
        manager = self.get_manager()
        idx = self.get_active_modality_idx()
        return manager.get_modality(idx)
    
    def get_support_modality(self):
        """Get support modality spec if exists.
        
        Returns
        -------
        ModalitySpec or None
        """
        manager = self.get_manager()
        idx = self.get_support_modality_idx()
        if idx is not None:
            return manager.get_modality(idx)
        return None
    
    def count_modalities(self) -> int:
        """Get number of modalities."""
        return self.get_manager().modality_count()
