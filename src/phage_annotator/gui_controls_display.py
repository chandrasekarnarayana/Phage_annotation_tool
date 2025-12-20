"""Display, playback, and general control handlers."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtGui, QtWidgets

from phage_annotator.analysis import compute_auto_window
from phage_annotator.lut_manager import LUTS, lut_names


class DisplayControlsMixin:
    """Mixin for display, playback, and general control handlers."""

    def _bc_value_from_slider(self, value: int) -> float:
        scale = float(getattr(self, "_bc_slider_scale", 1.0))
        if scale <= 0:
            return float(value)
        return float(value) / scale

    def _bc_slider_from_value(self, value: float) -> int:
        scale = float(getattr(self, "_bc_slider_scale", 1.0))
        return int(round(float(value) * scale))

    def _bc_set_controls(self, min_val: float, max_val: float) -> None:
        if getattr(self, "bc_min_spin", None) is None:
            return
        self._bc_updating_controls = True
        try:
            self.bc_min_spin.blockSignals(True)
            self.bc_max_spin.blockSignals(True)
            self.bc_min_slider.blockSignals(True)
            self.bc_max_slider.blockSignals(True)
            self.bc_min_spin.setValue(float(min_val))
            self.bc_max_spin.setValue(float(max_val))
            min_slider = self._bc_slider_from_value(min_val)
            max_slider = self._bc_slider_from_value(max_val)
            self.bc_min_slider.setValue(min_slider)
            self.bc_max_slider.setValue(max_slider)
        finally:
            self.bc_min_spin.blockSignals(False)
            self.bc_max_spin.blockSignals(False)
            self.bc_min_slider.blockSignals(False)
            self.bc_max_slider.blockSignals(False)
            self._bc_updating_controls = False

    def _bc_apply_minmax(self, min_val: float, max_val: float) -> None:
        prim = self.primary_image
        if prim.array is None:
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        step = float(getattr(self, "_bc_step", 1.0))
        if data_min is None or data_max is None:
            data_min = float(np.min(prim.array))
            data_max = float(np.max(prim.array))
        data_range = float(data_max - data_min)
        if data_range <= 0:
            return
        width = max(float(max_val - min_val), step)
        width = min(width, data_range)
        center = 0.5 * (min_val + max_val)
        min_val = center - width / 2.0
        max_val = center + width / 2.0
        if min_val < data_min:
            shift = data_min - min_val
            min_val += shift
            max_val += shift
        if max_val > data_max:
            shift = data_max - max_val
            min_val += shift
            max_val += shift
        if max_val - min_val < step:
            max_val = min_val + step
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        mapping.set_window(min_val, max_val)
        if self.vmin_label is not None:
            self.vmin_label.setText(f"vmin: {min_val:.3f}")
        if self.vmax_label is not None:
            self.vmax_label.setText(f"vmax: {max_val:.3f}")
        self._bc_set_controls(min_val, max_val)
        self._refresh_image()

    def _update_bc_controls(self, vals: np.ndarray, vmin: float, vmax: float) -> None:
        if getattr(self, "bc_min_spin", None) is None or vals is None or vals.size == 0:
            return
        data_min = float(np.min(vals))
        data_max = float(np.max(vals))
        if data_min == data_max:
            data_max = data_min + 1.0
        is_int = np.issubdtype(vals.dtype, np.integer)
        step = 1.0 if is_int else max((data_max - data_min) / 1000.0, 0.001)
        decimals = 0 if is_int else 3
        scale = max(1, int(round(1.0 / step)))
        span = data_max - data_min
        if span * scale > 2_000_000_000:
            scale = max(1, int(2_000_000_000 / max(span, 1e-9)))
        min_slider = int(round(data_min * scale))
        max_slider = int(round(data_max * scale))
        if min_slider == max_slider:
            max_slider = min_slider + 1
        self._bc_slider_scale = float(scale)
        self._bc_step = float(step)
        self._bc_data_min = data_min
        self._bc_data_max = data_max
        self._bc_updating_controls = True
        try:
            for spin in (self.bc_min_spin, self.bc_max_spin):
                spin.blockSignals(True)
                spin.setDecimals(decimals)
                spin.setSingleStep(step)
                spin.setRange(data_min, data_max)
            for slider in (self.bc_min_slider, self.bc_max_slider):
                slider.blockSignals(True)
                slider.setRange(min_slider, max_slider)
                slider.setSingleStep(1)
                slider.setPageStep(max(1, int(10 * scale)))
            data_mid = 0.5 * (data_min + data_max)
            min_val = float(vmin)
            max_val = float(vmax)
            center = 0.5 * (min_val + max_val)
            width = max(max_val - min_val, step)
            b_range = max(1, int(round((data_max - data_min) / step)))
            self.bc_brightness_slider.setRange(-b_range, b_range)
            brightness_val = int(round((center - data_mid) / step))
            self.bc_brightness_slider.setValue(
                max(-b_range, min(b_range, brightness_val))
            )
            c_min = -90
            c_max = 300
            self.bc_contrast_slider.setRange(c_min, c_max)
            contrast_val = int(round((data_max - data_min) / width - 1.0) * 100)
            contrast_val = max(c_min, min(c_max, contrast_val))
            self.bc_contrast_slider.setValue(contrast_val)
            self.bc_min_spin.setValue(float(vmin))
            self.bc_max_spin.setValue(float(vmax))
            self.bc_min_slider.setValue(self._bc_slider_from_value(vmin))
            self.bc_max_slider.setValue(self._bc_slider_from_value(vmax))
        finally:
            for spin in (self.bc_min_spin, self.bc_max_spin):
                spin.blockSignals(False)
            for slider in (self.bc_min_slider, self.bc_max_slider):
                slider.blockSignals(False)
            self._bc_updating_controls = False
        self._bc_update_preview(vmin, vmax)

    def _on_bc_min_slider(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = self._bc_value_from_slider(value)
        max_val = float(self.bc_max_spin.value())
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_max_slider(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = float(self.bc_min_spin.value())
        max_val = self._bc_value_from_slider(value)
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_min_spin(self, value: float) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = float(value)
        max_val = float(self.bc_max_spin.value())
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_max_spin(self, value: float) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        min_val = float(self.bc_min_spin.value())
        max_val = float(value)
        self._bc_apply_minmax(min_val, max_val)

    def _on_bc_brightness_change(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        step = float(getattr(self, "_bc_step", 1.0))
        data_mid = 0.5 * (data_min + data_max)
        L = data_mid + value * step
        min_val, max_val = self._current_vmin_vmax()
        W = max_val - min_val
        self._bc_apply_minmax(L - W / 2.0, L + W / 2.0)

    def _on_bc_contrast_change(self, value: int) -> None:
        if getattr(self, "_bc_updating_controls", False):
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        data_range = max(float(data_max - data_min), float(getattr(self, "_bc_step", 1.0)))
        min_val, max_val = self._current_vmin_vmax()
        center = 0.5 * (min_val + max_val)
        denom = max(0.01, 1.0 + (value / 100.0))
        W = data_range / denom
        W = max(W, float(getattr(self, "_bc_step", 1.0)))
        self._bc_apply_minmax(center - W / 2.0, center + W / 2.0)

    def _bc_set_from_inputs(self) -> None:
        if getattr(self, "bc_min_spin", None) is None:
            return
        min_val = float(self.bc_min_spin.value())
        max_val = float(self.bc_max_spin.value())
        self._bc_apply_minmax(min_val, max_val)

    def _bc_update_preview(self, min_val: float, max_val: float) -> None:
        label = getattr(self, "bc_preview", None)
        if label is None:
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        width = max(1, label.width())
        height = max(1, label.height())
        pm = QtGui.QPixmap(width, height)
        pm.fill(QtGui.QColor("#ffffff"))
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = QtGui.QRect(4, 4, width - 8, height - 8)
        painter.setPen(QtGui.QPen(QtGui.QColor("#111111"), 1))
        painter.drawRect(rect)
        if data_max == data_min:
            painter.end()
            label.setPixmap(pm)
            return
        def _x(val: float) -> int:
            return int(rect.left() + (val - data_min) / (data_max - data_min) * rect.width())
        x1 = _x(min_val)
        x2 = _x(max_val)
        y0 = rect.bottom()
        y1 = rect.top()
        painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 2))
        painter.drawLine(rect.left(), y0, x1, y0)
        painter.drawLine(x1, y0, x2, y1)
        painter.drawLine(x2, y1, rect.right(), y1)
        painter.end()
        label.setPixmap(pm)

    def _set_fov(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.images):
            return
        self.stop_playback_t()
        # Clear all analysis overlays when changing images to prevent stale results
        self._smlm_overlay = None
        self._smlm_overlay_extent = None
        self._smlm_results = []
        self._smlm_image_id = None  # Track that results are cleared
        self._deepstorm_overlay = None
        self._deepstorm_overlay_extent = None
        self._deepstorm_results = []
        self._deepstorm_image_id = None  # Track that results are cleared
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._particles_results = []
        self._particles_overlays = []
        self._particles_selected = None
        self._binary_view_mask = None
        self._binary_view_enabled = False
        if self.threshold_panel is not None:
            cfg = self.controller.session_state.threshold_configs_by_image.get(idx)
            if cfg:
                self._apply_threshold_settings(cfg)
                self.current_image_idx = idx
                self.primary_combo.setCurrentIndex(idx)
                self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
                self._refresh_roi_manager()
                self._refresh_metadata_dock(self.primary_image.id)
                self._maybe_autoload_annotations(self.primary_image.id)
                self._refresh_image()

    def _set_primary_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self._smlm_overlay = None
            self._smlm_overlay_extent = None
            self._smlm_results = []
            self._deepstorm_overlay = None
            self._deepstorm_overlay_extent = None
            self._deepstorm_results = []
            self._sr_overlay = None
            self._sr_overlay_extent = None
            self._particles_results = []
            self._particles_overlays = []
            self._particles_selected = None
            self._binary_view_mask = None
            self._binary_view_enabled = False
            if self.threshold_panel is not None:
                cfg = self.controller.session_state.threshold_configs_by_image.get(idx)
                if cfg:
                    self._apply_threshold_settings(cfg)
                    self.current_image_idx = idx
                    self.fov_list.setCurrentRow(idx)
                    self.axis_mode_combo.setCurrentText(
                        self.primary_image.interpret_3d_as
                    )
                    self._refresh_roi_manager()
                    self._refresh_metadata_dock(self.primary_image.id)
                    self._maybe_autoload_annotations(self.primary_image.id)
                    self._refresh_image()

    def _set_support_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self.support_image_idx = idx
            self.support_combo.setCurrentIndex(idx)
            self._maybe_autoload_annotations(self.support_image.id)
            self._refresh_image()

    def _toggle_play(self, axis: str) -> None:
        if self.play_mode == axis:
            self.stop_playback_t()
            return
        self.start_playback_t()

    def _on_play_tick(self) -> None:
        if self._playback_mode:
            return
        self._refresh_image()

    def _on_loop_change(self) -> None:
        self.loop_playback = self.loop_chk.isChecked()

    def _on_speed_change(self, value: int) -> None:
        if getattr(self, "fps_label", None) is not None:
            self.fps_label.setText(f"FPS: {value}")

    def _on_axis_mode_change(self, mode: str) -> None:
        self.stop_playback_t()
        self.controller.set_axis_interpretation(self.primary_image.id, mode)
        # Force reload for current primary to honor new interpretation.
        self._evict_image_cache(self.primary_image)
        self.proj_cache.invalidate_image(self.primary_image.id)
        self.recorder.record(
            "set_axis_interpretation", {"image": self.primary_image.name, "mode": mode}
        )
        self._refresh_image()

    def _on_vminmax_change(self) -> None:
        if self.vmin_slider.value() > self.vmax_slider.value():
            self.vmax_slider.setValue(self.vmin_slider.value())
            prim = self.primary_image
            if prim.array is not None:
                data = prim.array
                if self._interactive:
                    stride = max(1, self.downsample_factor)
                    data = data[::stride, ::stride, ::stride, ::stride]
                    vmin = float(np.percentile(data, self.vmin_slider.value()))
                    vmax = float(np.percentile(data, self.vmax_slider.value()))
                    mapping = self._get_display_mapping(prim.id, "frame", prim.array)
                    mapping.set_window(vmin, vmax)
                    if self._interactive:
                        self._contrast_drag_active = True
                        self.recorder.record(
                            "set_minmax",
                            {
                                "vmin": f"{self._last_vmin:.4f}",
                                "vmax": f"{self._last_vmax:.4f}",
                            },
                        )
                        self._schedule_refresh()

    def _apply_display_mapping(self) -> None:
        """Destructively apply the current display mapping to pixel data."""
        prim = self.primary_image
        if prim.array is None:
            return
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        # P1.4: Confirmation with "Don't show again" toggle stored in settings
        if self._settings.value("confirmApplyDisplayMapping", True, type=bool):
            mbox = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Warning,
                "Apply display mapping",
                (
                    "This will permanently rescale pixel values for the current image.\n"
                    "This cannot be undone. Proceed?"
                ),
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
                self._settings.setValue("confirmApplyDisplayMapping", False)
        data = prim.array.astype(np.float32, copy=True)
        if mapping.max_val == mapping.min_val:
            return
        data = (data - mapping.min_val) / (mapping.max_val - mapping.min_val)
        data = np.clip(data, 0.0, 1.0)
        prim.array = data
        mapping.reset_to_full_range(float(data.min()), float(data.max()))
        self._refresh_image()

    def _current_vmin_vmax(self) -> Tuple[float, float]:
        prim = self.primary_image
        if prim.array is None:
            return 0.0, 1.0
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        vmin, vmax = mapping.min_val, mapping.max_val
        if vmin > vmax:
            vmin, vmax = vmax, vmin
            mapping.set_window(vmin, vmax)
            self.vmin_label.setText(f"vmin: {vmin:.3f}")
            self.vmax_label.setText(f"vmax: {vmax:.3f}")
        # PHASE 2D FIX: Always return vmin, vmax (was missing return statement)
        return vmin, vmax

    def _on_lut_change(self, idx: int) -> None:
        if idx < 0:
            return
        self.current_cmap_idx = idx
        self.recorder.record(
            "set_lut",
            {"index": idx, "name": lut_names()[idx] if idx < len(lut_names()) else idx},
        )
        if self.lut_invert_chk is not None:
            invert_supported = True
            if 0 <= idx < len(LUTS):
                invert_supported = LUTS[idx].invert_supported
                self.lut_invert_chk.setEnabled(invert_supported)
                if not invert_supported:
                    self.lut_invert_chk.setChecked(False)
                    self._refresh_image()

    def _on_lut_invert(self) -> None:
        self.controller.set_invert(self.lut_invert_chk.isChecked())
        self.recorder.record(
            "set_lut_invert", {"invert": self.lut_invert_chk.isChecked()}
        )
        self._refresh_image()

    def _on_gamma_change(self, value: int) -> None:
        gamma = max(0.2, min(5.0, value / 10.0))
        mapping = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        mapping.gamma = gamma
        if self.gamma_label is not None:
            self.gamma_label.setText(f"{gamma:.2f}")
            self.recorder.record("set_gamma", {"gamma": f"{gamma:.2f}"})
            self.controller.display_changed.emit()
            self._refresh_image()

    def _on_log_toggle(self) -> None:
        mapping = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        mapping.mode = "log" if self.log_chk.isChecked() else "linear"
        self.recorder.record("set_log", {"enabled": self.log_chk.isChecked()})
        self.controller.display_changed.emit()
        self._refresh_image()

    def _copy_display_settings(self) -> None:
        """Copy LUT/min/max/gamma from primary to another target."""
        mapping = self.controller.display_mapping.mapping_for(
            self.primary_image.id, "frame"
        )
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Copy Display Settings")
        layout = QtWidgets.QFormLayout(dlg)
        target_combo = QtWidgets.QComboBox()
        target_combo.addItems(["Support image", "All images"])
        layout.addRow("Target", target_combo)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            choice = target_combo.currentText()
            if choice == "Support image":
                self._apply_display_to_image(self.support_image.id, "support", mapping)
            else:
                for img in self.images:
                    self._apply_display_to_image(img.id, "frame", mapping)
            self._refresh_image()
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def _apply_display_to_image(self, image_id: int, panel: str, mapping) -> None:
        copy = mapping.clone()
        copy.lut = mapping.lut
        copy.gamma = mapping.gamma
        copy.min_val = mapping.min_val
        copy.max_val = mapping.max_val
        copy.mode = mapping.mode
        copy.invert = mapping.invert
        self.controller.set_display_for_image(image_id, panel, copy)

    def _on_label_change(self, button, checked: bool) -> None:
        if checked:
            self.current_label = button.text()
            self._update_status()

    def _on_scope_change(self) -> None:
        self.annotation_scope = (
            "current" if self.scope_group.buttons()[0].isChecked() else "all"
        )

    def _on_target_change(self) -> None:
        buttons = self.target_group.buttons()
        if buttons[0].isChecked():
            self.annotate_target = "frame"
        elif buttons[1].isChecked():
            self.annotate_target = "mean"
        elif buttons[2].isChecked():
            self.annotate_target = "comp"
        else:
            self.annotate_target = "support"

    def _on_marker_size_change(self, val: int) -> None:
        self.marker_size = float(val)
        self._settings.setValue("markerSize", int(val))
        self._refresh_image()

    def _on_click_radius_change(self, val: float) -> None:
        self.click_radius_px = float(val)
        self._settings.setValue("clickRadiusPx", float(val))

    def _on_profile_mode(self) -> None:
        self.profile_enabled = self.profile_mode_chk.isChecked()

    def _on_profile_chk_changed(self) -> None:
        self.profile_enabled = self.profile_chk.isChecked()
        self._refresh_image()

    def _on_hist_chk_changed(self) -> None:
        self.hist_enabled = self.hist_chk.isChecked()
        self._refresh_image()

    def _clear_profile(self) -> None:
        self.profile_line = None
        self._refresh_image()

    def _on_hist_region(self) -> None:
        text = self.hist_region_combo.currentText()
        if text == "ROI":
            self.hist_region = "roi"
        elif text == "Crop area":
            self.hist_region = "crop"
        else:
            self.hist_region = "full"
        self._refresh_image()

    def _on_hist_scope_change(self) -> None:
        self._hist_scope_mode = self.hist_scope_combo.currentText()
        self._hist_cache = None
        self._hist_cache_key = None
        if self._hist_job_id is not None:
            self.jobs.cancel(self._hist_job_id)
            self._hist_job_id = None
            self._refresh_image()

    def _on_contrast_slider_pressed(self) -> None:
        self._contrast_drag_active = True
        self._start_interaction()

    def _on_contrast_slider_released(self) -> None:
        self._end_interaction()
        if not self._contrast_drag_active:
            return
        self._contrast_drag_active = False
        prim = self.primary_image
        if prim.array is None:
            return
        vmin = float(np.percentile(prim.array, self.vmin_slider.value()))
        vmax = float(np.percentile(prim.array, self.vmax_slider.value()))
        mapping = self._get_display_mapping(prim.id, "frame", prim.array)
        mapping.set_window(vmin, vmax)
        self._refresh_image()

    def _auto_set_dialog(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Set Auto Contrast")
        layout = QtWidgets.QFormLayout(dlg)
        low_spin = QtWidgets.QDoubleSpinBox()
        high_spin = QtWidgets.QDoubleSpinBox()
        low_spin.setRange(0.0, 100.0)
        high_spin.setRange(0.0, 100.0)
        low_spin.setDecimals(2)
        high_spin.setDecimals(2)
        low_spin.setValue(float(self._settings.value("autoLowPct", 0.35)))
        high_spin.setValue(float(self._settings.value("autoHighPct", 99.65)))
        layout.addRow("Low percentile (%)", low_spin)
        layout.addRow("High percentile (%)", high_spin)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            low = float(low_spin.value())
            high = float(high_spin.value())
            if high <= low:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid range", "High percentile must be greater than low."
                )
                return
            self._settings.setValue("autoLowPct", low)
            self._settings.setValue("autoHighPct", high)
            if self.auto_pct_label is not None:
                self.auto_pct_label.setText(f"{low:.2f}% / {high:.2f}%")
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def _auto_contrast(self) -> None:
        """Run Fiji-like auto contrast with a quick preview and background job."""
        prim = self.primary_image
        if prim.array is None:
            return
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        use_roi = self.auto_roi_chk.isChecked()
        scope = self.auto_scope_combo.currentText()
        target = self.auto_target_combo.currentText()

        def _current_panel_id() -> str:
            if self.annotate_target == "comp":
                return "composite"
            return self.annotate_target

        if target == "Current panel":
            panel_ids = [_current_panel_id()]
        else:
            panel_ids = [
                panel for panel, visible in self._panel_visibility.items() if visible
            ]

        if not panel_ids:
            return

        auto_img = self.support_image if panel_ids == ["support"] else prim
        if auto_img.array is None:
            self._ensure_loaded(auto_img.id)
            if auto_img.array is None:
                return

        # Quick preview on current slice (downsampled).
        slice_data = self._slice_data(auto_img)
        roi_mask = self._roi_mask(slice_data.shape) if use_roi else None
        stride = max(1, self.downsample_factor)
        quick = slice_data[::stride, ::stride]
        quick_mask = roi_mask[::stride, ::stride] if roi_mask is not None else None
        vmin, vmax = compute_auto_window(quick, low_pct, high_pct, roi_mask=quick_mask)
        self._apply_auto_to_panels(panel_ids, vmin, vmax)
        self._refresh_image()

        if self._auto_job_id is not None:
            self.jobs.cancel(self._auto_job_id)
            self._auto_job_id = None

        self._bump_job_generation()
        job_gen = self._job_generation

        def _sample_stack() -> np.ndarray:
            arr = auto_img.array
            if arr is None:
                return np.array([], dtype=np.float32)
            t_count, z_count = arr.shape[0], arr.shape[1]
            samples = []
            roi_mask_local = None
            if scope == "All frames":
                t_step = max(1, t_count // 16)
                z_idx = self.z_slider.value()
                for t in range(0, t_count, t_step):
                    frame = arr[t, z_idx, :, :]
                    if use_roi:
                        if roi_mask_local is None:
                            roi_mask_local = self._roi_mask(frame.shape)
                        samples.append(frame[roi_mask_local])
                    else:
                        samples.append(frame.ravel())
            elif scope == "Whole image":
                t_step = max(1, t_count // 8)
                z_step = max(1, z_count // 8)
                for t in range(0, t_count, t_step):
                    for z in range(0, z_count, z_step):
                        frame = arr[t, z, :, :]
                        if use_roi:
                            if roi_mask_local is None:
                                roi_mask_local = self._roi_mask(frame.shape)
                            samples.append(frame[roi_mask_local])
                        else:
                            samples.append(frame.ravel())
            else:
                t = self.t_slider.value()
                z = self.z_slider.value()
                frame = arr[t, z, :, :]
                if use_roi:
                    roi_mask_local = self._roi_mask(frame.shape)
                    samples.append(frame[roi_mask_local])
                else:
                    samples.append(frame.ravel())
            if not samples:
                return np.array([], dtype=np.float32)
            sample = np.concatenate(samples)
            if sample.size > 200000:
                # Deterministic sampling for reproducibility (P3.2)
                rng = np.random.default_rng(42)
                idx = rng.choice(sample.size, size=200000, replace=False)
                sample = sample[idx]
            return sample

        def _job(progress, cancel_token):
            if cancel_token.is_cancelled():
                return None
            vmin_full, vmax_full = compute_auto_window(_sample_stack, low_pct, high_pct)
            if cancel_token.is_cancelled():
                return None
            return vmin_full, vmax_full, job_gen

        def _on_result(result) -> None:
            if result is None:
                return
            vmin_full, vmax_full, gen = result
            if gen != self._job_generation:
                return
            self._apply_auto_to_panels(panel_ids, vmin_full, vmax_full)
            self._refresh_image()

        def _on_error(err: str) -> None:
            self._append_log(f"[JOB] Auto contrast error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Auto contrast",
            on_result=_on_result,
            on_error=_on_error,
        )
        self._auto_job_id = handle.job_id

    def _apply_auto_to_panels(
        self, panel_ids: List[str], vmin: float, vmax: float
    ) -> None:
        for panel in panel_ids:
            image_id = (
                self.support_image.id if panel == "support" else self.primary_image.id
            )
            data = (
                self.support_image.array
                if panel == "support"
                else self.primary_image.array
            )
            mapping = self._get_display_mapping(image_id, panel, data)
            mapping.set_window(vmin, vmax)

    def _mark_dirty(self, dirty: bool = True) -> None:
        self._annotations_dirty = dirty

    def _autosave_tick(self) -> None:
        path = self.controller.autosave_if_needed(self, self._current_keypoints)
        if path is None:
            return
        self._append_log(f"[RECOVERY] Autosaved annotations to {path}")
        self._set_status("Autosaved recovery file.")

    def _check_recovery(self) -> None:
        recovery = self.controller.find_recovery_file(self._current_keypoints)
        if recovery is None:
            return
        resp = QtWidgets.QMessageBox.question(
            self,
            "Recovery found",
            "A newer recovery file was found. Restore annotations?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if resp == QtWidgets.QMessageBox.StandardButton.Yes:
            self.controller.restore_recovery(recovery)
            self._refresh_image()

    def _focus_axis_mode_control(self) -> None:
        if getattr(self, "advanced_group", None) is not None:
            self.advanced_group.setChecked(True)
            self.axis_mode_combo.setFocus()
            self.axis_mode_combo.showPopup()

    def _update_axes_info(self) -> None:
        """Refresh the Axes info panel and tooltip (OME vs heuristic)."""
        img = self.primary_image
        if img.array is not None:
            t, z, y, x = img.array.shape
        else:
            shape = img.shape
            if len(shape) == 2:
                t, z, y, x = 1, 1, shape[0], shape[1]
            elif len(shape) == 3:
                if img.has_time and not img.has_z:
                    t, z, y, x = shape[0], 1, shape[1], shape[2]
                elif img.has_z and not img.has_time:
                    t, z, y, x = 1, shape[0], shape[1], shape[2]
                else:
                    t, z, y, x = 1, 1, shape[1], shape[2]
            else:
                t, z, y, x = shape[0], shape[1], shape[2], shape[3]

        interp = img.interpret_3d_as
        self.axes_info_label.setText(
            f"T: {t}  Z: {z}  Y: {y}  X: {x}  | Interpretation: {interp}"
        )
        if img.ome_axes:
            tooltip = f"OME metadata axes: {img.ome_axes}"
        elif img.axis_auto_used and img.axis_auto_mode:
            tooltip = f"Auto heuristic used: {img.axis_auto_mode}"
        else:
            tooltip = "No OME metadata; manual interpretation"
        self.axes_info_label.setToolTip(tooltip)

    def _update_axis_warning(self) -> None:
        """Show a non-intrusive warning when auto heuristics are used."""
        img = self.primary_image
        if img.interpret_3d_as == "auto" and img.axis_auto_used and img.axis_auto_mode:
            mode = img.axis_auto_mode.upper()
            self.axis_warning.setText(
                f'<a href="axes">3D axis interpreted as {mode} (auto). Click to change.</a>'
            )
            self.axis_warning.setVisible(True)
        else:
            self.axis_warning.setVisible(False)

    def _on_limits_changed(self, ax) -> None:
        if ax not in {
            self.ax_frame,
            self.ax_mean,
            self.ax_comp,
            self.ax_support,
            self.ax_std,
        }:
            return
        if self._suppress_limits:
            return
        if self.link_zoom:
            self._last_zoom_linked = (ax.get_xlim(), ax.get_ylim())
            self._update_status()
