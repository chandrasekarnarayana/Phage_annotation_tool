"""Contrast sync helpers: preview rendering, modality sync, frame sync."""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


class DisplayContrastSync:
    """Sync and preview helpers for brightness/contrast."""

    def _on_bc_contrast_change(self, value: int) -> None:
        """Handle the on bc contrast change helper flow."""
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
        width = max(data_range / denom, float(getattr(self, "_bc_step", 1.0)))
        self._bc_apply_minmax(center - width / 2.0, center + width / 2.0)

    def _bc_set_from_inputs(self) -> None:
        """Handle the bc set from inputs helper flow."""
        if getattr(self, "bc_min_spin", None) is None:
            return
        self._bc_apply_minmax(float(self.bc_min_spin.value()), float(self.bc_max_spin.value()))

    def _bc_update_preview(self, min_val: float, max_val: float) -> None:
        """Handle the bc update preview helper flow."""
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
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            rect = QtCore.QRect(4, 4, width - 8, height - 8)
            painter.setPen(QtGui.QPen(QtGui.QColor("#111111"), 1))
            painter.drawRect(rect)
            if data_max == data_min:
                return

            def _x(val: float) -> int:
                """Handle the x helper flow."""
                return int(rect.left() + (val - data_min) / (data_max - data_min) * rect.width())

            x1 = _x(min_val)
            x2 = _x(max_val)
            y0 = rect.bottom()
            y1 = rect.top()
            painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 2))
            painter.drawLine(rect.left(), y0, x1, y0)
            painter.drawLine(x1, y0, x2, y1)
            painter.drawLine(x2, y1, rect.right(), y1)
        finally:
            painter.end()
            label.setPixmap(pm)

    def _on_bc_range_changed(self, min_val: float, max_val: float) -> None:
        """Handle the on bc range changed helper flow."""
        if getattr(self, "_bc_updating_controls", False):
            return
        self._bc_apply_minmax(float(min_val), float(max_val))

    def _sync_modality_display_settings(self, panel: str, mapping) -> None:
        """Synchronize modality display settings for the current workflow."""
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(panel)
        if modality is None:
            return
        settings = modality.display_settings
        settings.vmin = float(mapping.min_val)
        settings.vmax = float(mapping.max_val)
        settings.lut = int(mapping.lut)
        settings.gamma = float(mapping.gamma)

    def _image_obj_from_id(self, image_id: int):
        """Handle the image obj from id helper flow."""
        target = int(image_id)
        for img in self.images:
            if int(getattr(img, "id", -1)) == target:
                return img
        if 0 <= target < len(self.images):
            return self.images[target]
        return None

    def _sync_contrast_from_frame(self) -> None:
        """Synchronize contrast from frame for the current workflow."""
        panel_keys = self._contrast_target_panels()
        if not panel_keys:
            return
        source_panel = self._display_source_panel_key()
        panel_map = getattr(self, "_panel_modality_map", {})
        source_modality = panel_map.get(source_panel)
        source_image_id = int(getattr(source_modality, "image_id", self.primary_image.id))
        source = self.controller.display_mapping.mapping_for(source_image_id, source_panel)
        for key in panel_keys:
            modality = panel_map.get(key)
            if modality is None:
                continue
            image_id = modality.image_id
            img = self._image_obj_from_id(image_id)
            if img is None:
                continue
            data = img.array if img.array is not None else img
            mapping = self._get_display_mapping(image_id, key, data)
            if key == source_panel and image_id == source_image_id:
                continue
            mapping.min_val = source.min_val
            mapping.max_val = source.max_val
            mapping.lut = source.lut
            mapping.invert = source.invert
            mapping.gamma = source.gamma
            self._sync_modality_display_settings(key, mapping)
