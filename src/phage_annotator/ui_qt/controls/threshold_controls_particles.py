"""Thresholding and particle analysis handlers."""

from __future__ import annotations

import csv
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.analysis.particles import ParticleOptions, analyze_particles
from phage_annotator.analysis.threshold import (
    PostprocessOptions,
    compute_threshold,
    make_mask,
    postprocess_mask,
    smooth_image,
)

class ThresholdControlsParticlesMixin:
    """Analyze particles integration with ImageJ-style measurement table."""

    def _run_analyze_particles(self) -> None:
        """Document the run_analyze_particles flow."""
        if self.particles_panel is None:
            return
        image_id = self.primary_image.id
        mask_entry = self.controller.session_state.threshold_masks.get(image_id)
        if mask_entry is None:
            self.particles_panel.status_label.setText("No threshold mask. Create one first.")
            return
        
        # Phase ζ: Get selected modality_idx from panel
        selected_modality_idx = self.particles_panel.get_selected_modality_idx()
        self._particles_modality_idx = selected_modality_idx
        
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
        self.controller.set_particles_config(self.primary_image.id, dict(values.__dict__))

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
            """Document the job flow."""
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
            """Document the on_result flow."""
            if result is None:
                return
            self._particles_results = list(result)
            self._populate_particles_table()
            self._particles_refresh_overlay()
            self.particles_panel.status_label.setText(f"Found {len(result)} particles.")
            self._append_log(self._particles_log_message(result, opts))
            self.recorder.record("analyze_particles", values.__dict__)

        def _on_error(err: str) -> None:
            """Document the on_error flow."""
            self.particles_panel.status_label.setText("Analyze failed.")
            self._append_log(f"[Particles] Error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Analyze Particles",
            on_result=_on_result,
            on_error=_on_error,
            priority="interactive",
            replace_key="analyze-particles",
        )
        self._particles_job_id = handle.job_id
        self.particles_panel.status_label.setText("Running…")

    def _populate_particles_table(self) -> None:
        """Document the populate_particles_table flow."""
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
        """Document the particles_selection_changed flow."""
        if self.particles_panel is None:
            return
        rows = {idx.row() for idx in self.particles_panel.table.selectionModel().selectedRows()}
        self._particles_selected = next(iter(rows), None)
        self._particles_refresh_overlay()

    def _particles_refresh_overlay(self) -> None:
        """Document the particles_refresh_overlay flow."""
        self._particles_overlays = []
        if self.particles_panel is None:
            return
        show_outline = self.particles_panel.show_outlines_chk.isChecked()
        show_boxes = self.particles_panel.show_boxes_chk.isChecked()
        show_ellipse = self.particles_panel.show_ellipses_chk.isChecked()
        frame_ax = self.renderer.axes.get("frame") if getattr(self, "renderer", None) is not None else None
        scale = self._axis_scale(frame_ax) if frame_ax is not None else 1.0
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
        self._request_ui_refresh("threshold-controls")
