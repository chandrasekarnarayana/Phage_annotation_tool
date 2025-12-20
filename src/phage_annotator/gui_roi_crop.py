"""ROI and crop helpers."""

from __future__ import annotations

from typing import Tuple

import numpy as np

from phage_annotator.auto_roi import propose_roi


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
            rect = (
                circle.cx - circle.r,
                circle.cy - circle.r,
                circle.r * 2,
                circle.r * 2,
            )
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
        rect = (0.0, 0.0, float(w), float(h))
        self.controller.set_roi(rect, shape="circle")
        self.roi_rect = rect
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
        """Handle ROI spinbox changes with validation and clamping to image bounds."""
        # Get current values from spinboxes
        x = float(self.roi_x_spin.value())
        y = float(self.roi_y_spin.value())
        w = float(self.roi_w_spin.value())
        h = float(self.roi_h_spin.value())
        
        # Get image bounds
        img = self.primary_image
        if img.array is not None:
            img_h, img_w = img.array.shape[2], img.array.shape[3]
        else:
            img_h, img_w = img.shape[-2], img.shape[-1]
        
        # Clamp to image bounds
        x_clamped = max(0.0, min(x, img_w - 1))
        y_clamped = max(0.0, min(y, img_h - 1))
        w_clamped = max(1.0, min(w, img_w - x_clamped))
        h_clamped = max(1.0, min(h, img_h - y_clamped))
        
        # Update spinboxes if values were clamped
        if x_clamped != x or y_clamped != y or w_clamped != w or h_clamped != h:
            self.roi_x_spin.blockSignals(True)
            self.roi_y_spin.blockSignals(True)
            self.roi_w_spin.blockSignals(True)
            self.roi_h_spin.blockSignals(True)
            
            self.roi_x_spin.setValue(x_clamped)
            self.roi_y_spin.setValue(y_clamped)
            self.roi_w_spin.setValue(w_clamped)
            self.roi_h_spin.setValue(h_clamped)
            
            self.roi_x_spin.blockSignals(False)
            self.roi_y_spin.blockSignals(False)
            self.roi_w_spin.blockSignals(False)
            self.roi_h_spin.blockSignals(False)
            
            # Show feedback to user
            self._set_status("ROI clamped to image bounds")
        
        rect = (x_clamped, y_clamped, w_clamped, h_clamped)
        self.controller.set_roi(rect, shape=self.roi_shape)
        self.roi_rect = rect
        self.recorder.record("roi_change", {"rect": self.roi_rect, "shape": self.roi_shape})
        self._refresh_image()

    def _on_roi_shape_change(self) -> None:
        btns = self.roi_shape_group.buttons()
        if not btns:
            return
        if btns[0].isChecked():
            shape = "box"
        else:
            shape = "circle"
        self.controller.set_roi(self.roi_rect, shape=shape)
        self.roi_shape = shape
        self.recorder.record("roi_shape", {"shape": shape})
        self._refresh_image()

    def _auto_roi_mode_changed(self, text: str) -> None:
        if not hasattr(self, "auto_roi_wh_widget"):
            return
        use_area = text == "Area"
        self.auto_roi_wh_widget.setVisible(not use_area)
        self.auto_roi_area_widget.setVisible(use_area)
        self._persist_auto_roi_settings()

    def _persist_auto_roi_settings(self) -> None:
        if not hasattr(self, "_settings"):
            return
        if getattr(self, "auto_roi_shape_combo", None) is not None:
            self._settings.setValue("autoRoiShape", self.auto_roi_shape_combo.currentText())
        if getattr(self, "auto_roi_mode_combo", None) is not None:
            self._settings.setValue("autoRoiMode", self.auto_roi_mode_combo.currentText())
        if getattr(self, "auto_roi_w_spin", None) is not None:
            self._settings.setValue("autoRoiW", int(self.auto_roi_w_spin.value()))
        if getattr(self, "auto_roi_h_spin", None) is not None:
            self._settings.setValue("autoRoiH", int(self.auto_roi_h_spin.value()))
        if getattr(self, "auto_roi_area_spin", None) is not None:
            self._settings.setValue("autoRoiArea", int(self.auto_roi_area_spin.value()))

    def _sync_auto_roi_controls_from_settings(self) -> None:
        if not hasattr(self, "_settings"):
            return
        if getattr(self, "auto_roi_shape_combo", None) is not None:
            self.auto_roi_shape_combo.setCurrentText(
                self._settings.value("autoRoiShape", "box", type=str)
            )
        if getattr(self, "auto_roi_mode_combo", None) is not None:
            self.auto_roi_mode_combo.setCurrentText(
                self._settings.value("autoRoiMode", "W/H", type=str)
            )
        if getattr(self, "auto_roi_w_spin", None) is not None:
            self.auto_roi_w_spin.setValue(self._settings.value("autoRoiW", 100, type=int))
        if getattr(self, "auto_roi_h_spin", None) is not None:
            self.auto_roi_h_spin.setValue(self._settings.value("autoRoiH", 100, type=int))
        if getattr(self, "auto_roi_area_spin", None) is not None:
            self.auto_roi_area_spin.setValue(self._settings.value("autoRoiArea", 100 * 100, type=int))

    def _run_auto_roi(self) -> None:
        if self.primary_image.array is None:
            self._set_status("Load an image first.")
            return
        if self._auto_roi_job_id is not None:
            self.jobs.cancel(self._auto_roi_job_id)
            self._auto_roi_job_id = None
        self._job_generation += 1

        shape = self.auto_roi_shape_combo.currentText()
        size_mode = self.auto_roi_mode_combo.currentText()
        req_w = req_h = req_area = None
        if size_mode == "Area":
            req_area = int(self.auto_roi_area_spin.value())
        else:
            req_w = int(self.auto_roi_w_spin.value())
            req_h = int(self.auto_roi_h_spin.value())

        slice_data = self._slice_data(self.primary_image)
        crop_offset = (0, 0)
        if self.crop_rect:
            crop_offset = (int(max(0, self.crop_rect[0])), int(max(0, self.crop_rect[1])))
            slice_data = self._apply_crop_rect(slice_data, self.crop_rect, slice_data.shape)

        job_gen = self._job_generation

        def _job(progress, cancel_token):
            if cancel_token.is_cancelled():
                return None
            spec, diag = propose_roi(
                slice_data,
                shape=shape,
                request_w=req_w,
                request_h=req_h,
                request_area=req_area,
                min_side=100,
                max_circle_radius=300,
                max_area=None,
                stride=None,
                bg_sigma=30.0,
                p_low=1.0,
                p_high=99.5,
                weights=None,
            )
            if cancel_token.is_cancelled():
                return None
            return spec, diag, job_gen

        def _on_result(result) -> None:
            if result is None:
                return
            spec, diag, gen = result
            if gen != self._job_generation:
                return
            x, y, w, h = spec.rect
            if self.crop_rect:
                x += crop_offset[0]
                y += crop_offset[1]
            if spec.shape == "circle":
                cx = x + w / 2.0
                cy = y + h / 2.0
                r = min(w, h) / 2.0
                self.controller.set_roi_circle(float(cx), float(cy), float(r))
            else:
                self.controller.set_roi_box(float(x), float(y), float(w), float(h))
            self.roi_shape = spec.shape
            self.roi_rect = (float(x), float(y), float(w), float(h))
            self._sync_roi_controls()
            tip = (
                f"score={diag.get('score', 0):.3f} "
                f"low={diag.get('low_frac', 0):.3f} "
                f"high={diag.get('high_frac', 0):.3f} "
                f"grad={diag.get('grad', 0):.3f}"
            )
            self.auto_roi_btn.setToolTip(tip)
            self._set_status("Auto ROI applied.")
            self.recorder.record("auto_roi", {"shape": spec.shape, "rect": self.roi_rect, **diag})
            self._refresh_image()

        def _on_error(err: str) -> None:
            self._append_log(f"[Auto ROI] Error\n{err}")
            self._set_status("Auto ROI failed.")

        handle = self.jobs.submit(_job, name="Auto ROI", on_result=_on_result, on_error=_on_error)
        self._auto_roi_job_id = handle.job_id
        self._set_status("Auto ROI running…")

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
        """Handle crop spinbox changes with validation and clamping to image bounds."""
        # Get current values from spinboxes
        x = float(self.crop_x_spin.value())
        y = float(self.crop_y_spin.value())
        w = float(self.crop_w_spin.value())
        h = float(self.crop_h_spin.value())
        
        # Handle zero/negative dimensions
        if w <= 0 or h <= 0:
            self.crop_rect = None
            self._refresh_image()
            return
        
        # Get image bounds
        img = self.primary_image
        if img.array is not None:
            img_h, img_w = img.array.shape[2], img.array.shape[3]
        else:
            img_h, img_w = img.shape[-2], img.shape[-1]
        
        # Clamp to image bounds
        x_clamped = max(0.0, min(x, img_w - 1))
        y_clamped = max(0.0, min(y, img_h - 1))
        w_clamped = max(1.0, min(w, img_w - x_clamped))
        h_clamped = max(1.0, min(h, img_h - y_clamped))
        
        # Update spinboxes if values were clamped
        if x_clamped != x or y_clamped != y or w_clamped != w or h_clamped != h:
            self.crop_x_spin.blockSignals(True)
            self.crop_y_spin.blockSignals(True)
            self.crop_w_spin.blockSignals(True)
            self.crop_h_spin.blockSignals(True)
            
            self.crop_x_spin.setValue(x_clamped)
            self.crop_y_spin.setValue(y_clamped)
            self.crop_w_spin.setValue(w_clamped)
            self.crop_h_spin.setValue(h_clamped)
            
            self.crop_x_spin.blockSignals(False)
            self.crop_y_spin.blockSignals(False)
            self.crop_w_spin.blockSignals(False)
            self.crop_h_spin.blockSignals(False)
            
            # Show feedback to user
            self._set_status("Crop clamped to image bounds")
        
        self.crop_rect = (x_clamped, y_clamped, w_clamped, h_clamped)
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
        layout_spec = {
            "order": ["frame", "mean", "composite", "support", "std"],
            "panel_visibility": self._panel_visibility,
        }
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
