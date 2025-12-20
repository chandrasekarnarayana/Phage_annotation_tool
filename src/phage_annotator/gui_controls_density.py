"""Density model inference controls."""

from __future__ import annotations

import csv

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.density_config import DensityConfig
from phage_annotator.density_infer import DensityInferOptions, run_density_inference
from phage_annotator.density_model import DensityPredictor


class DensityControlsMixin:
    """Mixin for density model inference controls."""

    def _density_pick_model(self) -> None:
        if self.density_panel is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select model", "", "PyTorch Model (*.pt *.pth)")
        if not path:
            return
        self.density_panel.model_path_edit.setText(path)

    def _density_load_model(self) -> None:
        if self.density_panel is None:
            return
        path = self.density_panel.model_path_edit.text().strip()
        if not path:
            self.density_panel.model_status.setText("Select a model first.")
            return
        device = self.density_panel.device_combo.currentText()
        predictor = DensityPredictor()
        try:
            predictor.load(path, device=device)
        except Exception as exc:
            self.density_panel.model_status.setText(f"Load failed: {exc}")
            return
        self.controller.density_predictor = predictor
        self.controller.density_model_path = path
        self.controller.density_device = device
        self.density_panel.model_status.setText(f"Loaded: {path}")
        self._settings.setValue("densityModelPath", path)
        self._settings.setValue("densityDevice", device)

    def _density_run(self) -> None:
        if self.density_panel is None:
            return
        predictor = self.controller.density_predictor
        if predictor is None:
            self.density_panel.model_status.setText("Load a model first.")
            return
        if self.primary_image.array is None:
            self.density_panel.model_status.setText("Load an image first.")
            return
        opts = self._density_infer_options_from_ui()
        cfg = self._density_config_from_ui()
        panel = self.density_panel.target_combo.currentText().lower()
        self._density_last_panel = panel
        self.controller.density_target_panel = panel
        self._settings.setValue("densityTargetPanel", panel)

        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        roi_spec = (self.roi_shape, self.roi_rect) if roi_active else None
        crop_rect = self.crop_rect
        t_idx = self.t_slider.value()
        z_idx = self.z_slider.value()
        panel_frame = self._export_panel_frame(self.primary_image, self.support_image, t_idx, z_idx, panel, None)
        if panel_frame is None:
            self.density_panel.model_status.setText("Panel data unavailable.")
            return

        snapshot = {
            "roi_rect": self.roi_rect,
            "crop_rect": self.crop_rect,
            "t": t_idx,
            "z": z_idx,
            "panel": panel,
        }

        def _job(progress, cancel_token):
            if cancel_token.is_cancelled():
                return None
            result = run_density_inference(
                panel_frame,
                predictor,
                cfg,
                roi_spec=roi_spec if opts.use_roi_only else None,
                crop_rect=crop_rect,
                options=opts,
            )
            return result

        def _on_result(result):
            if result is None:
                return
            if (
                snapshot["roi_rect"] != self.roi_rect
                or snapshot["crop_rect"] != self.crop_rect
                or snapshot["t"] != self.t_slider.value()
                or snapshot["z"] != self.z_slider.value()
                or snapshot["panel"] != self._density_last_panel
            ):
                self.density_panel.model_status.setText("Result stale (view changed).")
                self.density_panel.run_btn.setEnabled(True)
                self.density_panel.cancel_btn.setEnabled(False)
                return
            self._density_last_result = result
            self._density_image_id = self.primary_image.id  # Track which image results are for
            if self.density_panel.overlay_chk.isChecked():
                self._density_overlay = result.density_map
                self._density_overlay_extent = (0, result.density_map.shape[1], result.density_map.shape[0], 0)
            else:
                self._density_overlay = None
                self._density_overlay_extent = None
            self._density_overlay_alpha = float(self.density_panel.overlay_alpha.value())
            self._density_overlay_cmap = self.density_panel.overlay_cmap.currentText()
            self._density_contours = self.density_panel.contours_chk.isChecked()
            self.density_panel.count_total_label.setText(f"Total: {result.count_total:.2f}")
            roi_count = "-" if result.count_roi is None else f"{result.count_roi:.2f}"
            self.density_panel.count_roi_label.setText(f"ROI: {roi_count}")
            self._set_status(f"Density count: {result.count_total:.2f}")
            self._refresh_image()
            self.density_panel.run_btn.setEnabled(True)
            self.density_panel.cancel_btn.setEnabled(False)

        self.density_panel.run_btn.setEnabled(False)
        self.density_panel.cancel_btn.setEnabled(True)
        handle = self.jobs.submit(_job, name="Density inference", on_result=_on_result)
        self._density_job_id = handle.job_id
        self.density_panel.model_status.setText("Running…")

    def _density_cancel(self) -> None:
        if self._density_job_id is None:
            return
        self.jobs.cancel(self._density_job_id)
        self._density_job_id = None
        if self.density_panel is not None:
            self.density_panel.cancel_btn.setEnabled(False)
            self.density_panel.run_btn.setEnabled(True)
            self.density_panel.model_status.setText("Cancelled.")

    def _density_config_from_ui(self) -> DensityConfig:
        if self.density_panel is None:
            return DensityConfig()
        normalize = self.density_panel.normalize_combo.currentText()
        config = DensityConfig(
            normalize=normalize,
            p_low=float(self.density_panel.p_low_spin.value()),
            p_high=float(self.density_panel.p_high_spin.value()),
            invert=self.density_panel.invert_chk.isChecked(),
        )
        self.controller.density_config = config
        self._settings.setValue("densityConfig", config.__dict__)
        return config

    def _density_infer_options_from_ui(self) -> DensityInferOptions:
        if self.density_panel is None:
            return DensityInferOptions()
        opts = DensityInferOptions(
            tile_size=int(self.density_panel.tile_size_spin.value()),
            overlap=int(self.density_panel.overlap_spin.value()),
            batch_tiles=int(self.density_panel.batch_spin.value()),
            use_roi_only=self.density_panel.roi_only_chk.isChecked(),
            return_full_frame=False,
        )
        self.controller.density_infer_options = opts
        self._settings.setValue("densityInferOptions", opts.__dict__)
        return opts

    def _density_overlay_toggle(self) -> None:
        if self._density_last_result is None:
            return
        if self.density_panel.overlay_chk.isChecked():
            self._density_overlay = self._density_last_result.density_map
            self._density_overlay_extent = (
                0,
                self._density_last_result.density_map.shape[1],
                self._density_last_result.density_map.shape[0],
                0,
            )
        else:
            self._density_overlay = None
            self._density_overlay_extent = None
        self._refresh_image()

    def _density_overlay_changed(self) -> None:
        if self._density_last_result is None:
            return
        self._density_overlay_alpha = float(self.density_panel.overlay_alpha.value())
        self._density_overlay_cmap = self.density_panel.overlay_cmap.currentText()
        self._density_contours = self.density_panel.contours_chk.isChecked()
        self._refresh_image()

    def _density_export_map(self) -> None:
        if self._density_last_result is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save density map", "", "TIFF (*.tif *.tiff);;NumPy (*.npy)"
        )
        if not path:
            return
        if path.endswith(".npy"):
            import numpy as np

            np.save(path, self._density_last_result.density_map.astype("float32"))
        else:
            import tifffile

            tifffile.imwrite(path, self._density_last_result.density_map.astype("float32"))

    def _density_export_counts(self) -> None:
        if self._density_last_result is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save counts", "", "CSV (*.csv)")
        if not path:
            return
        roi_txt = "-" if self._density_last_result.count_roi is None else f"{self._density_last_result.count_roi:.4f}"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["image", "t", "z", "count_total", "count_roi", "roi", "crop", "panel"])
            writer.writerow(
                [
                    self.primary_image.name,
                    self.t_slider.value(),
                    self.z_slider.value(),
                    f"{self._density_last_result.count_total:.4f}",
                    roi_txt,
                    self.roi_rect,
                    self.crop_rect,
                    self._density_last_panel,
                ]
            )
