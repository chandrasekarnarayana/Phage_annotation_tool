"""Extracted method group 3 for SmlmControlsMixin."""

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



class SmlmControlsReconstructionMixin:
    """Method group 3 extracted from SmlmControlsMixin."""

    def _build_smlm_debug_report(
        self,
        bridge_config: ThunderstormBridgeConfig,
        *,
        backend_meta: dict | None,
        error_text: str = "",
    ) -> str:
        """Build smlm debug report for the current workflow."""
        plugin_jar = bridge_config.plugin_jar_path or bridge_config.thunderstorm_jar_path
        package_version = "unknown"
        try:
            package_version = importlib.metadata.version("phage-annotator")
        except Exception:
            pass
        git_sha = self._resolve_git_sha()
        plugin_jar_sha = self._sha256_file(plugin_jar) if plugin_jar else ""
        plugin_jar_size = ""
        if plugin_jar:
            try:
                plugin_jar_size = str(pathlib.Path(plugin_jar).stat().st_size)
            except Exception:
                plugin_jar_size = ""
        fiji_version = self._resolve_fiji_version(bridge_config.fiji_executable)
        macro_source = "user"
        if not bridge_config.macro_path:
            macro_source = "auto"
        manifest = None
        try:
            from phage_annotator.smlm.external_plugins import resolve_plugin_descriptor

            desc = resolve_plugin_descriptor(bridge_config.plugin_id)
            manifest = desc.manifest if desc is not None else None
            if not bridge_config.macro_path and desc is not None and desc.macro_path:
                macro_source = "bundled"
            elif not bridge_config.macro_path and manifest is not None:
                macro_source = "generated"
        except Exception:
            manifest = None
        env_lines = [
            f"PHAGE_SMLM_INPUT=<temp-input.tif>",
            f"PHAGE_SMLM_OUTPUT=<temp-output.csv>",
            f"PHAGE_SMLM_PARAMS_JSON=<temp-params.json>",
            f"PHAGE_PLUGIN_ID={bridge_config.plugin_id}",
            f"PHAGE_PLUGIN_JAR={plugin_jar}",
        ]
        lines = [
            f"[SMLM DEBUG] timestamp={datetime.now().isoformat(timespec='seconds')}",
            f"os={platform.platform()}",
            f"python={sys.version.split()[0]}",
            f"package_version={package_version}",
            f"git_sha={git_sha}",
            f"backend={bridge_config.backend}",
            f"plugin_id={bridge_config.plugin_id}",
            f"fiji_executable={bridge_config.fiji_executable}",
            f"fiji_version={fiji_version}",
            f"macro_path={bridge_config.macro_path or '<auto>'}",
            f"macro_source={macro_source}",
            f"pyimagej_app_path={bridge_config.pyimagej_app_path}",
            f"command_template={'custom' if bridge_config.command_template else 'default'}",
            f"timeout_sec={bridge_config.timeout_sec}",
            f"plugin_jar_path={plugin_jar}",
            f"plugin_jar_sha256={plugin_jar_sha}",
            f"plugin_jar_size_bytes={plugin_jar_size}",
            "env:",
            *[f"  {line}" for line in env_lines],
        ]
        if manifest is not None:
            lines.extend(
                [
                    f"manifest.plugin_version_tested={manifest.plugin_version_tested or 'n/a'}",
                    f"manifest.csv_schema_version={manifest.csv_schema_version or 'n/a'}",
                    f"manifest.required_columns={','.join(manifest.required_columns)}",
                ]
            )
        if backend_meta:
            lines.append("backend_meta:")
            for key in sorted(backend_meta.keys()):
                if key == "executed_macro":
                    continue
                lines.append(f"  {key}: {backend_meta[key]}")
            output_csv = str((backend_meta or {}).get("output_csv", "")).strip()
            if output_csv:
                lines.append("artifacts:")
                lines.extend(self._artifact_lines([output_csv]))
            macro = str(backend_meta.get("executed_macro", "")).strip()
            if macro:
                lines.extend(["executed_macro:", textwrap.indent(macro, "  ")])
        if error_text:
            lines.extend(["error:", textwrap.indent(error_text.strip(), "  ")])
        return "\n".join(lines)
    def _artifact_lines(self, paths: list[str]) -> list[str]:
        """Handle the artifact lines helper flow."""
        lines: list[str] = []
        for raw in paths:
            p = pathlib.Path(raw)
            if p.exists():
                lines.append(f"  {p}: {p.stat().st_size} bytes")
            else:
                lines.append(f"  {p}: <missing>")
        return lines
    def _sha256_file(self, path: str) -> str:
        """Handle the sha256 file helper flow."""
        try:
            p = pathlib.Path(path)
            if not p.exists():
                return ""
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""
    def _resolve_git_sha(self) -> str:
        """Resolve git sha for the current workflow."""
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if proc.returncode == 0:
                return (proc.stdout or "").strip() or "unknown"
        except Exception:
            pass
        return "unknown"
    def _resolve_fiji_version(self, fiji_executable: str) -> str:
        """Resolve fiji version for the current workflow."""
        exe = str(fiji_executable or "").strip()
        if not exe:
            return ""
        try:
            proc = subprocess.run(
                [exe, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = (proc.stdout or proc.stderr or "").strip()
            return out.splitlines()[0][:180] if out else ""
        except Exception:
            return ""
    def _persist_smlm_error_report(self, report_text: str) -> str:
        """Handle the persist smlm error report helper flow."""
        out_dir = pathlib.Path("artifacts") / "smlm_errors"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"smlm_error_{stamp}.log"
        path.write_text(report_text, encoding="utf-8")
        self._last_smlm_error_report_path = str(path)
        return str(path)
    def _show_smlm_failure_actions(
        self,
        *,
        bridge_config: ThunderstormBridgeConfig,
        report_path: str,
        error_text: str,
    ) -> None:
        """Show smlm failure actions for the current workflow."""
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("SMLM Bridge Error")
        msg.setText("Fiji bridge execution failed.")
        msg.setInformativeText(
            "A detailed report was saved.\n"
            f"{report_path}"
        )
        msg.setDetailedText(error_text)
        fallback_btn = None
        if (bridge_config.backend or "").strip().lower() != "internal":
            fallback_btn = msg.addButton("Run Internal Backend", QtWidgets.QMessageBox.AcceptRole)
        logs_btn = msg.addButton("Open Logs Panel", QtWidgets.QMessageBox.ActionRole)
        folder_btn = msg.addButton("Open Error Folder", QtWidgets.QMessageBox.ActionRole)
        copy_btn = msg.addButton("Copy Debug Report", QtWidgets.QMessageBox.ActionRole)
        msg.addButton(QtWidgets.QMessageBox.Close)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked is logs_btn:
            self.set_panel_visible("logs", True, source="smlm_error")
            return
        if clicked is folder_btn:
            folder = pathlib.Path(report_path).resolve().parent
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))
            return
        if clicked is copy_btn:
            try:
                QtWidgets.QApplication.clipboard().setText(pathlib.Path(report_path).read_text(encoding="utf-8"))
            except Exception:
                pass
            return
        if fallback_btn is not None and clicked is fallback_btn and self.smlm_panel is not None:
            self.smlm_panel.thunder.backend_combo.setCurrentText("internal")
            self._status_info(
                "Retrying SMLM with internal backend.",
                timeout_ms=3000,
                source="smlm.retry",
            )
            self._run_smlm()
    def _cancel_smlm(self) -> None:
        """Handle the cancel smlm helper flow."""
        if self._smlm_job_id is None:
            return
        self.jobs.cancel(self._smlm_job_id)
        self._smlm_job_id = None
        if self.smlm_panel is not None:
            thunder = self.smlm_panel.thunder
            thunder.status_label.setText("Cancelling…")
            thunder.cancel_btn.setEnabled(False)
            thunder.run_btn.setEnabled(True)
            if hasattr(thunder, "clear_localizations"):
                thunder.clear_localizations()
    def _toggle_smlm_points_from_panel(self, checked: bool) -> None:
        """Toggle smlm points from panel for the current workflow."""
        self.show_smlm_points = bool(checked)
        if getattr(self, "show_smlm_points_act", None) is not None:
            self.show_smlm_points_act.blockSignals(True)
            self.show_smlm_points_act.setChecked(bool(checked))
            self.show_smlm_points_act.blockSignals(False)
        self._request_ui_refresh("smlm-controls")
