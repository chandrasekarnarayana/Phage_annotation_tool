"""ROI and crop helpers."""

from __future__ import annotations

from typing import Tuple

import numpy as np


class RoiCropMixin:
    """Mixin for ROI and crop computations."""

    def _roi_mask(self, shape: Tuple[int, int]) -> np.ndarray:
        h, w = shape
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        rx, ry, rw, rh = self.roi_rect
        if self.roi_shape == "none" or rw <= 0 or rh <= 0:
            return np.ones((h, w), dtype=bool)
        if self.roi_shape == "box":
            return (x >= rx) & (x <= rx + rw) & (y >= ry) & (y <= ry + rh)
        cx = rx + rw / 2
        cy = ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r**2

    def _roi_values(self, slice_data: np.ndarray) -> np.ndarray:
        mask = self._roi_mask(slice_data.shape)
        if not mask.any():
            return slice_data.flatten()
        return slice_data[mask]

    def _clear_roi(self) -> None:
        """Clear the active ROI selection."""
        self.controller.clear_roi()
        self._sync_roi_controls()
        self._refresh_image()

    def _toggle_roi_handles(self, checked: bool) -> None:
        """Show/hide ROI resize handles on the canvas."""
        self.show_roi_handles = bool(checked)
        self._settings.setValue("showRoiHandles", self.show_roi_handles)
        self._refresh_image()

    def _on_roi_interactor_change(self, roi_type, rect, circle) -> None:
        """Sync Matplotlib ROI interactions back into controller/UI state."""
        if roi_type == "box" and rect is not None:
            if self.roi_shape != "box":
                self._set_roi_shape("box")
            self._set_roi_rect((rect.x, rect.y, rect.w, rect.h))
        elif roi_type == "circle" and circle is not None:
            if self.roi_shape != "circle":
                self._set_roi_shape("circle")
            rect = (circle.cx - circle.r, circle.cy - circle.r, circle.r * 2, circle.r * 2)
            self._set_roi_rect(rect)
        else:
            self.controller.clear_roi()
            self._sync_roi_controls()
        self._update_status()
        self._refresh_image()

    def _reset_roi(self) -> None:
        """Reset ROI to the full image bounds."""
        img = self.primary_image
        if img.array is not None:
            h, w = img.array.shape[2], img.array.shape[3]
        else:
            h, w = img.shape[-2], img.shape[-1]
        self.roi_rect = (0.0, 0.0, float(w), float(h))
        self.roi_shape = "circle"
        self._sync_roi_controls()
        self._refresh_image()

    def _sync_roi_controls(self) -> None:
        rect = self.roi_rect
        self.roi_x_spin.blockSignals(True)
        self.roi_y_spin.blockSignals(True)
        self.roi_w_spin.blockSignals(True)
        self.roi_h_spin.blockSignals(True)
        self.roi_x_spin.setValue(rect[0])
        self.roi_y_spin.setValue(rect[1])
        self.roi_w_spin.setValue(rect[2])
        self.roi_h_spin.setValue(rect[3])
        self.roi_x_spin.blockSignals(False)
        self.roi_y_spin.blockSignals(False)
        self.roi_w_spin.blockSignals(False)
        self.roi_h_spin.blockSignals(False)

    def _on_roi_change(self) -> None:
        self.roi_rect = (
            float(self.roi_x_spin.value()),
            float(self.roi_y_spin.value()),
            float(self.roi_w_spin.value()),
            float(self.roi_h_spin.value()),
        )
        self.recorder.record("roi_change", {"rect": self.roi_rect, "shape": self.roi_shape})
        self._refresh_image()

    def _on_roi_shape_change(self) -> None:
        btns = self.roi_shape_group.buttons()
        if not btns:
            return
        if btns[0].isChecked():
            self.roi_shape = "box"
        else:
            self.roi_shape = "circle"
        self.recorder.record("roi_shape", {"shape": self.roi_shape})
        self._refresh_image()

    def _reset_crop(self, initial: bool = False) -> None:
        """Reset crop to full frame bounds."""
        img = self.primary_image
        if img.array is not None:
            h, w = img.array.shape[2], img.array.shape[3]
        else:
            h, w = img.shape[-2], img.shape[-1]
        if initial:
            self.crop_rect = (0.0, 0.0, float(w), float(h))
        else:
            self.crop_rect = None
        self._sync_crop_controls()
        self._refresh_image()

    def _on_crop_change(self) -> None:
        rect = (
            float(self.crop_x_spin.value()),
            float(self.crop_y_spin.value()),
            float(self.crop_w_spin.value()),
            float(self.crop_h_spin.value()),
        )
        if rect[2] <= 0 or rect[3] <= 0:
            self.crop_rect = None
        else:
            self.crop_rect = rect
        self._refresh_image()

    def _sync_crop_controls(self) -> None:
        if self.crop_rect is None:
            rect = (0.0, 0.0, 0.0, 0.0)
        else:
            rect = self.crop_rect
        self.crop_x_spin.blockSignals(True)
        self.crop_y_spin.blockSignals(True)
        self.crop_w_spin.blockSignals(True)
        self.crop_h_spin.blockSignals(True)
        self.crop_x_spin.setValue(rect[0])
        self.crop_y_spin.setValue(rect[1])
        self.crop_w_spin.setValue(rect[2])
        self.crop_h_spin.setValue(rect[3])
        self.crop_x_spin.blockSignals(False)
        self.crop_y_spin.blockSignals(False)
        self.crop_w_spin.blockSignals(False)
        self.crop_h_spin.blockSignals(False)

    def _apply_crop(self, data: np.ndarray) -> np.ndarray:
        if self.crop_rect is None:
            return data
        return self._apply_crop_rect(data, self.crop_rect, (data.shape[0], data.shape[1]))

    def _on_panel_toggle(self, key: str, checked: bool) -> None:
        if not checked and sum(self._panel_visibility.values()) <= 1:
            if key in self.panel_actions:
                self.panel_actions[key].setChecked(True)
            return
        self._panel_visibility[key] = checked
        self._rebuild_figure_layout()
        self._refresh_image()

    def _panel_grid_shape(self, n: int) -> Tuple[int, int]:
        if n <= 1:
            return 1, 1
        if n == 2:
            return 1, 2
        if n == 3:
            return 1, 3
        return 2, 2

    def _rebuild_figure_layout(self) -> None:
        layout_spec = {"order": ["frame", "mean", "composite", "support", "std"], "panel_visibility": self._panel_visibility}
        if not self.renderer.request_layout_rebuild(layout_spec):
            return
        axes = self.renderer.init_figure(layout_spec)
        self.ax_frame = axes.get("frame")
        self.ax_mean = axes.get("mean")
        self.ax_comp = axes.get("composite")
        self.ax_support = axes.get("support")
        self.ax_std = axes.get("std")
        self._bind_axis_callbacks()
        if self.tool_router is not None:
            self._set_roi_interactor_tool(self.tool_router.tool)
