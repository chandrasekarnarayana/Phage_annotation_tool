"""Export and project save/load helpers."""

from __future__ import annotations

import pathlib
from typing import Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis import compute_mean_std
from phage_annotator.annotation_metadata import format_tokens
from phage_annotator.display_mapping import build_norm
from phage_annotator.export_view import ExportOptions, render_view_to_array
from phage_annotator.gui_image_io import read_metadata
from phage_annotator.lut_manager import cmap_for
from phage_annotator.scalebar import ScaleBarSpec


class ExportMixin:
    """Mixin for saving/loading annotations and projects."""

    def _save_csv(self) -> None:
        csv_path, _ = self._default_export_paths()
        self.controller.save_csv(self, csv_path)
        self._set_status(f"Saved CSV to {csv_path}")
        self._mark_dirty(False)

    def _quick_save_csv(self) -> None:
        """Quick-save annotations CSV to the default path."""
        csv_path, _ = self._default_export_paths()
        self.controller.save_csv(self, csv_path)
        self._set_status(f"Saved CSV to {csv_path}")
        self._mark_dirty(False)

    def _save_json(self) -> None:
        _, json_path = self._default_export_paths()
        self.controller.save_json(self, json_path)
        self._set_status(f"Saved JSON to {json_path}")
        self._mark_dirty(False)

    def _default_export_paths(self) -> Tuple[pathlib.Path, pathlib.Path]:
        first = self.primary_image.path
        csv_path = pathlib.Path(first).with_suffix(".annotations.csv")
        json_path = pathlib.Path(first).with_suffix(".annotations.json")
        if self._settings.value("encodeAnnotationMetaFilename", False, type=bool):
            meta = self.controller.build_annotation_metadata(self.primary_image.id)
            tokens = format_tokens(meta)
            if tokens:
                csv_path = csv_path.with_name(f"{csv_path.stem}{tokens}{csv_path.suffix}")
                json_path = json_path.with_name(f"{json_path.stem}{tokens}{json_path.suffix}")
        return csv_path, json_path

    def _save_project(self) -> None:
        """Save a .phageproj plus per-image annotations."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save project",
            str(pathlib.Path.cwd() / "session.phageproj"),
            "Phage project (*.phageproj)",
        )
        if not path:
            return
        settings = {
            "last_fov_index": self.current_image_idx,
            "last_support_index": self.support_image_idx,
            "smlm_runs": list(self._smlm_run_history),
            "threshold_settings": dict(self._threshold_settings),
            "threshold_configs_by_image": dict(
                self.controller.session_state.threshold_configs_by_image
            ),
            "particles_configs_by_image": dict(
                self.controller.session_state.particles_configs_by_image
            ),
            "density_config": (
                self.controller.density_config.__dict__ if self.controller.density_config else {}
            ),
            "density_infer_options": (
                self.controller.density_infer_options.__dict__
                if self.controller.density_infer_options
                else {}
            ),
            "density_model_path": self.controller.density_model_path,
            "density_device": self.controller.density_device,
            "density_target_panel": self._density_last_panel,
        }
        self.controller.save_project(
            self, pathlib.Path(path), settings, self.roi_manager.rois_by_image
        )
        self._set_status(f"Saved project to {path}")
        self._mark_dirty(False)

    def _load_project(self) -> None:
        """Load a .phageproj and restore image list, annotations, and settings."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load project", str(pathlib.Path.cwd()), "Phage project (*.phageproj)"
        )
        if not path:
            return
        self._cancel_all_jobs()
        self._bump_job_generation()
        if not self.controller.load_project(self, pathlib.Path(path), read_metadata):
            return
        self.stop_playback_t()
        self.fov_list.clear()
        self.primary_combo.clear()
        self.support_combo.clear()
        for img in self.images:
            self.fov_list.addItem(img.name)
            self.primary_combo.addItem(img.name)
            self.support_combo.addItem(img.name)
        self.current_image_idx = self.controller.session_state.active_primary_id
        self.support_image_idx = self.controller.session_state.active_support_id
        self.fov_list.setCurrentRow(self.current_image_idx)
        self.primary_combo.setCurrentIndex(self.current_image_idx)
        self.support_combo.setCurrentIndex(self.support_image_idx)
        self.speed_slider.setValue(int(self.controller.session_state.fps))
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        self.current_cmap_idx = mapping.lut
        if self.lut_combo is not None:
            idx = min(self.current_cmap_idx, self.lut_combo.count() - 1)
            self.lut_combo.setCurrentIndex(idx)
        if self.lut_invert_chk is not None:
            self.lut_invert_chk.setChecked(mapping.invert)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if self.controller.rois_by_image:
            self.roi_manager.rois_by_image = self.controller.rois_by_image
        self._smlm_run_history = list(self.controller.session_state.smlm_runs)
        self._last_smlm_run = self._smlm_run_history[-1] if self._smlm_run_history else None
        self._threshold_settings = dict(self.controller.session_state.threshold_settings)
        if self.threshold_panel is not None and self._threshold_settings:
            self._apply_threshold_settings(self._threshold_settings)
        if self.controller.session_state.threshold_configs_by_image:
            image_id = self.primary_image.id
            cfg = self.controller.session_state.threshold_configs_by_image.get(image_id)
            if cfg:
                self._apply_threshold_settings(cfg)
        if self.density_panel is not None:
            cfg = self.controller.density_config
            self.density_panel.normalize_combo.setCurrentText(cfg.normalize)
            self.density_panel.p_low_spin.setValue(cfg.p_low)
            self.density_panel.p_high_spin.setValue(cfg.p_high)
            self.density_panel.invert_chk.setChecked(cfg.invert)
            if self.controller.density_infer_options:
                opts = self.controller.density_infer_options
                self.density_panel.tile_spin.setValue(opts.tile_size)
                self.density_panel.overlap_spin.setValue(opts.overlap)
                self.density_panel.batch_spin.setValue(opts.batch_tiles)
                self.density_panel.roi_only_chk.setChecked(opts.use_roi_only)
            if self.controller.density_model_path:
                self.density_panel.model_path_edit.setText(self.controller.density_model_path)
            self.density_panel.device_combo.setCurrentText(self.controller.density_device)
            target = self.controller.density_target_panel
            if isinstance(target, str):
                self.density_panel.target_combo.setCurrentText(target.capitalize())
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._refresh_image()
        self._mark_dirty(False)
        self._check_recovery()

    def _export_view_dialog(self) -> None:
        if self.primary_image.array is None:
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Export View")
        layout = QtWidgets.QFormLayout(dlg)
        panel_combo = QtWidgets.QComboBox()
        panel_combo.addItems(["Frame", "Mean", "Composite", "Support", "Std"])
        scope_combo = QtWidgets.QComboBox()
        scope_combo.addItems(["Current slice", "T range", "All frames"])
        t_start = QtWidgets.QSpinBox()
        t_end = QtWidgets.QSpinBox()
        t_start.setRange(0, max(0, self.primary_image.array.shape[0] - 1))
        t_end.setRange(0, max(0, self.primary_image.array.shape[0] - 1))
        t_start.setValue(self.t_slider.value())
        t_end.setValue(self.t_slider.value())
        region_combo = QtWidgets.QComboBox()
        region_combo.addItems(["Full view", "Crop", "ROI bounds", "ROI mask-clipped"])
        roi_outline_chk = QtWidgets.QCheckBox("ROI outline")
        roi_outline_chk.setChecked(bool(self.roi_rect))
        roi_fill_chk = QtWidgets.QCheckBox("ROI fill")
        ann_chk = QtWidgets.QCheckBox("Annotation points")
        ann_chk.setChecked(True)
        ann_label_chk = QtWidgets.QCheckBox("Annotation labels")
        particle_chk = QtWidgets.QCheckBox("Particle outlines")
        scalebar_chk = QtWidgets.QCheckBox("Scale bar")
        scalebar_chk.setChecked(self.scale_bar_enabled and self.scale_bar_include_in_export)
        overlay_text_chk = QtWidgets.QCheckBox("Overlay text")
        marker_spin = QtWidgets.QDoubleSpinBox()
        marker_spin.setRange(1.0, 200.0)
        marker_spin.setValue(float(self.marker_size))
        roi_lw_spin = QtWidgets.QDoubleSpinBox()
        roi_lw_spin.setRange(0.5, 6.0)
        roi_lw_spin.setValue(1.5)
        dpi_spin = QtWidgets.QSpinBox()
        dpi_spin.setRange(72, 600)
        dpi_spin.setValue(150)
        fmt_combo = QtWidgets.QComboBox()
        fmt_combo.addItems(["PNG", "TIFF"])
        overlay_only_chk = QtWidgets.QCheckBox("Overlay only (transparent)")
        transparent_chk = QtWidgets.QCheckBox("Transparent background")
        transparent_chk.setChecked(True)

        layout.addRow("Panel", panel_combo)
        layout.addRow("Scope", scope_combo)
        range_row = QtWidgets.QHBoxLayout()
        range_row.addWidget(QtWidgets.QLabel("Start"))
        range_row.addWidget(t_start)
        range_row.addWidget(QtWidgets.QLabel("End"))
        range_row.addWidget(t_end)
        layout.addRow("T range", range_row)
        layout.addRow("Region", region_combo)
        layout.addRow(roi_outline_chk)
        layout.addRow(roi_fill_chk)
        layout.addRow(ann_chk)
        layout.addRow(ann_label_chk)
        layout.addRow(particle_chk)
        layout.addRow(scalebar_chk)
        layout.addRow(overlay_text_chk)
        layout.addRow("Marker size", marker_spin)
        layout.addRow("ROI line width", roi_lw_spin)
        layout.addRow("DPI", dpi_spin)
        layout.addRow("Format", fmt_combo)
        layout.addRow(overlay_only_chk)
        layout.addRow(transparent_chk)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        fmt = fmt_combo.currentText().lower()
        default_name = pathlib.Path(self.primary_image.path).with_suffix(f".export.{fmt}")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export View", str(default_name))
        if not path:
            return
        opts = ExportOptions(
            panel=panel_combo.currentText().lower(),
            region=region_combo.currentText().lower(),
            include_roi_outline=roi_outline_chk.isChecked(),
            include_roi_fill=roi_fill_chk.isChecked(),
            include_annotations=ann_chk.isChecked(),
            include_annotation_labels=ann_label_chk.isChecked(),
            include_particles=particle_chk.isChecked(),
            include_scalebar=scalebar_chk.isChecked(),
            include_overlay_text=overlay_text_chk.isChecked(),
            marker_size=float(marker_spin.value()),
            roi_line_width=float(roi_lw_spin.value()),
            dpi=int(dpi_spin.value()),
            fmt=fmt,
            overlay_only=overlay_only_chk.isChecked(),
            transparent_bg=transparent_chk.isChecked(),
            roi_mask_clip=region_combo.currentText().lower() == "roi mask-clipped",
        )
        scope = scope_combo.currentText()
        t_values = self._export_t_values(scope, t_start.value(), t_end.value())
        self._export_view_job(pathlib.Path(path), t_values, opts)

    def _export_t_values(self, scope: str, t_start: int, t_end: int) -> list[int]:
        if scope == "Current slice":
            return [self.t_slider.value()]
        if scope == "All frames":
            return list(range(self.primary_image.array.shape[0]))
        if t_end < t_start:
            t_start, t_end = t_end, t_start
        return list(range(t_start, t_end + 1))

    def _export_view_job(
        self, base_path: pathlib.Path, t_values: list[int], opts: ExportOptions
    ) -> None:
        prim = self.primary_image
        if prim.array is None:
            return
        support = self.support_image if self.support_image.array is not None else None
        z_idx = self.z_slider.value()
        cal = self._get_calibration_state(prim.id)
        scalebar_spec = ScaleBarSpec(
            enabled=opts.include_scalebar,
            length_um=self.scale_bar_length_um,
            thickness_px=self.scale_bar_thickness_px,
            location=self.scale_bar_location,
            padding_px=self.scale_bar_padding_px,
            show_text=self.scale_bar_show_text,
            text_offset_px=self.scale_bar_text_offset_px,
            background_box=self.scale_bar_background_box,
        )
        crop_rect = (
            self.crop_rect if opts.region in ("crop", "roi bounds", "roi mask-clipped") else None
        )
        roi_rect = self.roi_rect if opts.region in ("roi bounds", "roi mask-clipped") else None
        roi_shape = self.roi_shape

        def _job(progress, cancel_token):
            total = len(t_values)
            for idx, t_idx in enumerate(t_values):
                if cancel_token.is_cancelled():
                    return None
                frame = self._export_panel_frame(prim, support, t_idx, z_idx, opts.panel, crop_rect)
                if frame is None:
                    continue
                frame, offset = self._apply_roi_region(
                    frame, roi_rect, roi_shape, opts.region, crop_rect
                )
                annotations = self._export_annotations(t_idx, offset, opts)
                annotation_labels = self._export_annotation_labels(annotations, opts)
                annotation_points = [(x, y, color) for x, y, color, _ in annotations]
                roi_overlays = self._export_roi_overlays(offset, opts)
                particle_overlays = (
                    self._particles_overlays
                    if opts.include_particles and t_idx == self.t_slider.value()
                    else []
                )
                overlay_text = self._build_overlay_text() if opts.include_overlay_text else None
                mapping = self._get_display_mapping(prim.id, opts.panel, frame)
                norm = build_norm(mapping)
                cmap = cmap_for(mapping.lut, mapping.invert)
                image = render_view_to_array(
                    frame,
                    cmap=cmap,
                    norm=norm,
                    overlays=[],
                    annotations=annotation_points,
                    annotation_labels=annotation_labels,
                    roi_overlays=roi_overlays,
                    particle_overlays=particle_overlays,
                    overlay_text=overlay_text,
                    scalebar_spec=scalebar_spec if opts.include_scalebar else None,
                    pixel_size_um=cal.pixel_size_um_per_px,
                    options=opts,
                )
                image = self._apply_roi_mask_clip(image, frame, roi_rect, roi_shape, opts, offset)
                out_path = self._export_frame_path(
                    base_path, t_idx, opts, multiple=len(t_values) > 1
                )
                _save_image(out_path, image, opts)
                progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
            return True

        self.jobs.submit(_job, name="Export view")

    def _export_panel_frame(self, prim, support, t_idx: int, z_idx: int, panel: str, crop_rect):
        if prim.array is None:
            return None
        if panel == "support":
            if support is None or support.array is None:
                return None
            data = support.array[t_idx, z_idx, :, :]
        elif panel == "mean":
            data, _ = compute_mean_std(prim.array)
        elif panel == "std":
            _, data = compute_mean_std(prim.array)
        elif panel == "composite":
            data, _ = compute_mean_std(prim.array)
        else:
            data = prim.array[t_idx, z_idx, :, :]
        return self._apply_crop_rect(data, crop_rect, data.shape)

    def _apply_roi_region(
        self, frame: np.ndarray, roi_rect, roi_shape: str, region: str, crop_rect
    ):
        offset = (crop_rect[0], crop_rect[1]) if crop_rect else (0.0, 0.0)
        if roi_rect is None:
            return frame, offset
        if region not in ("roi bounds", "roi mask-clipped"):
            return frame, offset
        x, y, w, h = roi_rect
        x0 = int(max(0, x - offset[0]))
        y0 = int(max(0, y - offset[1]))
        x1 = int(min(frame.shape[1], x0 + w))
        y1 = int(min(frame.shape[0], y0 + h))
        return frame[y0:y1, x0:x1], (offset[0] + x0, offset[1] + y0)

    def _export_annotations(self, t_idx: int, offset, opts: ExportOptions):
        if not opts.include_annotations:
            return []
        points = []
        for kp in self._current_keypoints():
            if kp.t not in (-1, t_idx) or kp.z not in (-1, self.z_slider.value()):
                continue
            x = kp.x - offset[0]
            y = kp.y - offset[1]
            points.append((x, y, self._label_color(kp.label, faded=False), kp.label))
        return points

    def _export_annotation_labels(self, annotations, opts: ExportOptions):
        if not opts.include_annotation_labels:
            return []
        return [(x, y, label) for x, y, _, label in annotations]

    def _export_roi_overlays(self, offset, opts: ExportOptions):
        overlays = []
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        if roi_active and (opts.include_roi_outline or opts.include_roi_fill):
            x, y, w, h = self.roi_rect
            rect = (x - offset[0], y - offset[1], w, h)
            if self.roi_shape == "circle":
                overlays.append(("circle", rect, "#00c0ff"))
            else:
                overlays.append(("box", rect, "#00c0ff"))
        return overlays

    def _apply_roi_mask_clip(
        self,
        image: np.ndarray,
        frame: np.ndarray,
        roi_rect,
        roi_shape: str,
        opts: ExportOptions,
        offset,
    ):
        if not opts.roi_mask_clip or roi_rect is None:
            return image
        mask = np.ones(frame.shape, dtype=bool)
        rx, ry, rw, rh = roi_rect
        rx -= offset[0]
        ry -= offset[1]
        rx = max(0, rx)
        ry = max(0, ry)
        if roi_shape == "circle":
            cx, cy = rx + rw / 2, ry + rh / 2
            r = min(rw, rh) / 2
            yy, xx = np.ogrid[: frame.shape[0], : frame.shape[1]]
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
        else:
            x0 = int(max(0, rx))
            y0 = int(max(0, ry))
            x1 = int(min(frame.shape[1], rx + rw))
            y1 = int(min(frame.shape[0], ry + rh))
            mask = np.zeros(frame.shape, dtype=bool)
            mask[y0:y1, x0:x1] = True
        if image.shape[-1] == 4:
            if opts.transparent_bg:
                image[..., 3] = np.where(mask, image[..., 3], 0)
            else:
                image[~mask] = 0
        return image

    def _export_frame_path(
        self, base: pathlib.Path, t_idx: int, opts: ExportOptions, *, multiple: bool
    ) -> pathlib.Path:
        if not multiple:
            return base
        stem = base.stem
        return base.with_name(f"{stem}_t{t_idx:04d}{base.suffix}")


def _save_image(path: pathlib.Path, image: np.ndarray, opts: ExportOptions) -> None:
    if opts.fmt == "tiff":
        import tifffile as tif

        tif.imwrite(str(path), image)
        return
    import matplotlib.pyplot as plt

    plt.imsave(str(path), image)
