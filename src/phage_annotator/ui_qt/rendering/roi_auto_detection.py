"""ROI and crop helpers."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode

class RoiAutoDetectionMixin:
    """Auto-ROI mode, settings persistence, and ROI detection pipeline."""

    def _current_layout_spec(self) -> dict:
        """Document the current_layout_spec flow."""
        order: list[str] = []
        panel_visibility = dict(self._panel_visibility)
        hidden_base = set(getattr(self, "_lazy_hidden_base_panel_keys", set()) or set())
        self._panel_modality_map = {}
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if not self.images or manager is None:
            return {
                "order": order,
                "panel_visibility": panel_visibility,
            }
        for modality in manager.get_all_modalities():
            key = self._panel_key_for_modality_idx(int(modality.idx))
            self._panel_modality_map[key] = modality
            if key in hidden_base:
                panel_visibility[key] = False
            else:
                panel_visibility[key] = bool(panel_visibility.get(key, True))
        panel_order = dict(getattr(self, "_lazy_panel_order", {}) or {})
        next_order = max([int(v) for v in panel_order.values() if str(v).isdigit()] or [0]) + 1
        for key in self._panel_modality_map.keys():
            if not str(panel_order.get(key, "")).isdigit():
                panel_order[key] = next_order
                next_order += 1
        self._lazy_panel_order = panel_order
        order = sorted(
            list(self._panel_modality_map.keys()),
            key=lambda k: (int(panel_order.get(k, 10**6)), str(k)),
        )
        valid_order_keys = set(order)
        for key in list(panel_visibility.keys()):
            if str(key).startswith("modality_") and str(key) not in valid_order_keys:
                panel_visibility[str(key)] = False
        return {
            "order": order,
            "panel_visibility": panel_visibility,
        }

    def _auto_roi_mode_changed(self, text: str) -> None:
        """Document the auto_roi_mode_changed flow."""
        if not hasattr(self, "auto_roi_wh_widget"):
            return
        use_area = text == "Area"
        self.auto_roi_wh_widget.setVisible(not use_area)
        self.auto_roi_area_widget.setVisible(use_area)
        self._persist_auto_roi_settings()

    def _persist_auto_roi_settings(self) -> None:
        """Document the persist_auto_roi_settings flow."""
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
        """Document the sync_auto_roi_controls_from_settings flow."""
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
        """Document the run_auto_roi flow."""
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
            """Document the job flow."""
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
            """Document the on_result flow."""
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
            """Document the on_error flow."""
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
