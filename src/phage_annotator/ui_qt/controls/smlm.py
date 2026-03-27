"""SMLM (ThunderSTORM/Deep-STORM) handlers."""

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


class SmlmControlsMixin:
    """Mixin for SMLM (ThunderSTORM/Deep-STORM) handlers."""

    def _smlm_params_from_ui(self) -> Optional[SmlmParams]:
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
        if self.smlm_panel is None:
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Fiji.app directory")
        if path:
            self.smlm_panel.thunder.pyimagej_app_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Fiji app path updated.")

    def _pick_smlm_fiji_executable(self) -> None:
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Fiji executable")
        if path:
            self.smlm_panel.thunder.fiji_exec_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Fiji executable updated.")

    def _pick_smlm_plugin_jar(self) -> None:
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select plugin JAR", "", "JAR Files (*.jar)")
        if path:
            self.smlm_panel.thunder.thunderstorm_jar_edit.setText(path)
            self.smlm_panel.thunder.status_label.setText("Plugin JAR updated.")

    def _list_smlm_plugin_commands(self) -> None:
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
        if self.smlm_panel is None:
            return
        sw = self.smlm_panel.thunder
        sw.generated_macro_view.setVisible(True)
        sw.show_macro_btn.setText("Hide Generated Macro")

    def _open_smlm_logs_panel(self) -> None:
        self.set_panel_visible("logs", True, source="smlm_fixit")

    def _open_smlm_error_folder(self) -> None:
        path = getattr(self, "_last_smlm_error_report_path", "")
        if path:
            folder = pathlib.Path(path).resolve().parent
        else:
            folder = pathlib.Path("artifacts") / "smlm_errors"
            folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    def _sync_runbook_state_to_session(self) -> None:
        state = self._get_runbook_state()
        self.controller.set_smlm_runbook_state(
            enabled=bool(state.enabled),
            locked_profiles=dict(state.locked_profiles),
            provenance=list(state.provenance_events),
        )

    def _run_smlm(self) -> None:
        if self.smlm_panel is None:
            return
        thunder = self.smlm_panel.thunder
        self._ensure_loaded(self.current_image_idx)
        if self.primary_image.array is None:
            thunder.status_label.setText("Load an image first.")
            return
        roi_rect = self.roi_rect
        if roi_rect is None or roi_rect[2] <= 0 or roi_rect[3] <= 0:
            thunder.status_label.setText("Set an ROI first.")
            if self.dock_roi is not None:
                self.set_panel_visible("roi", True, source="smlm_validation")
            return
        
        # Phase ζ: Get selected modality_idx from panel
        selected_modality_idx = self.smlm_panel.get_selected_modality_idx()
        self._smlm_modality_idx = selected_modality_idx
        
        params = self._smlm_params_from_ui()
        if params is None:
            return
        bridge_config = self._smlm_bridge_config_from_ui()
        runbook_state = self._get_runbook_state()
        if self.smlm_panel is not None:
            runbook_state.enabled = bool(self.smlm_panel.thunder.repro_mode_chk.isChecked())
        self._sync_runbook_state_to_session()
        proposed_profile = {
            "backend": bridge_config.backend,
            "plugin_id": bridge_config.plugin_id,
            "plugin_jar_path": bridge_config.plugin_jar_path,
            "params": params.__dict__,
            "fiji_executable": bridge_config.fiji_executable,
            "fiji_macro_path": bridge_config.macro_path,
            "thunderstorm_jar_path": bridge_config.thunderstorm_jar_path,
            "fiji_command_template": bridge_config.command_template,
            "pyimagej_app_path": bridge_config.pyimagej_app_path,
        }
        effective_profile = resolve_profile(runbook_state, "ThunderSTORM", proposed_profile)
        params = SmlmParams(**effective_profile.get("params", params.__dict__))
        bridge_config = ThunderstormBridgeConfig(
            backend=str(effective_profile.get("backend", bridge_config.backend)),
            plugin_id=str(effective_profile.get("plugin_id", bridge_config.plugin_id)),
            plugin_jar_path=str(
                effective_profile.get("plugin_jar_path", bridge_config.plugin_jar_path)
            ),
            fiji_executable=str(effective_profile.get("fiji_executable", bridge_config.fiji_executable)),
            macro_path=str(effective_profile.get("fiji_macro_path", bridge_config.macro_path)),
            thunderstorm_jar_path=str(
                effective_profile.get("thunderstorm_jar_path", bridge_config.thunderstorm_jar_path)
            ),
            command_template=str(
                effective_profile.get("fiji_command_template", bridge_config.command_template)
            ),
            pyimagej_app_path=str(
                effective_profile.get("pyimagej_app_path", bridge_config.pyimagej_app_path)
            ),
            timeout_sec=bridge_config.timeout_sec,
            plugin_parameters=self._build_plugin_parameters(params),
        )
        if (
            bridge_config.backend in {"fiji_subprocess", "fiji_pyimagej"}
            and not (bridge_config.plugin_jar_path or bridge_config.thunderstorm_jar_path)
        ):
            jar = discover_bundled_thunderstorm_jar()
            if jar is not None:
                bridge_config = ThunderstormBridgeConfig(
                    backend=bridge_config.backend,
                    fiji_executable=bridge_config.fiji_executable,
                    macro_path=bridge_config.macro_path,
                    plugin_id=bridge_config.plugin_id,
                    plugin_jar_path=str(jar),
                    thunderstorm_jar_path=str(jar),
                    command_template=bridge_config.command_template,
                    pyimagej_app_path=bridge_config.pyimagej_app_path,
                    timeout_sec=bridge_config.timeout_sec,
                    plugin_parameters=bridge_config.plugin_parameters,
                )
                if self.smlm_panel is not None:
                    self.smlm_panel.thunder.thunderstorm_jar_edit.setText(str(jar))

        err, warn = self._validate_smlm_params(params)
        if err:
            thunder.status_label.setText(err)
            return
        if warn:
            thunder.status_label.setText(warn)

        self.stop_playback_t()
        self._cancel_smlm()
        arr = self.primary_image.array
        t_count = int(arr.shape[0])
        _, z_idx = self._slice_indices(self.primary_image)
        full_h, full_w = arr.shape[2], arr.shape[3]
        if self.crop_rect is None or self.crop_rect[2] <= 0 or self.crop_rect[3] <= 0:
            x0, y0, x1, y1 = 0, 0, full_w, full_h
        else:
            cx, cy, cw, ch = self.crop_rect
            x0 = int(max(0, cx))
            y0 = int(max(0, cy))
            x1 = int(min(full_w, cx + cw))
            y1 = int(min(full_h, cy + ch))
        if x1 <= x0 or y1 <= y0:
            thunder.status_label.setText("Crop has zero area.")
            return
        crop_offset = (x0, y0)
        roi_rect_crop = (roi_rect[0] - x0, roi_rect[1] - y0, roi_rect[2], roi_rect[3])
        roi_mask = roi_mask_for_shape((y1 - y0, x1 - x0), roi_rect_crop, self.roi_shape)
        if not roi_mask.any():
            thunder.status_label.setText("ROI has no pixels in crop.")
            return

        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        job_gen = self._job_generation
        image_id = self.primary_image.id
        self._smlm_run_id += 1
        run_id = self._smlm_run_id
        self._record_smlm_run(
            "ThunderSTORM",
            params.__dict__,
            roi_rect,
            self.crop_rect,
            None,
            backend=bridge_config.backend,
            backend_config={
                "plugin_id": bridge_config.plugin_id,
                "plugin_jar_path": bridge_config.plugin_jar_path,
                "fiji_executable": bridge_config.fiji_executable,
                "fiji_macro_path": bridge_config.macro_path,
                "thunderstorm_jar_path": bridge_config.thunderstorm_jar_path,
                "fiji_command_template": bridge_config.command_template,
                "pyimagej_app_path": bridge_config.pyimagej_app_path,
            },
            runbook_enabled=runbook_state.enabled,
        )
        append_provenance_event(
            runbook_state,
            event_type="smlm_run_requested",
            payload={
                "method": "ThunderSTORM",
                "backend": bridge_config.backend,
                "plugin_id": bridge_config.plugin_id,
                "plugin_jar_path": bridge_config.plugin_jar_path,
                "image_path": str(self.primary_image.path),
                "thunderstorm_jar_path": bridge_config.thunderstorm_jar_path,
                "roi_rect": list(roi_rect),
                "crop_rect": list(self.crop_rect) if self.crop_rect is not None else None,
                "params": dict(params.__dict__),
                "runbook_enabled": bool(runbook_state.enabled),
            },
        )
        self._sync_runbook_state_to_session()

        def _job(progress, cancel_token):
            def _frames():
                for t in range(t_count):
                    if cancel_token.is_cancelled():
                        break
                    frame = arr[t, z_idx, :, :]
                    if x0 != 0 or y0 != 0 or x1 != full_w or y1 != full_h:
                        frame = frame[y0:y1, x0:x1]
                    yield (t, frame)

            def _progress_cb(val: int, msg: str) -> None:
                progress(val, msg)

            locs, sr, backend_meta = run_thunderstorm_backend(
                _frames(),
                total_frames=t_count,
                roi_mask=roi_mask,
                roi_rect=roi_rect,
                crop_offset=crop_offset,
                params=params,
                pixel_size_nm=pixel_size_nm,
                config=bridge_config,
                progress_cb=_progress_cb,
                is_cancelled=cancel_token.is_cancelled,
            )
            return (locs, sr, backend_meta, roi_rect, crop_offset, image_id, job_gen, run_id, t_count)

        def _on_result(result) -> None:
            if result is None:
                return
            locs, sr, backend_meta, roi_rect_full, crop_off, img_id, gen, res_run_id, frames = result
            if gen != self._job_generation or img_id != self.primary_image.id or res_run_id != self._smlm_run_id:
                return
            self._smlm_results = locs
            self._smlm_image_id = img_id  # Track which image these results are for
            self._smlm_overlay = sr
            off_x, off_y = crop_off
            self._smlm_overlay_extent = (
                roi_rect_full[0] - off_x,
                roi_rect_full[0] - off_x + roi_rect_full[2],
                roi_rect_full[1] - off_y + roi_rect_full[3],
                roi_rect_full[1] - off_y,
            )
            self._sr_overlay = self._smlm_overlay
            self._sr_overlay_extent = self._smlm_overlay_extent
            thunder.status_label.setText(f"Done: {len(locs)} localizations")
            thunder.progress.setValue(100)
            thunder.run_btn.setEnabled(True)
            thunder.cancel_btn.setEnabled(False)
            if hasattr(thunder, "set_localizations"):
                thunder.set_localizations(locs)
            self._append_log(
                f"[SMLM] ThunderSTORM backend={bridge_config.backend} "
                f"job={self._smlm_job_id} frames={frames} detections={len(locs)}"
            )
            if hasattr(thunder, "set_generated_macro"):
                thunder.set_generated_macro(str((backend_meta or {}).get("executed_macro", "")))
            if hasattr(thunder, "append_debug_report"):
                thunder.append_debug_report(self._build_smlm_debug_report(bridge_config, backend_meta=backend_meta))
            append_provenance_event(
                runbook_state,
                event_type="smlm_run_finished",
                payload={
                    "method": "ThunderSTORM",
                    "backend": bridge_config.backend,
                    "backend_meta": dict(backend_meta or {}),
                    "detections": int(len(locs)),
                    "frames": int(frames),
                },
            )
            self._sync_runbook_state_to_session()
            self._request_ui_refresh("smlm-controls")

        def _on_error(err: str) -> None:
            thunder.status_label.setText("Error (see Logs).")
            thunder.run_btn.setEnabled(True)
            thunder.cancel_btn.setEnabled(False)
            if hasattr(thunder, "clear_localizations"):
                thunder.clear_localizations()
            self._append_log(f"[SMLM] Error\n{err}")
            report_text = self._build_smlm_debug_report(
                bridge_config,
                backend_meta=None,
                error_text=err,
            )
            report_path = self._persist_smlm_error_report(report_text)
            if hasattr(thunder, "append_debug_report"):
                thunder.append_debug_report(report_text)
            self._show_smlm_failure_actions(
                bridge_config=bridge_config,
                report_path=report_path,
                error_text=err,
            )

        def _on_progress(val: int, msg: str) -> None:
            thunder.progress.setValue(val)
            if msg:
                thunder.status_label.setText(msg)

        handle = self.jobs.submit(
            _job,
            name="SMLM (ROI)",
            on_result=_on_result,
            on_error=_on_error,
            on_progress=_on_progress,
            timeout_sec=600.0,
            retries=2,  # P5.3: Increased from 1 to handle transient errors
            priority="interactive",
            replace_key="smlm-roi",
        )
        self._smlm_job_id = handle.job_id
        thunder.progress.setValue(0)
        thunder.status_label.setText("Running…")
        thunder.run_btn.setEnabled(False)
        thunder.cancel_btn.setEnabled(True)
        self._append_log(
            f"[SMLM] ThunderSTORM backend={bridge_config.backend} "
            f"started job={self._smlm_job_id} frames={t_count}"
        )

    def _build_smlm_debug_report(
        self,
        bridge_config: ThunderstormBridgeConfig,
        *,
        backend_meta: dict | None,
        error_text: str = "",
    ) -> str:
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
        lines: list[str] = []
        for raw in paths:
            p = pathlib.Path(raw)
            if p.exists():
                lines.append(f"  {p}: {p.stat().st_size} bytes")
            else:
                lines.append(f"  {p}: <missing>")
        return lines

    def _sha256_file(self, path: str) -> str:
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
        self.show_smlm_points = bool(checked)
        if getattr(self, "show_smlm_points_act", None) is not None:
            self.show_smlm_points_act.blockSignals(True)
            self.show_smlm_points_act.setChecked(bool(checked))
            self.show_smlm_points_act.blockSignals(False)
        self._request_ui_refresh("smlm-controls")

    def _export_smlm_csv(self) -> None:
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to export.")
            return
        settings = getattr(self, "_settings", None)
        default_dir = ""
        if settings is not None:
            default_dir = str(settings.value("smlmLastExportDir", "", type=str) or "")
        if not default_dir:
            default_dir = str(pathlib.Path.cwd())
        default_name = f"thunderstorm_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export SMLM CSV",
            str(pathlib.Path(default_dir) / default_name),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.export_localizations_csv(path)
        else:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "frame_index",
                        "x_px",
                        "y_px",
                        "sigma_px",
                        "photons",
                        "background",
                        "uncertainty_px",
                        "label",
                    ]
                )
                for loc in self._smlm_results:
                    writer.writerow(
                        [
                            loc.frame_index,
                            f"{loc.x_px:.4f}",
                            f"{loc.y_px:.4f}",
                            f"{loc.sigma_px:.4f}",
                            f"{loc.photons:.4f}",
                            f"{loc.background:.4f}",
                            f"{loc.uncertainty_px:.4f}",
                            loc.label or "",
                        ]
                    )
        if settings is not None:
            settings.setValue("smlmLastExportDir", str(pathlib.Path(path).parent))
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText(f"Exported CSV: {path}")

    def _export_smlm_hdf5(self) -> None:
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to export.")
            return
        try:
            import h5py
        except Exception:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("h5py not available.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export SMLM HDF5", "", "HDF5 Files (*.h5)")
        if not path:
            return
        data = np.zeros(
            (len(self._smlm_results),),
            dtype=[
                ("frame_index", "i4"),
                ("x_px", "f4"),
                ("y_px", "f4"),
                ("sigma_px", "f4"),
                ("photons", "f4"),
                ("background", "f4"),
                ("uncertainty_px", "f4"),
            ],
        )
        for i, loc in enumerate(self._smlm_results):
            data[i] = (loc.frame_index, loc.x_px, loc.y_px, loc.sigma_px, loc.photons, loc.background, loc.uncertainty_px)
        with h5py.File(path, "w") as f:
            f.create_dataset("localizations", data=data, compression="gzip")
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText(f"Exported HDF5: {path}")

    def _smlm_to_annotations(self) -> None:
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to add.")
            return
        if hasattr(self, "_ensure_annotation_write_context_confirmed"):
            if not self._ensure_annotation_write_context_confirmed("Import SMLM localizations"):
                return
        image_id = self.primary_image.id
        locs_to_add = list(self._smlm_results)
        if self.smlm_panel is not None:
            selected = self.smlm_panel.thunder.selected_localizations()
            if selected:
                locs_to_add = selected
        self._block_table = True
        for loc in locs_to_add:
            self.controller.add_annotation(
                image_id=image_id,
                image_name=self.primary_image.name,
                t=loc.frame_index,
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
            self.smlm_panel.thunder.status_label.setText(
                f"Added {len(locs_to_add)} localization(s) to annotations."
            )

    def _browse_deepstorm_model(self) -> None:
        if self.smlm_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Deep-STORM model", "", "Model Files (*.pt)"
        )
        if path:
            self.smlm_panel.deep.model_path_edit.setText(path)

    def _deepstorm_params_from_ui(self) -> Optional[DeepStormParams]:
        if self.smlm_panel is None:
            return None
        values = self.smlm_panel.deep.values()
        return DeepStormParams(
            model_path=values.model_path,
            patch_size=values.patch_size,
            overlap=values.overlap,
            upsample=values.upsample,
            sigma_px=values.sigma_px,
            normalize_mode=values.normalize_mode,
            output_mode=values.output_mode,
            window_size=values.window_size,
            aggregation_mode=values.aggregation_mode,
        )

    def _run_deepstorm(self) -> None:
        if self.smlm_panel is None:
            return
        deep = self.smlm_panel.deep
        if not is_torch_available():
            deep.status_label.setText("PyTorch not available.")
            return
        
        # Check GPU availability before running inference
        from phage_annotator.tools.utils.gpu_utils import check_cuda_available
        params_check = self._deepstorm_params_from_ui()
        if params_check and params_check.device in ("cuda", "auto"):
            cuda_ok, cuda_msg = check_cuda_available()
            if not cuda_ok and params_check.device == "cuda":
                from matplotlib.backends.qt_compat import QtWidgets
                QtWidgets.QMessageBox.warning(
                    self, 
                    "CUDA Not Available",
                    f"Cannot run Deep-STORM on GPU:\n\n{cuda_msg}\n\nPlease select 'CPU' device or install CUDA support."
                )
                return
            elif not cuda_ok and params_check.device == "auto":
                deep.status_label.setText("Running on CPU (CUDA unavailable)")
        
        self._ensure_loaded(self.current_image_idx)
        if self.primary_image.array is None:
            deep.status_label.setText("Load an image first.")
            return
        params = self._deepstorm_params_from_ui()
        if params is None or not params.model_path:
            deep.status_label.setText("Select a model first.")
            return
        roi_rect = self.roi_rect
        if roi_rect is None or roi_rect[2] <= 0 or roi_rect[3] <= 0:
            deep.status_label.setText("Set an ROI first.")
            if self.dock_roi is not None:
                self.set_panel_visible("roi", True, source="deepstorm_validation")
            return
        
        # Phase ζ: Get selected modality_idx from panel
        selected_modality_idx = self.smlm_panel.get_selected_modality_idx()
        self._deepstorm_modality_idx = selected_modality_idx
        
        err, warn = self._validate_deepstorm_params(params)
        if err:
            deep.status_label.setText(err)
            return
        if warn:
            deep.status_label.setText(warn)

        self.stop_playback_t()
        self._cancel_deepstorm()
        arr = self.primary_image.array
        t_count = int(arr.shape[0])
        _, z_idx = self._slice_indices(self.primary_image)
        full_h, full_w = arr.shape[2], arr.shape[3]
        if self.crop_rect is None or self.crop_rect[2] <= 0 or self.crop_rect[3] <= 0:
            x0, y0, x1, y1 = 0, 0, full_w, full_h
        else:
            cx, cy, cw, ch = self.crop_rect
            x0 = int(max(0, cx))
            y0 = int(max(0, cy))
            x1 = int(min(full_w, cx + cw))
            y1 = int(min(full_h, cy + ch))
        if x1 <= x0 or y1 <= y0:
            deep.status_label.setText("Crop has zero area.")
            return
        crop_offset = (x0, y0)
        roi_rect_crop = (roi_rect[0] - x0, roi_rect[1] - y0, roi_rect[2], roi_rect[3])
        crop_w = x1 - x0
        crop_h = y1 - y0
        rx0 = max(0.0, roi_rect_crop[0])
        ry0 = max(0.0, roi_rect_crop[1])
        rx1 = min(float(crop_w), roi_rect_crop[0] + roi_rect_crop[2])
        ry1 = min(float(crop_h), roi_rect_crop[1] + roi_rect_crop[3])
        if rx1 <= rx0 or ry1 <= ry0:
            deep.status_label.setText("ROI has no pixels in crop.")
            return
        eff_roi_full = (rx0 + x0, ry0 + y0, rx1 - rx0, ry1 - ry0)
        job_gen = self._job_generation
        image_id = self.primary_image.id
        self._deepstorm_run_id += 1
        run_id = self._deepstorm_run_id
        device = "cuda" if is_torch_available() and self._torch_has_cuda() else "cpu"
        model_hash = self._hash_file(params.model_path)
        self._record_smlm_run(
            "Deep-STORM",
            params.__dict__,
            eff_roi_full,
            self.crop_rect,
            {"path": params.model_path, "hash": model_hash},
        )

        def _job(progress, cancel_token):
            def _frames():
                for t in range(t_count):
                    if cancel_token.is_cancelled():
                        break
                    frame = arr[t, z_idx, :, :]
                    if x0 != 0 or y0 != 0 or x1 != full_w or y1 != full_h:
                        frame = frame[y0:y1, x0:x1]
                    if rx0 > 0 or ry0 > 0 or rx1 < crop_w or ry1 < crop_h:
                        frame = frame[int(ry0):int(ry1), int(rx0):int(rx1)]
                    yield (t, frame)

            def _progress_cb(val: int, msg: str) -> None:
                progress(val, msg)

            sr, locs = run_deepstorm_stream(
                _frames(),
                total_frames=t_count,
                roi_rect=eff_roi_full,
                params=params,
                device=device,
                progress_cb=_progress_cb,
                is_cancelled=cancel_token.is_cancelled,
            )
            return (sr, locs, eff_roi_full, crop_offset, image_id, job_gen, run_id, t_count)

        def _on_result(result) -> None:
            if result is None:
                return
            sr, locs, roi_rect_full, crop_off, img_id, gen, res_run_id, frames = result
            if gen != self._job_generation or img_id != self.primary_image.id or res_run_id != self._deepstorm_run_id:
                return
            self._deepstorm_results = locs
            self._deepstorm_image_id = img_id  # Track which image these results are for
            self._deepstorm_overlay = sr
            off_x, off_y = crop_off
            self._deepstorm_overlay_extent = (
                roi_rect_full[0] - off_x,
                roi_rect_full[0] - off_x + roi_rect_full[2],
                roi_rect_full[1] - off_y + roi_rect_full[3],
                roi_rect_full[1] - off_y,
            )
            self._sr_overlay = self._deepstorm_overlay
            self._sr_overlay_extent = self._deepstorm_overlay_extent
            deep.status_label.setText(f"Done: {len(locs)} localizations")
            deep.progress.setValue(100)
            deep.run_btn.setEnabled(True)
            deep.cancel_btn.setEnabled(False)
            self._append_log(
                f"[SMLM] Deep-STORM job={self._deepstorm_job_id} frames={frames} detections={len(locs)}"
            )
            self._request_ui_refresh("smlm-controls")

        def _on_error(err: str) -> None:
            deep.status_label.setText("Error (see Logs).")
            deep.run_btn.setEnabled(True)
            deep.cancel_btn.setEnabled(False)
            self._append_log(f"[Deep-STORM] Error\n{err}")

        def _on_progress(val: int, msg: str) -> None:
            deep.progress.setValue(val)
            if msg:
                deep.status_label.setText(msg)

        handle = self.jobs.submit(
            _job,
            name="Deep-STORM (ROI)",
            on_result=_on_result,
            on_error=_on_error,
            on_progress=_on_progress,
            timeout_sec=900.0,
            retries=2,  # P5.3: Increased from 1 to handle transient errors
            priority="interactive",
            replace_key="deepstorm-roi",
        )
        self._deepstorm_job_id = handle.job_id
        deep.progress.setValue(0)
        deep.status_label.setText(f"Running on {device}…")
        deep.run_btn.setEnabled(False)
        deep.cancel_btn.setEnabled(True)
        self._append_log(f"[SMLM] Deep-STORM started job={self._deepstorm_job_id} frames={t_count}")

    def _cancel_deepstorm(self) -> None:
        if self._deepstorm_job_id is None:
            return
        self.jobs.cancel(self._deepstorm_job_id)
        self._deepstorm_job_id = None
        if self.smlm_panel is not None:
            deep = self.smlm_panel.deep
            deep.status_label.setText("Cancelling…")
            deep.cancel_btn.setEnabled(False)
            deep.run_btn.setEnabled(True)

    def _export_deepstorm_csv(self) -> None:
        if not self._deepstorm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.deep.status_label.setText("No Deep-STORM results.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Deep-STORM CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x_px", "y_px", "score"])
            for loc in self._deepstorm_results:
                writer.writerow([f"{loc.x_px:.4f}", f"{loc.y_px:.4f}", f"{loc.score:.4f}"])
        if self.smlm_panel is not None:
            self.smlm_panel.deep.status_label.setText(f"Exported CSV: {path}")

    def _export_deepstorm_sr(self) -> None:
        if self._deepstorm_overlay is None:
            if self.smlm_panel is not None:
                self.smlm_panel.deep.status_label.setText("No SR image to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export SR Image", "", "TIFF Files (*.tif);;PNG Files (*.png)"
        )
        if not path:
            return
        if path.lower().endswith(".png"):
            from matplotlib import pyplot as plt

            plt.imsave(path, self._deepstorm_overlay, cmap="magma")
        else:
            import tifffile as tif

            tif.imwrite(path, self._deepstorm_overlay.astype(np.float32, copy=False))
        if self.smlm_panel is not None:
            self.smlm_panel.deep.status_label.setText(f"Exported SR image: {path}")

    def _deepstorm_to_annotations(self) -> None:
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
        try:
            import torch
        except Exception:
            return False
        return torch.cuda.is_available()

    def _apply_smlm_preset(self, name: str) -> None:
        if self.smlm_panel is None:
            return
        self.smlm_panel.apply_preset(name)

    def _validate_smlm_params(self, params: SmlmParams) -> Tuple[Optional[str], Optional[str]]:
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
        if getattr(self, "show_smlm_points_act", None) is not None:
            self.show_smlm_points = self.show_smlm_points_act.isChecked()
            if self.smlm_panel is not None and hasattr(self.smlm_panel.thunder, "show_points_chk"):
                self.smlm_panel.thunder.show_points_chk.blockSignals(True)
                self.smlm_panel.thunder.show_points_chk.setChecked(bool(self.show_smlm_points))
                self.smlm_panel.thunder.show_points_chk.blockSignals(False)
            self._request_ui_refresh("smlm-controls")

    def _toggle_smlm_sr(self) -> None:
        if getattr(self, "show_smlm_sr_act", None) is not None:
            self.show_sr_overlay = self.show_smlm_sr_act.isChecked()
            self._request_ui_refresh("smlm-controls")

    def _build_plugin_parameters(self, params: SmlmParams) -> dict:
        """Map current SMLM parameters into plugin manifest parameter names."""
        return {
            "sigma_px": float(params.sigma_px),
            "fit_radius_px": int(params.fit_radius_px),
            "filter_type": str(params.filter_type),
            "dog_sigma1": float(params.dog_sigma1),
            "dog_sigma2": float(params.dog_sigma2),
            "detection_thr_sigma": float(params.detection_thr_sigma),
            "max_candidates_per_frame": int(params.max_candidates_per_frame),
            "merge_radius_px": float(params.merge_radius_px),
            "min_photons": float(params.min_photons),
            "max_uncertainty_nm": float(params.max_uncertainty_nm),
            "upsample": int(params.upsample),
            "render_mode": str(params.render_mode),
            "render_sigma_nm": float(params.render_sigma_nm),
        }

    def _on_smlm_runbook_toggled(self, checked: bool) -> None:
        state = self._get_runbook_state()
        state.enabled = bool(checked)
        append_provenance_event(
            state,
            event_type="runbook_toggled",
            payload={"enabled": bool(checked)},
        )
        self._sync_runbook_state_to_session()
        self._status_info(
            "SMLM runbook mode enabled." if checked else "SMLM runbook mode disabled.",
            timeout_ms=2500,
            source="smlm.runbook.toggle",
        )
