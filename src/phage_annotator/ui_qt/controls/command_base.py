"""Extracted method group 1 for SmlmControlsMixin."""

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



class CommandBaseMixin:
    """Method group 1 extracted from SmlmControlsMixin."""

    def _smlm_params_from_ui(self) -> Optional[SmlmParams]:
        """Handle the smlm params from ui helper flow."""
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
        """Handle the smlm bridge config from ui helper flow."""
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
        """Return runbook state for the current workflow."""
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
        """Show smlm preflight fixit for the current workflow."""
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
    def _pick_smlm_fiji_app_path(self) -> None:
        """Handle the pick smlm fiji app path helper flow."""
        if self.smlm_panel is None:
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Fiji.app directory")
        if path:
            self.smlm_panel.thunder.pyimagej_app_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Fiji app path updated.")
    def _pick_smlm_fiji_executable(self) -> None:
        """Handle the pick smlm fiji executable helper flow."""
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Fiji executable")
        if path:
            self.smlm_panel.thunder.fiji_exec_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Fiji executable updated.")
    def _pick_smlm_plugin_jar(self) -> None:
        """Handle the pick smlm plugin jar helper flow."""
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select plugin JAR", "", "JAR Files (*.jar)")
        if path:
            self.smlm_panel.thunder.thunderstorm_jar_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Plugin JAR updated.")
    def _list_smlm_plugin_commands(self) -> None:
        """Handle the list smlm plugin commands helper flow."""
        if self.smlm_panel is None:
            return
        jar = self.smlm_panel.thunder.thunderstorm_jar_edit.text().strip()
        if not jar:
            QtWidgets.QMessageBox.information(self, "Plugin Commands", "No plugin JAR selected.")
            return
        menus, commands = parse_plugins_config_from_jar(jar)
        if not commands:
            QtWidgets.QMessageBox.information(self, "Plugin Commands", "No commands discovered in plugins.config.")
            return
        lines = []
        for idx, command in enumerate(commands):
            menu = menus[idx] if idx < len(menus) else "(menu unknown)"
            lines.append(f"{idx + 1}. {command} [{menu}]")
        QtWidgets.QMessageBox.information(self, "Plugin Commands", "\n".join(lines))
    def _show_smlm_macro_viewer(self) -> None:
        """Show smlm macro viewer for the current workflow."""
        if self.smlm_panel is None:
            return
        sw = self.smlm_panel.thunder
        sw.generated_macro_view.setVisible(True)
        sw.show_macro_btn.setText("Hide Generated Macro")
    def _open_smlm_logs_panel(self) -> None:
        """Open smlm logs panel for the current workflow."""
        self.set_panel_visible("logs", True, source="smlm_fixit")
    def _open_smlm_error_folder(self) -> None:
        """Open smlm error folder for the current workflow."""
        path = getattr(self, "_last_smlm_error_report_path", "")
        if path:
            folder = pathlib.Path(path).resolve().parent
        else:
            folder = pathlib.Path("artifacts") / "smlm_errors"
            folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))
    def _sync_runbook_state_to_session(self) -> None:
        """Synchronize runbook state to session for the current workflow."""
        state = self._get_runbook_state()
        self.controller.set_smlm_runbook_state(
            enabled=bool(state.enabled),
            locked_profiles=dict(state.locked_profiles),
            provenance=list(state.provenance_events),
        )
