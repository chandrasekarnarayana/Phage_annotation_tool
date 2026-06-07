"""Brightness/contrast slider and spin-box controls."""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


class DisplayContrastControls:
    """Control helpers for BC sliders, spin boxes, and range widgets."""

    def _display_source_panel_key(self) -> str:
        """Handle the display source panel key helper flow."""
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        target = str(getattr(self, "annotate_target", "")).strip()
        if target and target in panel_map:
            return target
        if panel_map:
            return next(iter(panel_map.keys()))
        return "modality_0"

    def _display_source_image(self):
        """Handle the display source image helper flow."""
        panel_key = self._display_source_panel_key()
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(panel_key)
        if modality is not None:
            img = self._image_obj_from_id(int(getattr(modality, "image_id", -1)))
            if img is not None:
                return img
        return self.primary_image

    def _bc_value_from_slider(self, value: int) -> float:
        """Handle the bc value from slider helper flow."""
        scale = float(getattr(self, "_bc_slider_scale", 1.0))
        if scale <= 0:
            return float(value)
        return float(value) / scale

    def _bc_slider_from_value(self, value: float) -> int:
        """Handle the bc slider from value helper flow."""
        scale = float(getattr(self, "_bc_slider_scale", 1.0))
        return int(round(float(value) * scale))

    def _bc_set_controls(self, min_val: float, max_val: float) -> None:
        """Handle the bc set controls helper flow."""
        if getattr(self, "bc_min_spin", None) is None:
            return
        range_slider = getattr(self, "bc_range_slider", None)
        min_slider_widget = getattr(self, "bc_min_slider", None)
        max_slider_widget = getattr(self, "bc_max_slider", None)
        self._bc_updating_controls = True
        try:
            self.bc_min_spin.blockSignals(True)
            self.bc_max_spin.blockSignals(True)
            if min_slider_widget is not None:
                min_slider_widget.blockSignals(True)
            if max_slider_widget is not None:
                max_slider_widget.blockSignals(True)
            if range_slider is not None:
                range_slider.blockSignals(True)
            self.bc_min_spin.setValue(float(min_val))
            self.bc_max_spin.setValue(float(max_val))
            if range_slider is not None:
                range_slider.setValues(min_val, max_val, emit_signal=False)
            if min_slider_widget is not None and max_slider_widget is not None:
                min_slider_widget.setValue(self._bc_slider_from_value(min_val))
                max_slider_widget.setValue(self._bc_slider_from_value(max_val))
        finally:
            self.bc_min_spin.blockSignals(False)
            self.bc_max_spin.blockSignals(False)
            if min_slider_widget is not None:
                min_slider_widget.blockSignals(False)
            if max_slider_widget is not None:
                max_slider_widget.blockSignals(False)
            if range_slider is not None:
                range_slider.blockSignals(False)
            self._bc_updating_controls = False

    def _bc_apply_minmax(self, min_val: float, max_val: float) -> None:
        """Handle the bc apply minmax helper flow."""
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return

        # Log contrast change
        logger = get_panel_logger("contrast")
        old_mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        logger.log_value_change(
            "contrast",
            f"({old_mapping.min_val:.3f}, {old_mapping.max_val:.3f})",
            f"({min_val:.3f}, {max_val:.3f})",
            panel=panel_key
        )

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
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        mapping.set_window(min_val, max_val)
        self._sync_modality_display_settings(panel_key, mapping)
        self._propagate_sync_to_modalities(prim.id, panel_key, min_val, max_val)
        if self.vmin_label is not None:
            self.vmin_label.setText(f"vmin: {min_val:.3f}")
        if self.vmax_label is not None:
            self.vmax_label.setText(f"vmax: {max_val:.3f}")
        self._bc_set_controls(min_val, max_val)
        self._sync_contrast_from_frame()
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")

    def _update_bc_controls(self, vals: np.ndarray, vmin: float, vmax: float) -> None:
        """Update bc controls for the current workflow."""
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
        range_slider = getattr(self, "bc_range_slider", None)
        min_slider_widget = getattr(self, "bc_min_slider", None)
        max_slider_widget = getattr(self, "bc_max_slider", None)
        self._bc_updating_controls = True
        try:
            for spin in (self.bc_min_spin, self.bc_max_spin):
                spin.blockSignals(True)
                spin.setDecimals(decimals)
                spin.setSingleStep(step)
                spin.setRange(data_min, data_max)
            if min_slider_widget is not None and max_slider_widget is not None:
                for slider in (min_slider_widget, max_slider_widget):
                    slider.blockSignals(True)
                    slider.setRange(min_slider, max_slider)
                    slider.setSingleStep(1)
                    slider.setPageStep(max(1, int(10 * scale)))
            if range_slider is not None:
                range_slider.blockSignals(True)
                range_slider.setRange(data_min, data_max)
                range_slider.setStep(step)
            data_mid = 0.5 * (data_min + data_max)
            min_val = float(vmin)
            max_val = float(vmax)
            center = 0.5 * (min_val + max_val)
            width = max(max_val - min_val, step)
            b_range = max(1, int(round((data_max - data_min) / step)))
            self.bc_brightness_slider.setRange(-b_range, b_range)
            brightness_val = int(round((center - data_mid) / step))
            self.bc_brightness_slider.setValue(max(-b_range, min(b_range, brightness_val)))
            c_min = -90
            c_max = 300
            self.bc_contrast_slider.setRange(c_min, c_max)
            contrast_val = int(round((data_max - data_min) / width - 1.0) * 100)
            self.bc_contrast_slider.setValue(max(c_min, min(c_max, contrast_val)))
            self.bc_min_spin.setValue(float(vmin))
            self.bc_max_spin.setValue(float(vmax))
            if min_slider_widget is not None and max_slider_widget is not None:
                min_slider_widget.setValue(self._bc_slider_from_value(vmin))
                max_slider_widget.setValue(self._bc_slider_from_value(vmax))
            if range_slider is not None:
                range_slider.setValues(vmin, vmax, emit_signal=False)
        finally:
            for spin in (self.bc_min_spin, self.bc_max_spin):
                spin.blockSignals(False)
            if min_slider_widget is not None and max_slider_widget is not None:
                for slider in (min_slider_widget, max_slider_widget):
                    slider.blockSignals(False)
            if range_slider is not None:
                range_slider.blockSignals(False)
            self._bc_updating_controls = False
        self._bc_update_preview(vmin, vmax)

    def _on_bc_min_slider(self, value: int) -> None:
        """Handle the on bc min slider helper flow."""
        if getattr(self, "_bc_updating_controls", False):
            return
        self._bc_apply_minmax(self._bc_value_from_slider(value), float(self.bc_max_spin.value()))

    def _on_bc_max_slider(self, value: int) -> None:
        """Handle the on bc max slider helper flow."""
        if getattr(self, "_bc_updating_controls", False):
            return
        self._bc_apply_minmax(float(self.bc_min_spin.value()), self._bc_value_from_slider(value))

    def _on_bc_min_spin(self, value: float) -> None:
        """Handle the on bc min spin helper flow."""
        if getattr(self, "_bc_updating_controls", False):
            return
        self._bc_apply_minmax(float(value), float(self.bc_max_spin.value()))

    def _on_bc_max_spin(self, value: float) -> None:
        """Handle the on bc max spin helper flow."""
        if getattr(self, "_bc_updating_controls", False):
            return
        self._bc_apply_minmax(float(self.bc_min_spin.value()), float(value))

    def _on_bc_brightness_change(self, value: int) -> None:
        """Handle the on bc brightness change helper flow."""
        if getattr(self, "_bc_updating_controls", False):
            return
        data_min = getattr(self, "_bc_data_min", None)
        data_max = getattr(self, "_bc_data_max", None)
        if data_min is None or data_max is None:
            return
        step = float(getattr(self, "_bc_step", 1.0))
        data_mid = 0.5 * (data_min + data_max)
        center = data_mid + value * step
        min_val, max_val = self._current_vmin_vmax()
        width = max_val - min_val
        self._bc_apply_minmax(center - width / 2.0, center + width / 2.0)
