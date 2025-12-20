"""Thresholding and particle analysis handlers."""

from __future__ import annotations

import csv
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis import roi_mask_for_shape
from phage_annotator.particles import ParticleOptions, analyze_particles
from phage_annotator.thresholding import (
    PostprocessOptions,
    compute_threshold,
    make_mask,
    postprocess_mask,
    smooth_image,
)


class ThresholdControlsMixin:
    """Mixin for thresholding and particle analysis handlers."""

    def _threshold_method_changed(self) -> None:
        if self.threshold_panel is None:
            return
        method = self.threshold_panel.method_combo.currentText()
        if method == "Manual":
            self._threshold_refresh_preview()
        else:
            self._threshold_auto()

    def _threshold_manual_changed(self) -> None:
        if self.threshold_panel is None:
            return
        if self.threshold_panel.method_combo.currentText() != "Manual":
            return
        self._threshold_timer.start()

    def _threshold_refresh_preview(self) -> None:
        if self.threshold_panel is None:
            return
        values = self.threshold_panel.values()
        if not values.preview:
            self._threshold_preview_mask = None
            self._threshold_preview_extent = None
            self._refresh_image()
            return

        image = self._threshold_source_image(values.target)
        if image is None:
            self.threshold_panel.status_label.setText("No image data.")
            return
        crop_offset = self._threshold_crop_offset(image.shape)
        data, roi_mask = self._threshold_apply_roi(image, values, crop_offset)
        if data is None:
            self.threshold_panel.status_label.setText("ROI empty.")
            return

        smooth = smooth_image(data, values.smooth_sigma)
        if values.method == "Manual":
            low, high = self._threshold_percentile_bounds(smooth, values, roi_mask)
            thr_low = low
            thr_high = high
        else:
            thr = self._threshold_auto_value
            if thr is None or np.isnan(thr):
                return
            thr_low = float(thr)
            thr_high = None

        mask = make_mask(smooth, thr_low, thr_high, invert=values.invert_mask)
        opts = PostprocessOptions(
            min_area_px=values.min_area_px,
            fill_holes=values.fill_holes,
            open_radius_px=values.open_radius_px,
            close_radius_px=values.close_radius_px,
            despeckle=values.despeckle,
            watershed_split=values.watershed_split,
        )
        mask = postprocess_mask(mask, opts)
        self._threshold_preview_mask = mask
        self._threshold_preview_extent = (0, mask.shape[1], mask.shape[0], 0)
        self._threshold_mask_full = self._threshold_to_full_mask(mask, crop_offset, image.shape)
        self._threshold_settings = values.__dict__
        self.controller.session_state.threshold_settings = dict(self._threshold_settings)
        self.controller.session_state.threshold_configs_by_image[self.primary_image.id] = dict(self._threshold_settings)
        self._append_log(self._threshold_log_message(values, self._threshold_auto_value))
        self.recorder.record("threshold_preview", self._threshold_settings)
        self._refresh_image()

    def _threshold_auto(self) -> None:
        if self.threshold_panel is None:
            return
        values = self.threshold_panel.values()
        if values.method == "Manual":
            return
        if self._threshold_job_id is not None:
            self.jobs.cancel(self._threshold_job_id)
            self._threshold_job_id = None

        image = self._threshold_source_image(values.target)
        if image is None:
            self.threshold_panel.status_label.setText("No image data.")
            return
        crop_offset = self._threshold_crop_offset(image.shape)
        data, roi_mask = self._threshold_apply_roi(image, values, crop_offset)
        if data is None:
            self.threshold_panel.status_label.setText("ROI empty.")
            return

        def _job(progress, cancel_token):
            pixels = self._threshold_sample_pixels(values, roi_mask, data)
            if cancel_token.is_cancelled():
                return float("nan")
            thr = compute_threshold(pixels, values.method, background=values.background)
            return float(thr)

        def _on_result(result: float) -> None:
            self._threshold_auto_value = result
            if result is None or np.isnan(result):
                self.threshold_panel.status_label.setText("Auto method unavailable.")
                self.threshold_panel.auto_value.setText("Auto: —")
                return
            self.threshold_panel.auto_value.setText(f"Auto: {result:.4f}")
            self.recorder.record(
                "threshold_auto",
                {
                    "method": values.method,
                    "value": float(result),
                    "region_roi": values.region_roi,
                    "scope": values.scope,
                },
            )
            self._threshold_refresh_preview()

        def _on_error(err: str) -> None:
            self.threshold_panel.status_label.setText("Auto threshold failed.")
            self._append_log(f"[Threshold] Error\n{err}")

        handle = self.jobs.submit(_job, name="Threshold Auto", on_result=_on_result, on_error=_on_error)
        self._threshold_job_id = handle.job_id
        self.threshold_panel.status_label.setText(f"Computing {values.method}…")

    def _threshold_source_image(self, target: str) -> Optional[np.ndarray]:
        prim = self.primary_image
        if prim.array is None:
            return None
        if target == "Frame":
            return self._slice_data(prim)
        if target == "Mean":
            data, _ = self._get_projection(prim, "mean")
            return data
        if target == "Composite":
            data, _ = self._get_projection(prim, "composite")
            return data
        if target == "Support":
            if self.support_image.array is None:
                return None
            return self._slice_data(self.support_image)
        return self._slice_data(prim)

    def _threshold_crop_offset(self, shape: Tuple[int, int]) -> Tuple[int, int]:
        if not self.crop_rect:
            return (0, 0)
        x, y, _, _ = self.crop_rect
        return (int(max(0, x)), int(max(0, y)))

    def _threshold_apply_roi(
        self, image: np.ndarray, values, crop_offset: Tuple[int, int]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        data = image
        if self.crop_rect:
            data = self._apply_crop_rect(data, self.crop_rect, image.shape)
        roi_mask = None
        if values.region_roi:
            x0, y0 = crop_offset
            if self.roi_rect is None:
                return None, None
            roi_rect = (self.roi_rect[0] - x0, self.roi_rect[1] - y0, self.roi_rect[2], self.roi_rect[3])
            roi_mask = roi_mask_for_shape(data.shape, roi_rect, self.roi_shape)
            if not roi_mask.any():
                return None, None
        return data, roi_mask

    def _threshold_percentile_bounds(
        self, data: np.ndarray, values, roi_mask: Optional[np.ndarray]
    ) -> Tuple[float, float]:
        sample = data[roi_mask] if roi_mask is not None else data.ravel()
        low = float(np.percentile(sample, values.manual_low_pct))
        high = float(np.percentile(sample, values.manual_high_pct))
        return low, high

    def _threshold_sample_pixels(self, values, roi_mask: Optional[np.ndarray], data: np.ndarray) -> np.ndarray:
        if values.scope == "Current slice":
            sample = data[roi_mask] if roi_mask is not None else data
            return sample.ravel()

        prim = self.primary_image
        if prim.array is None:
            return data.ravel()
        t_count = int(prim.array.shape[0])
        n = min(values.sample_count, t_count)
        # Deterministic frame selection for reproducibility (P3.2)
        idxs = np.linspace(0, t_count - 1, n).astype(int)
        pixels = []
        for t in idxs:
            frame = prim.array[t, self.z_slider.value(), :, :]
            if self.crop_rect:
                frame = self._apply_crop_rect(frame, self.crop_rect, frame.shape)
            if roi_mask is not None:
                pixels.append(frame[roi_mask])
            else:
                pixels.append(frame.ravel())
        if not pixels:
            return np.array([])
        return np.concatenate(pixels)

    def _threshold_to_full_mask(
        self, mask: np.ndarray, crop_offset: Tuple[int, int], full_shape: Tuple[int, int]
    ) -> np.ndarray:
        full = np.zeros(full_shape, dtype=bool)
        x0, y0 = crop_offset
        y1 = min(full_shape[0], y0 + mask.shape[0])
        x1 = min(full_shape[1], x0 + mask.shape[1])
        full[y0:y1, x0:x1] = mask[: y1 - y0, : x1 - x0]
        return full

    def _threshold_create_mask(self) -> None:
        if self._threshold_mask_full is None:
            self._set_status("No threshold mask to save.")
            return
        image_id = self.primary_image.id
        self.controller.session_state.threshold_masks[image_id] = {
            "t": int(self.t_slider.value()),
            "z": int(self.z_slider.value()),
            "mask": self._threshold_mask_full.copy(),
        }
        self._set_status("Threshold mask stored for current slice.")
        if self.threshold_panel is not None:
            self._append_log(self._threshold_log_message(self.threshold_panel.values(), self._threshold_auto_value))
            self.recorder.record("threshold_create_mask", self._threshold_settings)

    def _threshold_create_roi(self) -> None:
        if self._threshold_mask_full is None:
            self._set_status("No threshold mask to convert.")
            return
        mask = self._threshold_mask_full
        try:
            from scipy import ndimage as ndi
        except Exception:
            ndi = None
        if ndi is None:
            ys, xs = np.nonzero(mask)
            if ys.size == 0:
                self._set_status("Mask empty.")
                return
            x0, x1 = xs.min(), xs.max()
            y0, y1 = ys.min(), ys.max()
        else:
            labeled, n = ndi.label(mask)
            if n == 0:
                self._set_status("Mask empty.")
                return
            sizes = ndi.sum(mask, labeled, range(1, n + 1))
            idx = int(np.argmax(sizes)) + 1
            ys, xs = np.nonzero(labeled == idx)
            x0, x1 = xs.min(), xs.max()
            y0, y1 = ys.min(), ys.max()
        rect = (float(x0), float(y0), float(x1 - x0), float(y1 - y0))
        self.controller.set_roi(rect, shape="box")
        self.roi_shape = "box"
        self.roi_rect = rect
        self._sync_roi_controls()
        self._refresh_image()

    def _threshold_analyze_particles(self) -> None:
        self._show_analyze_particles_panel()

    def _threshold_apply_destructive(self) -> None:
        if self.threshold_panel is None:
            return
        if self._threshold_preview_mask is None:
            self._set_status("No threshold preview to apply.")
            return
        # P1.4: Confirmation with "Don't show again" toggle stored in settings
        if self._settings.value("confirmApplyThreshold", True, type=bool):
            mbox = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Question,
                "Apply Threshold",
                "Replace the current view with a binary mask layer?",
                parent=self,
            )
            mbox.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
            )
            dont = QtWidgets.QCheckBox("Don't show again")
            mbox.setCheckBox(dont)
            resp = mbox.exec()
            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            if dont.isChecked():
                self._settings.setValue("confirmApplyThreshold", False)
        if self._threshold_mask_full is None:
            image = self._threshold_source_image(self.threshold_panel.values().target)
            if image is None:
                return
            crop_offset = self._threshold_crop_offset(image.shape)
            self._threshold_mask_full = self._threshold_to_full_mask(
                self._threshold_preview_mask, crop_offset, image.shape
            )
        self._binary_view_mask = self._threshold_mask_full
        self._binary_view_enabled = True
        self._threshold_preview_mask = None
        self._threshold_preview_extent = None
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._set_status("Binary mask applied to view.")
        self.recorder.record("threshold_apply", self._threshold_settings)
        self._append_log(self._threshold_log_message(self.threshold_panel.values(), self._threshold_auto_value))
        self._refresh_image()

    def _run_analyze_particles(self) -> None:
        if self.particles_panel is None:
            return
        image_id = self.primary_image.id
        mask_entry = self.controller.session_state.threshold_masks.get(image_id)
        if mask_entry is None:
            self.particles_panel.status_label.setText("No threshold mask. Create one first.")
            return
        values = self.particles_panel.values()
        if values.clear_previous:
            self._particles_results = []
        opts = ParticleOptions(
            min_area_px=values.min_area,
            max_area_px=None if values.max_area <= 0 else values.max_area,
            min_circularity=values.min_circ,
            max_circularity=values.max_circ,
            exclude_edges=values.exclude_edges,
            include_holes=values.include_holes,
            watershed_split=values.watershed_split,
        )
        self.controller.session_state.particles_configs_by_image[self.primary_image.id] = values.__dict__

        if values.scope == "Current slice":
            if mask_entry.get("t") != int(self.t_slider.value()) or mask_entry.get("z") != int(
                self.z_slider.value()
            ):
                self.particles_panel.status_label.setText("Mask not for current slice.")
                return
            mask = mask_entry.get("mask")
            if mask is None:
                return
            if values.region_roi:
                roi_mask = roi_mask_for_shape(mask.shape, self.roi_rect, self.roi_shape)
                mask = mask & roi_mask
            particles = analyze_particles(mask, int(self.t_slider.value()), opts)
            self._particles_results.extend(particles)
            self._populate_particles_table()
            self._particles_refresh_overlay()
            self.particles_panel.status_label.setText(f"Found {len(particles)} particles.")
            self._append_log(self._particles_log_message(particles, opts))
            self.recorder.record("analyze_particles", values.__dict__)
            return

        settings = dict(self._threshold_settings)
        if not settings:
            self.particles_panel.status_label.setText("No threshold settings stored.")
            return
        if self._particles_job_id is not None:
            self.jobs.cancel(self._particles_job_id)
            self._particles_job_id = None
        arr = self.primary_image.array
        if arr is None:
            return
        t_count = int(arr.shape[0])
        z_idx = int(self.z_slider.value())
        crop_rect = self.crop_rect
        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        region_roi = values.region_roi

        def _job(progress, cancel_token):
            all_parts = []
            for t in range(t_count):
                if cancel_token.is_cancelled():
                    return None
                frame = arr[t, z_idx, :, :]
                crop_off_x = 0
                crop_off_y = 0
                if crop_rect:
                    frame = self._apply_crop_rect(frame, crop_rect, frame.shape)
                    crop_off_x = int(max(0, crop_rect[0]))
                    crop_off_y = int(max(0, crop_rect[1]))
                if settings.get("smooth_sigma", 0.0) > 0:
                    frame = smooth_image(frame, float(settings.get("smooth_sigma", 0.0)))
                roi_mask = None
                if region_roi and roi_rect is not None:
                    if crop_rect:
                        roi_local = (
                            roi_rect[0] - crop_off_x,
                            roi_rect[1] - crop_off_y,
                            roi_rect[2],
                            roi_rect[3],
                        )
                    else:
                        roi_local = roi_rect
                    roi_mask = roi_mask_for_shape(frame.shape, roi_local, roi_shape)
                if settings.get("method") == "Manual":
                    low = float(
                        np.percentile(
                            frame[roi_mask] if roi_mask is not None else frame.ravel(),
                            settings.get("manual_low_pct", 20),
                        )
                    )
                    high = float(
                        np.percentile(
                            frame[roi_mask] if roi_mask is not None else frame.ravel(),
                            settings.get("manual_high_pct", 99),
                        )
                    )
                    mask = make_mask(frame, low, high, invert=bool(settings.get("invert_mask", False)))
                else:
                    thr = compute_threshold(
                        frame[roi_mask] if roi_mask is not None else frame.ravel(),
                        settings.get("method", "Otsu"),
                        background=settings.get("background", "dark"),
                    )
                    mask = make_mask(frame, float(thr), None, invert=bool(settings.get("invert_mask", False)))
                post = PostprocessOptions(
                    min_area_px=int(settings.get("min_area_px", 5)),
                    fill_holes=bool(settings.get("fill_holes", False)),
                    open_radius_px=int(settings.get("open_radius_px", 1)),
                    close_radius_px=int(settings.get("close_radius_px", 1)),
                    despeckle=bool(settings.get("despeckle", False)),
                    watershed_split=bool(settings.get("watershed_split", False)),
                )
                mask = postprocess_mask(mask, post)
                parts = analyze_particles(mask, t, opts)
                if crop_off_x or crop_off_y:
                    parts = [self._offset_particle(p, crop_off_x, crop_off_y) for p in parts]
                all_parts.extend(parts)
                progress(int((t + 1) / t_count * 100), f"Frames {t+1}/{t_count}")
            return all_parts

        def _on_result(result):
            if result is None:
                return
            self._particles_results = list(result)
            self._populate_particles_table()
            self._particles_refresh_overlay()
            self.particles_panel.status_label.setText(f"Found {len(result)} particles.")
            self._append_log(self._particles_log_message(result, opts))
            self.recorder.record("analyze_particles", values.__dict__)

        def _on_error(err: str) -> None:
            self.particles_panel.status_label.setText("Analyze failed.")
            self._append_log(f"[Particles] Error\n{err}")

        handle = self.jobs.submit(_job, name="Analyze Particles", on_result=_on_result, on_error=_on_error)
        self._particles_job_id = handle.job_id
        self.particles_panel.status_label.setText("Running…")

    def _populate_particles_table(self) -> None:
        if self.particles_panel is None:
            return
        tbl = self.particles_panel.table
        tbl.blockSignals(True)
        tbl.setRowCount(len(self._particles_results))
        for row, p in enumerate(self._particles_results):
            tbl.setItem(row, 0, QtWidgets.QTableWidgetItem(str(p.frame_index)))
            tbl.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{p.area_px}"))
            tbl.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{p.perimeter_px:.2f}"))
            tbl.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{p.circularity:.2f}"))
            tbl.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{p.centroid_x:.2f}"))
            tbl.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{p.centroid_y:.2f}"))
            tbl.setItem(row, 6, QtWidgets.QTableWidgetItem(f"{p.eq_diameter:.2f}"))
            tbl.setItem(row, 7, QtWidgets.QTableWidgetItem(str(p.bbox)))
        tbl.blockSignals(False)
        tbl.resizeColumnsToContents()

    def _particles_selection_changed(self) -> None:
        if self.particles_panel is None:
            return
        rows = {idx.row() for idx in self.particles_panel.table.selectionModel().selectedRows()}
        self._particles_selected = next(iter(rows), None)
        self._particles_refresh_overlay()

    def _particles_refresh_overlay(self) -> None:
        self._particles_overlays = []
        if self.particles_panel is None:
            return
        show_outline = self.particles_panel.show_outlines_chk.isChecked()
        show_boxes = self.particles_panel.show_boxes_chk.isChecked()
        show_ellipse = self.particles_panel.show_ellipses_chk.isChecked()
        scale = self._axis_scale(self.ax_frame) if self.ax_frame is not None else 1.0
        off_x = self.crop_rect[0] if self.crop_rect else 0.0
        off_y = self.crop_rect[1] if self.crop_rect else 0.0
        for idx, p in enumerate(self._particles_results):
            selected = self._particles_selected == idx
            color = "#ffb000" if not selected else "#ff0000"
            if show_outline and p.outline:
                pts = [((x - off_x) / scale, (y - off_y) / scale) for x, y in p.outline]
                self._particles_overlays.append(("outline", pts, color, selected))
            if show_boxes:
                x, y, w, h = p.bbox
                self._particles_overlays.append(
                    ("box", ((x - off_x) / scale, (y - off_y) / scale, w / scale, h / scale), color, selected)
                )
            if show_ellipse:
                x, y, w, h = p.bbox
                self._particles_overlays.append(
                    ("ellipse", ((x - off_x) / scale, (y - off_y) / scale, w / scale, h / scale), color, selected)
                )
        self._refresh_image()

    def _export_particles_csv(self) -> None:
        if not self._particles_results:
            self.particles_panel.status_label.setText("No particle results.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Particles CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "frame",
                    "area_px",
                    "perimeter_px",
                    "circularity",
                    "centroid_x",
                    "centroid_y",
                    "eq_diameter",
                    "bbox",
                ]
            )
            for p in self._particles_results:
                writer.writerow(
                    [
                        p.frame_index,
                        p.area_px,
                        f"{p.perimeter_px:.3f}",
                        f"{p.circularity:.3f}",
                        f"{p.centroid_x:.3f}",
                        f"{p.centroid_y:.3f}",
                        f"{p.eq_diameter:.3f}",
                        p.bbox,
                    ]
                )
        self.particles_panel.status_label.setText(f"Exported CSV: {path}")

    def _particles_create_selection(self) -> None:
        if not self._particles_results:
            self.particles_panel.status_label.setText("No particles to select.")
            return
        xs = []
        ys = []
        for p in self._particles_results:
            x, y, w, h = p.bbox
            xs.extend([x, x + w])
            ys.extend([y, y + h])
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        rect = (float(x0), float(y0), float(x1 - x0), float(y1 - y0))
        self.controller.set_roi(rect, shape="box")
        self.roi_shape = "box"
        self.roi_rect = rect
        self._sync_roi_controls()
        self._refresh_image()

    def _offset_particle(self, particle, dx: int, dy: int):
        bbox = particle.bbox
        outline = None
        if particle.outline:
            outline = [(x + dx, y + dy) for x, y in particle.outline]
        return type(particle)(
            frame_index=particle.frame_index,
            area_px=particle.area_px,
            perimeter_px=particle.perimeter_px,
            circularity=particle.circularity,
            centroid_x=particle.centroid_x + dx,
            centroid_y=particle.centroid_y + dy,
            bbox=(bbox[0] + dx, bbox[1] + dy, bbox[2], bbox[3]),
            eq_diameter=particle.eq_diameter,
            outline=outline,
        )

    def _particles_log_message(self, particles, opts: ParticleOptions) -> str:
        return (
            "[Particles] count={count} min_area={min_area} max_area={max_area} "
            "circ={cmin:.2f}-{cmax:.2f} exclude_edges={edge} watershed={ws}"
        ).format(
            count=len(particles),
            min_area=opts.min_area_px,
            max_area=opts.max_area_px if opts.max_area_px is not None else "inf",
            cmin=opts.min_circularity,
            cmax=opts.max_circularity,
            edge=opts.exclude_edges,
            ws=opts.watershed_split,
        )

    def _threshold_log_message(self, values, thr_value: Optional[float]) -> str:
        thr = thr_value if thr_value is not None else float("nan")
        return (
            "[Threshold] method={method} thr={thr:.4f} region_roi={roi} scope={scope} "
            "invert={invert} smooth={smooth:.2f} post(min={min_area}, open={open_r}, close={close_r}, "
            "holes={holes}, ws={ws})"
        ).format(
            method=values.method,
            thr=thr,
            roi=values.region_roi,
            scope=values.scope,
            invert=values.invert_mask,
            smooth=values.smooth_sigma,
            min_area=values.min_area_px,
            open_r=values.open_radius_px,
            close_r=values.close_radius_px,
            holes=values.fill_holes,
            ws=values.watershed_split,
        )
