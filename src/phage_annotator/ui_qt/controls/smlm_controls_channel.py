"""Extracted method group 2 for SmlmControlsMixin."""

from __future__ import annotations

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.smlm.backends import (
    ThunderstormBridgeConfig,
    discover_bundled_thunderstorm_jar,
    run_thunderstorm_backend,
)
from phage_annotator.smlm.reproducibility import (
    append_provenance_event,
    resolve_profile,
)
from phage_annotator.smlm.thunderstorm import SmlmParams

class SmlmControlsChannelMixin:
    """Method group 2 extracted from SmlmControlsMixin."""

    def _run_smlm(self) -> None:
        """Run smlm for the current workflow."""
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
            """Handle the job helper flow."""
            def _frames():
                """Handle the frames helper flow."""
                for t in range(t_count):
                    if cancel_token.is_cancelled():
                        break
                    frame = arr[t, z_idx, :, :]
                    if x0 != 0 or y0 != 0 or x1 != full_w or y1 != full_h:
                        frame = frame[y0:y1, x0:x1]
                    yield (t, frame)

            def _progress_cb(val: int, msg: str) -> None:
                """Handle the progress cb helper flow."""
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
            """Handle the on result helper flow."""
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
            """Handle the on error helper flow."""
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
            """Handle the on progress helper flow."""
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
