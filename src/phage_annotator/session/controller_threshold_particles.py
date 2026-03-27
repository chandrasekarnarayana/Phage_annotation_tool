"""Threshold, particles, and evidence-layer controller helpers."""

from __future__ import annotations

from phage_annotator.session.signal_hub import emit_state_changed


class SessionControllerThresholdParticlesMixin:
    """Controller helpers for threshold, particles, and evidence-layer state."""

    def set_threshold_preview_settings(self, image_id: int, settings: dict) -> None:
        """Persist threshold preview settings for one image."""
        payload = dict(settings or {})
        self.session_state.threshold_settings = payload
        self.session_state.threshold_configs_by_image[int(image_id)] = payload
        emit_state_changed(self)

    def store_threshold_mask(self, image_id: int, payload: dict) -> None:
        """Persist a threshold mask payload for one image."""
        self.session_state.threshold_masks[int(image_id)] = dict(payload or {})
        emit_state_changed(self)

    def set_particles_config(self, image_id: int, payload: dict) -> None:
        """Persist particle-analysis configuration for one image."""
        self.session_state.particles_configs_by_image[int(image_id)] = dict(payload or {})
        emit_state_changed(self)

    def set_evidence_layer_config(self, config: dict) -> None:
        """Store evidence-layer configuration."""
        self.session_state.evidence_layer_config = dict(config or {})
        emit_state_changed(self)

    def set_evidence_layer_presets(self, presets: dict) -> None:
        """Store named evidence-layer presets."""
        self.session_state.evidence_layer_presets = dict(presets or {})
        emit_state_changed(self)
