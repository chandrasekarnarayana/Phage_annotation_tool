"""Helper mixin for multi-modality panel integration."""

from __future__ import annotations


class ModalityHelpersMixin:
    """Mixin to sync modality lists across analysis panels."""

    def _update_analysis_panel_modalities(self) -> None:
        """Update modality combo boxes in all analysis panels."""
        manager = getattr(self.controller.session_state, "modality_manager", None)

        self._update_modality_cache_budget(manager)

        # Update threshold panel
        if hasattr(self, "threshold_panel") and self.threshold_panel is not None:
            self.threshold_panel.update_modality_list(manager)

        # Update particles panel
        if hasattr(self, "particles_panel") and self.particles_panel is not None:
            self.particles_panel.update_modality_list(manager)

        # Update SMLM panel
        if hasattr(self, "smlm_panel") and self.smlm_panel is not None:
            self.smlm_panel.update_modality_list(manager)

    def _update_modality_cache_budget(self, manager) -> None:
        """Update projection cache budgets per modality."""
        cache = getattr(self, "proj_cache", None)
        if cache is None:
            return
        if manager is None:
            cache.set_modality_count(1)
            return
        cache.set_modality_count(len(manager.get_all_modalities()) or 1)
