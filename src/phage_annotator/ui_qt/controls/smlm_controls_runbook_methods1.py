"""Method group 1 split from smlm_controls_runbook.py."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import pathlib
import platform
import subprocess
import sys
import textwrap
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.deepstorm.infer import DeepStormParams, is_torch_available, run_deepstorm_stream
from phage_annotator.smlm.backends import (
    ThunderstormBridgeConfig,
    discover_bundled_thunderstorm_jar,
    run_thunderstorm_backend,
)
from phage_annotator.smlm.reproducibility import (
    ReproducibilityRunbookState,
    append_provenance_event,
    export_reproducibility_bundle,
    lock_profile,
    resolve_profile,
)
from phage_annotator.smlm.preflight import report_to_text, run_preflight
from phage_annotator.smlm.external_plugins import parse_plugins_config_from_jar
from phage_annotator.smlm.thunderstorm import SmlmParams

class _SmlmControlsRunbookMixinMethods1:
    """Methods split from SmlmControlsRunbookMixin."""

    def _smlm_params_from_ui(self) -> Optional[SmlmParams]:
        """Document the smlm_params_from_ui flow."""
        if self.smlm_panel is None:
            return None
        values = self.smlm_panel.thunder.values()
        return SmlmParams(
            sigma_px=values.sigma_px,
            fit_radius_px=values.fit_radius_px,
            filter_type=values.filter_type,
            dog_sigma1=values.dog_sigma1,
            dog_sigma2=values.dog_sigma2,
            detection_thr_sigma=values.detection_thr_sigma,
            max_candidates_per_frame=values.max_candidates_per_frame,
            merge_radius_px=values.merge_radius_px,
            min_photons=values.min_photons,
            max_uncertainty_nm=values.max_uncertainty_nm,
            upsample=values.upsample,
            render_mode=values.render_mode,
            render_sigma_nm=values.render_sigma_nm,
        )

    def _smlm_bridge_config_from_ui(self) -> ThunderstormBridgeConfig:
        """Document the smlm_bridge_config_from_ui flow."""
        if self.smlm_panel is None:
            return ThunderstormBridgeConfig()
        values = self.smlm_panel.thunder.values()
        return ThunderstormBridgeConfig(
            backend=values.backend,
            plugin_id=values.plugin_id or "thunder_storm",
            plugin_jar_path=values.plugin_jar_path,
            fiji_executable=values.fiji_executable,
            macro_path=values.fiji_macro_path,
            thunderstorm_jar_path=values.thunderstorm_jar_path,
            command_template=values.fiji_command_template,
            pyimagej_app_path=values.pyimagej_app_path,
            timeout_sec=int(self._settings.value("smlmBridgeTimeoutSec", 900, type=int)),
        )

    def _get_runbook_state(self) -> ReproducibilityRunbookState:
        """Document the get_runbook_state flow."""
        state = getattr(self, "_smlm_runbook_state", None)
        if state is None:
            state = ReproducibilityRunbookState()
            self._smlm_runbook_state = state
        return state

    def _run_smlm_preflight(self) -> None:
        """Run bridge preflight checks and surface actionable diagnostics."""
        if self.smlm_panel is None:
            return
        config = self._smlm_bridge_config_from_ui()
        do_probe = str(config.backend).strip().lower() == "fiji_subprocess"
        report = run_preflight(config, probe=do_probe)
        summary = report_to_text(report)
        self.smlm_panel.thunder.status_label.setText(
            "Preflight OK" if report.ok else "Preflight failed (see details)"
        )
        if hasattr(self.smlm_panel.thunder, "append_debug_report"):
            self.smlm_panel.thunder.append_debug_report(summary)
        if report.ok:
            if hasattr(self.smlm_panel.thunder, "clear_fixit_card"):
                self.smlm_panel.thunder.clear_fixit_card()
            self._status_success(
                "SMLM preflight passed.",
                timeout_ms=2500,
                source="smlm.preflight",
            )
        else:
            self._show_smlm_preflight_fixit(report.exit_code, summary)
            self._status_warning(
                "SMLM preflight failed; review checklist.",
                sticky=True,
                source="smlm.preflight",
            )
            QtWidgets.QMessageBox.warning(self, "SMLM Preflight", summary)

    def _show_smlm_preflight_fixit(self, exit_code: int, summary: str) -> None:
        """Document the show_smlm_preflight_fixit flow."""
        if self.smlm_panel is None or not hasattr(self.smlm_panel.thunder, "set_fixit_card"):
            return
        sw = self.smlm_panel.thunder
        actions = []
        title = "Preflight failed"
        detail = summary
        if int(exit_code) == 2:
            title = "Fiji not configured"
            detail = "Set Fiji paths, then run probe again."
            actions = [
                ("Set FIJI_APP_PATH", self._pick_smlm_fiji_app_path),
                ("Set FIJI_EXE_PATH", self._pick_smlm_fiji_executable),
                ("Re-run Probe", self._run_smlm_preflight),
                ("Copy Debug Report", sw._copy_debug_report),
            ]
        elif int(exit_code) == 3:
            title = "Plugin not discoverable"
            detail = "Select plugin JAR and inspect available plugin commands."
            actions = [
                ("Select JAR", self._pick_smlm_plugin_jar),
                ("List Commands", self._list_smlm_plugin_commands),
                ("Re-run Probe", self._run_smlm_preflight),
                ("Copy Debug Report", sw._copy_debug_report),
            ]
        elif int(exit_code) == 4:
            title = "Macro execution failed"
            detail = "Inspect generated macro and logs, then run probe again."
            actions = [
                ("Show Macro", self._show_smlm_macro_viewer),
                ("Open Error Folder", self._open_smlm_error_folder),
                ("Open Logs", self._open_smlm_logs_panel),
                ("Re-run Probe", self._run_smlm_preflight),
            ]
        elif int(exit_code) == 5:
            title = "Probe output missing"
            detail = "Inspect output/logs and rerun probe."
            actions = [
                ("Open Output Folder", self._open_smlm_error_folder),
                ("Open Logs", self._open_smlm_logs_panel),
                ("Re-run Probe", self._run_smlm_preflight),
                ("Copy Debug Report", sw._copy_debug_report),
            ]
        else:
            actions = [
                ("Re-run Probe", self._run_smlm_preflight),
                ("Copy Debug Report", sw._copy_debug_report),
            ]
        sw.set_fixit_card(title=title, detail=detail, actions=actions)

    def _sync_runbook_state_to_session(self) -> None:
        """Document the sync_runbook_state_to_session flow."""
        state = self._get_runbook_state()
        self.controller.set_smlm_runbook_state(
            enabled=bool(state.enabled),
            locked_profiles=dict(state.locked_profiles),
            provenance=list(state.provenance_events),
        )

    def _apply_smlm_preset(self, name: str) -> None:
        """Document the apply_smlm_preset flow."""
        if self.smlm_panel is None:
            return
        self.smlm_panel.apply_preset(name)

    def _validate_smlm_params(self, params: SmlmParams) -> Tuple[Optional[str], Optional[str]]:
        """Document the validate_smlm_params flow."""
        if params.sigma_px <= 0:
            return "Sigma must be positive.", None
        if params.fit_radius_px < 2:
            return "Fit radius too small (min 2 px).", None
        if params.detection_thr_sigma <= 0:
            return "Threshold must be positive.", None
        warn = None
        if not (1.0 <= params.sigma_px <= 1.8):
            warn = "Sigma outside recommended range (1.1–1.6 px)."
        if not (2.0 <= params.detection_thr_sigma <= 6.0):
            warn = "Threshold outside recommended range (2–6 σ)."
        if not (3 <= params.fit_radius_px <= 6):
            warn = "Fit radius outside recommended range (3–5 px)."
        return None, warn

    def _record_smlm_run(
        self,
        method: str,
        params: dict,
        roi_rect: Tuple[float, float, float, float],
        crop_rect: Optional[Tuple[float, float, float, float]],
        model: Optional[dict],
        *,
        backend: str = "internal",
        backend_config: Optional[dict] = None,
        runbook_enabled: bool = False,
    ) -> None:
        """Document the record_smlm_run flow."""
        from datetime import datetime

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "method": method,
            "params": params,
            "backend": backend,
            "backend_config": dict(backend_config or {}),
            "runbook_enabled": bool(runbook_enabled),
            "roi_rect": roi_rect,
            "roi_shape": self.roi_shape,
            "crop_rect": crop_rect,
            "image_path": str(self.primary_image.path),
            "model": model,
        }
        self._smlm_run_history.append(entry)
        self._last_smlm_run = entry
        self.controller.set_smlm_runs_value(list(self._smlm_run_history))

    def _hash_file(self, path: str) -> Optional[str]:
        """Document the hash_file flow."""
        if not path:
            return None
        try:
            p = pathlib.Path(path)
            if not p.exists():
                return None
            import hashlib

            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def _rerun_last_smlm(self) -> None:
        """Document the rerun_last_smlm flow."""
        if not self._last_smlm_run:
            self._status_info(
                "No SMLM run to re-run.",
                timeout_ms=2500,
                source="smlm.rerun",
            )
            return
        method = self._last_smlm_run.get("method")
        params = self._last_smlm_run.get("params", {})
        if self.smlm_panel is None:
            return
        if method == "ThunderSTORM":
            thunder = self.smlm_panel.thunder
            self.smlm_panel.tabs.setCurrentIndex(0)
            thunder.sigma_spin.setValue(float(params.get("sigma_px", thunder.sigma_spin.value())))
            thunder.fit_radius_spin.setValue(int(params.get("fit_radius_px", thunder.fit_radius_spin.value())))
            thunder.det_thr_spin.setValue(float(params.get("detection_thr_sigma", thunder.det_thr_spin.value())))
            thunder.max_candidates_spin.setValue(
                int(params.get("max_candidates_per_frame", thunder.max_candidates_spin.value()))
            )
            thunder.merge_radius_spin.setValue(float(params.get("merge_radius_px", thunder.merge_radius_spin.value())))
            thunder.min_photons_spin.setValue(float(params.get("min_photons", thunder.min_photons_spin.value())))
            thunder.render_combo.setCurrentText(str(params.get("render_mode", thunder.render_combo.currentText())))
            self._run_smlm()
        elif method == "Deep-STORM":
            deep = self.smlm_panel.deep
            self.smlm_panel.tabs.setCurrentIndex(1)
            deep.model_path_edit.setText(str(params.get("model_path", deep.model_path_edit.text())))
            deep.patch_combo.setCurrentText(str(params.get("patch_size", deep.patch_combo.currentText())))
            deep.overlap_spin.setValue(int(params.get("overlap", deep.overlap_spin.value())))
            deep.upsample_spin.setValue(int(params.get("upsample", deep.upsample_spin.value())))
            deep.sigma_spin.setValue(float(params.get("sigma_px", deep.sigma_spin.value())))
            deep.normalize_combo.setCurrentText(str(params.get("normalize_mode", deep.normalize_combo.currentText())))
            deep.output_combo.setCurrentText(str(params.get("output_mode", deep.output_combo.currentText())))
            deep.window_spin.setValue(int(params.get("window_size", deep.window_spin.value())))
            deep.agg_combo.setCurrentText(str(params.get("aggregation_mode", deep.agg_combo.currentText())))
            self._run_deepstorm()
