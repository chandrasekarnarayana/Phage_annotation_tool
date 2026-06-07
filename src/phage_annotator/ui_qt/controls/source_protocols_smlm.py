"""Extracted method group 6 for SmlmControlsMixin."""

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



class SourceProtocolsOverlaysMixin:
    """Method group 6 extracted from SmlmControlsMixin."""

    def _deepstorm_to_annotations(self) -> None:
        """Handle the deepstorm to annotations helper flow."""
        if not self._deepstorm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.deep.status_label.setText("No Deep-STORM results to add.")
            return
        if hasattr(self, "_ensure_annotation_write_context_confirmed"):
            if not self._ensure_annotation_write_context_confirmed("Import Deep-STORM localizations"):
                return
        image_id = self.primary_image.id
        self._block_table = True
        for loc in self._deepstorm_results:
            self.controller.add_annotation(
                image_id=image_id,
                image_name=self.primary_image.name,
                t=-1,
                z=self.z_slider.value(),
                y=loc.y_px,
                x=loc.x_px,
                label=self.current_label,
                scope=self.annotation_scope,
            )
        self._block_table = False
        self._request_ui_refresh("smlm-controls", table=True)
        self._mark_dirty()
        if self.smlm_panel is not None:
            self.smlm_panel.deep.status_label.setText("Added to annotations.")
    def _torch_has_cuda(self) -> bool:
        """Handle the torch has cuda helper flow."""
        try:
            import torch
        except Exception:
            return False
        return torch.cuda.is_available()
    def _apply_smlm_preset(self, name: str) -> None:
        """Apply smlm preset for the current workflow."""
        if self.smlm_panel is None:
            return
        self.smlm_panel.apply_preset(name)
    def _validate_smlm_params(self, params: SmlmParams) -> Tuple[Optional[str], Optional[str]]:
        """Validate smlm params for the current workflow."""
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
    def _validate_deepstorm_params(self, params: DeepStormParams) -> Tuple[Optional[str], Optional[str]]:
        """Validate deepstorm params for the current workflow."""
        if params.patch_size not in (64, 96, 128):
            return "Patch size must be 64/96/128.", None
        if params.overlap < 0 or params.overlap >= params.patch_size:
            return "Overlap must be smaller than patch size.", None
        if params.upsample < 2:
            return "Upsample must be >= 2.", None
        warn = None
        if not (1.0 <= params.sigma_px <= 1.8):
            warn = "Sigma outside recommended range (1.1–1.6 px)."
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
        """Record smlm run for the current workflow."""
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
        """Handle the hash file helper flow."""
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
        """Handle the rerun last smlm helper flow."""
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
    def _lock_current_smlm_profile(self) -> None:
        """Handle the lock current smlm profile helper flow."""
        if self.smlm_panel is None:
            return
        params = self._smlm_params_from_ui()
        if params is None:
            return
        bridge = self._smlm_bridge_config_from_ui()
        state = self._get_runbook_state()
        lock_profile(
            state,
            "ThunderSTORM",
            {
                "backend": bridge.backend,
                "plugin_id": bridge.plugin_id,
                "plugin_jar_path": bridge.plugin_jar_path,
                "params": dict(params.__dict__),
                "fiji_executable": bridge.fiji_executable,
                "fiji_macro_path": bridge.macro_path,
                "thunderstorm_jar_path": bridge.thunderstorm_jar_path,
                "fiji_command_template": bridge.command_template,
                "pyimagej_app_path": bridge.pyimagej_app_path,
            },
        )
        self._sync_runbook_state_to_session()
        self._status_success(
            "Runbook profile locked for ThunderSTORM.",
            timeout_ms=3000,
            source="smlm.runbook.lock",
        )
        self.smlm_panel.thunder.status_label.setText("Runbook profile locked.")
    def _export_smlm_runbook(self) -> None:
        """Export smlm runbook for the current workflow."""
        state = self._get_runbook_state()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Reproducibility Runbook",
            str(pathlib.Path.cwd() / "smlm_runbook.json"),
            "JSON Files (*.json)",
        )
        if not path:
            return
        out = export_reproducibility_bundle(
            state,
            out_path=pathlib.Path(path),
            session_payload={
                "image_path": str(getattr(self.primary_image, "path", "")),
                "smlm_runs": list(getattr(self, "_smlm_run_history", [])),
            },
        )
        self._sync_runbook_state_to_session()
        self._status_success(
            f"Exported runbook to {out}",
            timeout_ms=4000,
            source="smlm.runbook.export",
        )
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText(f"Runbook exported: {out.name}")
    def _toggle_smlm_points(self) -> None:
        """Toggle smlm points for the current workflow."""
        if getattr(self, "show_smlm_points_act", None) is not None:
            self.show_smlm_points = self.show_smlm_points_act.isChecked()
            if self.smlm_panel is not None and hasattr(self.smlm_panel.thunder, "show_points_chk"):
                self.smlm_panel.thunder.show_points_chk.blockSignals(True)
                self.smlm_panel.thunder.show_points_chk.setChecked(bool(self.show_smlm_points))
                self.smlm_panel.thunder.show_points_chk.blockSignals(False)
            self._request_ui_refresh("smlm-controls")
    def _toggle_smlm_sr(self) -> None:
        """Toggle smlm sr for the current workflow."""
        if getattr(self, "show_smlm_sr_act", None) is not None:
            self.show_sr_overlay = self.show_smlm_sr_act.isChecked()
            self._request_ui_refresh("smlm-controls")
