"""Extracted method group 2 for RoiCropMixin."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode



class CommandBaseMixin:
    """Method group 2 extracted from RoiCropMixin."""

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
            self._status_warning("ROI clamped to image bounds", source="roi.crop")
        
        rect = (x_clamped, y_clamped, w_clamped, h_clamped)
        self.controller.set_roi(rect, shape=self.roi_shape)
        self.roi_rect = rect
        self._store_roi_for_current_sync_group()
        self.recorder.record("roi_change", {"rect": self.roi_rect, "shape": self.roi_shape})
        if hasattr(self, "_refresh_roi_manager"):
            self._refresh_roi_manager()
        self._request_ui_refresh("roi-crop")
    def _on_roi_shape_change(self) -> None:
        """Handle the on roi shape change helper flow."""
        btns = self.roi_shape_group.buttons()
        if not btns:
            return
        if btns[0].isChecked():
            shape = "box"
        else:
            shape = "circle"
        self.controller.set_roi(self.roi_rect, shape=shape)
        self.roi_shape = shape
        self._store_roi_for_current_sync_group()
        self.recorder.record("roi_shape", {"shape": shape})
        if hasattr(self, "_refresh_roi_manager"):
            self._refresh_roi_manager()
        self._request_ui_refresh("roi-crop")
    def _auto_roi_mode_changed(self, text: str) -> None:
        """Handle the auto roi mode changed helper flow."""
        if not hasattr(self, "auto_roi_wh_widget"):
            return
        use_area = text == "Area"
        self.auto_roi_wh_widget.setVisible(not use_area)
        self.auto_roi_area_widget.setVisible(use_area)
        self._persist_auto_roi_settings()
    def _persist_auto_roi_settings(self) -> None:
        """Handle the persist auto roi settings helper flow."""
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
        """Synchronize auto roi controls from settings for the current workflow."""
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
        """Run auto roi for the current workflow."""
        if self.primary_image.array is None:
            self._status_warning("Load an image first.", source="roi.auto")
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
            """Handle the job helper flow."""
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
            """Handle the on result helper flow."""
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
            self._store_roi_for_current_sync_group()
            self._sync_roi_controls()
            tip = (
                f"score={diag.get('score', 0):.3f} "
                f"low={diag.get('low_frac', 0):.3f} "
                f"high={diag.get('high_frac', 0):.3f} "
                f"grad={diag.get('grad', 0):.3f}"
            )
            self.auto_roi_btn.setToolTip(tip)
            self._status_success("Auto ROI applied.", source="roi.auto")
            self.recorder.record("auto_roi", {"shape": spec.shape, "rect": self.roi_rect, **diag})
            self._request_ui_refresh("roi-crop")

        def _on_error(err: str) -> None:
            """Handle the on error helper flow."""
            self._append_log(f"[Auto ROI] Error\n{err}")
            self._status_error("Auto ROI failed.", source="roi.auto")

        handle = self.jobs.submit(
            _job,
            name="Auto ROI",
            on_result=_on_result,
            on_error=_on_error,
            priority="interactive",
            replace_key="auto-roi",
        )
        self._auto_roi_job_id = handle.job_id
        self._status_info("Auto ROI running…", timeout_ms=2500, source="roi.auto")
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
        self._request_ui_refresh("roi-crop")
