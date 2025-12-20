"""SMLM (ThunderSTORM/Deep-STORM) handlers."""

from __future__ import annotations

import csv
import pathlib
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis import roi_mask_for_shape
from phage_annotator.deepstorm_infer import DeepStormParams, is_torch_available, run_deepstorm_stream
from phage_annotator.smlm_thunderstorm import SmlmParams, run_smlm_stream


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
                self.dock_roi.setVisible(True)
            return
        params = self._smlm_params_from_ui()
        if params is None:
            return
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
        self._record_smlm_run("ThunderSTORM", params.__dict__, roi_rect, self.crop_rect, None)

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

            locs, sr = run_smlm_stream(
                _frames(),
                total_frames=t_count,
                roi_mask=roi_mask,
                roi_rect=roi_rect,
                crop_offset=crop_offset,
                params=params,
                pixel_size_nm=pixel_size_nm,
                progress_cb=_progress_cb,
                is_cancelled=cancel_token.is_cancelled,
            )
            return (locs, sr, roi_rect, crop_offset, image_id, job_gen, run_id, t_count)

        def _on_result(result) -> None:
            if result is None:
                return
            locs, sr, roi_rect_full, crop_off, img_id, gen, res_run_id, frames = result
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
            self._append_log(
                f"[SMLM] ThunderSTORM job={self._smlm_job_id} frames={frames} detections={len(locs)}"
            )
            self._refresh_image()

        def _on_error(err: str) -> None:
            thunder.status_label.setText("Error (see Logs).")
            thunder.run_btn.setEnabled(True)
            thunder.cancel_btn.setEnabled(False)
            self._append_log(f"[SMLM] Error\n{err}")

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
        )
        self._smlm_job_id = handle.job_id
        thunder.progress.setValue(0)
        thunder.status_label.setText("Running…")
        thunder.run_btn.setEnabled(False)
        thunder.cancel_btn.setEnabled(True)
        self._append_log(f"[SMLM] ThunderSTORM started job={self._smlm_job_id} frames={t_count}")

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

    def _export_smlm_csv(self) -> None:
        if not self._smlm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.thunder.status_label.setText("No SMLM results to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export SMLM CSV", "", "CSV Files (*.csv)")
        if not path:
            return
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
        image_id = self.primary_image.id
        self._block_table = True
        for loc in self._smlm_results:
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
        self._refresh_image()
        self._mark_dirty()
        if self.smlm_panel is not None:
            self.smlm_panel.thunder.status_label.setText("Added to annotations.")

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
                self.dock_roi.setVisible(True)
            return
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
            self._refresh_image()

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
        self._refresh_image()
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
    ) -> None:
        from datetime import datetime

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "method": method,
            "params": params,
            "roi_rect": roi_rect,
            "roi_shape": self.roi_shape,
            "crop_rect": crop_rect,
            "image_path": str(self.primary_image.path),
            "model": model,
        }
        self._smlm_run_history.append(entry)
        self._last_smlm_run = entry
        self.controller.session_state.smlm_runs = list(self._smlm_run_history)

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
            self._set_status("No SMLM run to re-run.")
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

    def _toggle_smlm_points(self) -> None:
        if getattr(self, "show_smlm_points_act", None) is not None:
            self.show_smlm_points = self.show_smlm_points_act.isChecked()
            self._refresh_image()

    def _toggle_smlm_sr(self) -> None:
        if getattr(self, "show_smlm_sr_act", None) is not None:
            self.show_sr_overlay = self.show_smlm_sr_act.isChecked()
            self._refresh_image()
