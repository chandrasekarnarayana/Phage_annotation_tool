"""SMLM-related controller helpers."""

from __future__ import annotations

from phage_annotator.session.signal_hub import emit_state_changed


class SessionControllerSmlmMixin:
    """Controller helpers for persisted SMLM workflow state."""

    def set_smlm_runbook_state(self, *, enabled: bool, locked_profiles: dict, provenance: list) -> None:
        """Persist SMLM runbook state."""
        self.session_state.smlm_runbook_enabled = bool(enabled)
        self.session_state.smlm_runbook_locked_profiles = dict(locked_profiles or {})
        self.session_state.smlm_runbook_provenance = list(provenance or [])
        emit_state_changed(self)

    def set_smlm_runs_value(self, runs: list[dict]) -> None:
        """Persist SMLM run history."""
        self.session_state.smlm_runs = list(runs or [])
        emit_state_changed(self)
