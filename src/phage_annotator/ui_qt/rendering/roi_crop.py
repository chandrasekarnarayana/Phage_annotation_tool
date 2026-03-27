"""ROI and crop helpers."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode


class RoiCropMixin:
    """Mixin for ROI and crop computations."""

    def _current_sync_group_key_for_roi(self) -> str:
        """Resolve the active/manual sync group key used for ROI sharing."""
        try:
            if hasattr(self, "_sync_follow_active_enabled") and self._sync_follow_active_enabled():
                if hasattr(self, "_sync_key_active_group"):
                    return str(self._sync_key_active_group() or "").strip()
            combo = getattr(self, "sync_key_combo", None)
            if combo is not None:
                return str(combo.currentData() or "").strip()
        except Exception:
            return ""
        return ""

    def _store_roi_for_current_sync_group(self) -> None:
        """Store current ROI state for the active sync group."""
        key = self._current_sync_group_key_for_roi()
        if not key:
            return
        state = None
        if str(getattr(self, "roi_shape", "none")) != "none":
            state = {
                "shape": str(getattr(self, "roi_shape", "box")),
                "rect": tuple(float(v) for v in tuple(getattr(self, "roi_rect", (0, 0, 0, 0)))),
            }
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "set_roi_state_for_sync_group"):
            controller.set_roi_state_for_sync_group(key, state)
            return

    def _apply_roi_for_sync_group(self, group_key: str) -> None:
        """Apply stored ROI for a sync group, if any."""
        key = str(group_key or "").strip()
        if not key:
            return
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "roi_state_for_sync_group"):
            state = controller.roi_state_for_sync_group(key)
            if state is None and key not in dict(getattr(controller.session_state, "roi_by_sync_group", {}) or {}):
                state = "__missing__"
        else:
            state = "__missing__"
        if state == "__missing__":
            return
        if state is None:
            self.controller.clear_roi()
            self.roi_shape = "none"
            self.roi_rect = (0.0, 0.0, 0.0, 0.0)
            self._sync_roi_controls()
            self._request_ui_refresh("roi-crop")
            return
        shape = str(state.get("shape", "box"))
        rect = tuple(state.get("rect", (0.0, 0.0, 0.0, 0.0)))
        if len(rect) != 4:
            return
        current_shape = str(getattr(self, "roi_shape", "none"))
        current_rect = tuple(getattr(self, "roi_rect", (0.0, 0.0, 0.0, 0.0)))
        if current_shape == shape and current_rect == tuple(rect):
            return
        self.controller.set_roi(tuple(rect), shape=shape)
        self.roi_shape = shape
        self.roi_rect = tuple(float(v) for v in rect)
        self._sync_roi_controls()
        self._request_ui_refresh("roi-crop")

    def _current_layout_spec(self) -> dict:
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

    def _roi_mask(self, shape: Tuple[int, ...]) -> np.ndarray:
        if len(shape) < 2:
            raise ValueError(f"Invalid shape for ROI mask: {shape}")
        h, w = int(shape[0]), int(shape[1])
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
        # For multi-channel views, apply 2D ROI mask over spatial dimensions.
        return np.asarray(slice_data[mask]).reshape(-1)

    def _clear_roi(self) -> None:
        """Clear the active ROI selection (P3.3: confirmation added)."""
        # Check if confirmation is needed
        if self._settings.value("confirmClearROI", True, type=bool):
            reply = QtWidgets.QMessageBox.question(
                self,
                "Clear ROI",
                "Clear the current ROI selection?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.controller.clear_roi()
        self._sync_roi_controls()
        self._request_ui_refresh("roi-crop")

    def _toggle_roi_handles(self, checked: bool) -> None:
        """Show/hide ROI resize handles on the canvas."""
        self.show_roi_handles = bool(checked)
        self._settings.setValue("showRoiHandles", self.show_roi_handles)
        self._request_ui_refresh("roi-crop")

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
            self.roi_shape = "none"
            self.roi_rect = (0.0, 0.0, 0.0, 0.0)
            self._sync_roi_controls()
        self._store_roi_for_current_sync_group()
        self._update_status()
        self._request_ui_refresh("roi-crop")

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
        self._store_roi_for_current_sync_group()
        self._sync_roi_controls()
        self._request_ui_refresh("roi-crop")

    def _sync_roi_controls(self) -> None:
        if not all(
            hasattr(self, attr)
            for attr in ("roi_x_spin", "roi_y_spin", "roi_w_spin", "roi_h_spin")
        ):
            return
        group = getattr(self, "roi_shape_group", None)
        if group is not None:
            buttons = list(group.buttons())
            if len(buttons) >= 2:
                is_box = str(getattr(self, "roi_shape", "box")) == "box"
                buttons[0].blockSignals(True)
                buttons[1].blockSignals(True)
                buttons[0].setChecked(bool(is_box))
                buttons[1].setChecked(not bool(is_box))
                buttons[0].blockSignals(False)
                buttons[1].blockSignals(False)
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

    def _on_crop_change(self) -> None:
        """Handle crop spinbox changes with validation and clamping to image bounds."""
        if any(
            getattr(self, attr, None) is None
            for attr in ("crop_x_spin", "crop_y_spin", "crop_w_spin", "crop_h_spin")
        ):
            return
        # Get current values from spinboxes
        x = float(self.crop_x_spin.value())
        y = float(self.crop_y_spin.value())
        w = float(self.crop_w_spin.value())
        h = float(self.crop_h_spin.value())
        
        # Handle zero/negative dimensions
        if w <= 0 or h <= 0:
            self.crop_rect = None
            self._request_ui_refresh("roi-crop")
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
            self._status_warning("Crop clamped to image bounds", source="crop.bounds")
        
        self.crop_rect = (x_clamped, y_clamped, w_clamped, h_clamped)
        self._request_ui_refresh("roi-crop")

    def _sync_crop_controls(self) -> None:
        if any(
            getattr(self, attr, None) is None
            for attr in ("crop_x_spin", "crop_y_spin", "crop_w_spin", "crop_h_spin")
        ):
            return
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
        key = str(key)
        if key not in self._panel_visibility:
            self._panel_visibility[key] = bool(checked)
        allow_empty = bool(getattr(self, "_allow_empty_canvas_rows", True))
        if (not allow_empty) and (not checked) and sum(self._panel_visibility.values()) <= 1:
            if key in self.panel_actions:
                self.panel_actions[key].setChecked(True)
            if hasattr(self, "_annotation_view_checkboxes"):
                chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(str(key))
                if chk is not None:
                    chk.blockSignals(True)
                    chk.setChecked(True)
                    chk.blockSignals(False)
            return
        self._panel_visibility[key] = checked
        if key in self.panel_actions and self.panel_actions[key].isChecked() != checked:
            self.panel_actions[key].blockSignals(True)
            self.panel_actions[key].setChecked(checked)
            self.panel_actions[key].blockSignals(False)
        if hasattr(self, "_annotation_view_checkboxes"):
            chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(str(key))
            if chk is not None and chk.isChecked() != checked:
                chk.blockSignals(True)
                chk.setChecked(checked)
                chk.blockSignals(False)
        if hasattr(self, "_set_lazy_row_visible_state"):
            self._set_lazy_row_visible_state(str(key), bool(checked))
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        self._rebuild_figure_layout()
        self._request_ui_refresh("roi-crop")

    def _panel_grid_shape(self, n: int) -> Tuple[int, int]:
        if n <= 1:
            return 1, 1
        rows_override = int(getattr(self, "_canvas_layout_rows", 0) or 0)
        cols_override = int(getattr(self, "_canvas_layout_cols", 0) or 0)
        if rows_override > 0 and cols_override > 0:
            return max(1, rows_override), max(1, cols_override)
        if rows_override > 0:
            rows = max(1, rows_override)
            cols = int(np.ceil(float(n) / float(rows)))
            return rows, max(1, cols)
        if cols_override > 0:
            cols = max(1, cols_override)
            rows = int(np.ceil(float(n) / float(cols)))
            return max(1, rows), cols
        # Default auto layout: choose an adaptive near-square grid for any N.
        # Scoring priorities:
        # 1) Minimize empty cells
        # 2) Keep grid balanced (cols close to rows)
        # 3) Prefer fewer rows on ties (wider canvas-friendly layout)
        best_rows, best_cols = 1, n
        best_score = None
        for rows in range(1, n + 1):
            cols = int(np.ceil(float(n) / float(rows)))
            empty = int(rows * cols - n)
            balance = abs(cols - rows)
            score = (empty * 10) + balance
            candidate = (score, rows)
            if best_score is None or candidate < best_score:
                best_score = candidate
                best_rows, best_cols = rows, cols
        return max(1, int(best_rows)), max(1, int(best_cols))

    def _rebuild_figure_layout(self, layout_spec: Optional[dict] = None) -> None:
        if layout_spec is None:
            layout_spec = self._current_layout_spec()
        if not self.renderer.request_layout_rebuild(layout_spec):
            return
        order = layout_spec["order"]
        panel_visibility = layout_spec.get("panel_visibility", {})
        visible = [key for key in order if panel_visibility.get(key, False)]
        axes = {}
        if getattr(self, "modality_canvas", None) is not None:
            panel_indices = {key: i for i, key in enumerate(visible)}
            panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
            specs = []
            for key in visible:
                modality = panel_map.get(key)
                title = str(getattr(modality, "display_name", key.title()))
                specs.append((panel_indices[key], title))
            self.modality_canvas.set_layout_mode(LayoutMode.AUTO)
            self.modality_canvas.set_modalities(specs, grid=self._panel_grid_shape(len(visible)))
            for key in visible:
                view = self.modality_canvas.get_view(panel_indices[key])
                if view is not None:
                    axes[key] = view.ax
            axes = self.renderer.init_external_axes(axes, visible)
        else:
            axes = self.renderer.init_figure(layout_spec)
        primary_key = visible[0] if visible else None
        self.ax_frame = axes.get(primary_key) if primary_key is not None else None
        self.ax_mean = None
        self.ax_comp = None
        self.ax_support = None
        self.ax_std = None
        self._sync_view_manager_panels(visible)
        self._bind_axis_callbacks()
        if self.tool_router is not None:
            self._set_roi_interactor_tool(self.tool_router.tool)

    def _copy_roi_to_all_images(self) -> None:
        """Copy the current ROI to all open images (P5.2).
        
        Requires user confirmation and copies the current ROI shape and position
        to all other open images. The copied ROIs will have new IDs but retain
        the same shape, position, color, and visibility settings.
        """
        active_roi = self.roi_manager.get_active(self.primary_image.id)
        if active_roi is None or self.roi_rect == (0, 0, 0, 0):
            QtWidgets.QMessageBox.warning(
                self,
                "No ROI to copy",
                "Please define an ROI before copying to all images."
            )
            return

        # Confirm with user
        reply = QtWidgets.QMessageBox.question(
            self,
            "Copy ROI to all images",
            f"Copy ROI '{active_roi.name}' to all {len(self.images) - 1} other open images?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        # Copy to all images
        target_ids = [img.id for img in self.images if img.id != self.primary_image.id]
        count = self.roi_manager.copy_roi_to_images(
            self.primary_image.id,
            active_roi.roi_id,
            target_ids
        )

        self.recorder.record("copy_roi_to_all_images", {"count": count})
        QtWidgets.QMessageBox.information(
            self,
            "ROI copied",
            f"Copied ROI to {count} image{'s' if count != 1 else ''}."
        )

    def _save_roi_template(self) -> None:
        """Save the current ROI as a reusable template (P5.2).
        
        Opens a dialog to name the template, then saves it for later
        application to other images via _apply_roi_template().
        """
        active_roi = self.roi_manager.get_active(self.primary_image.id)
        if active_roi is None or self.roi_rect == (0, 0, 0, 0):
            QtWidgets.QMessageBox.warning(
                self,
                "No ROI to save",
                "Please define an ROI before saving as template."
            )
            return

        # Get template name from user
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Save ROI Template",
            "Template name:",
            text=active_roi.name
        )
        if not ok or not name:
            return

        self.roi_manager.save_roi_template(name, active_roi)
        self.recorder.record("save_roi_template", {"name": name})
        QtWidgets.QMessageBox.information(
            self,
            "Template saved",
            f"ROI template '{name}' saved successfully."
        )

    def _apply_roi_template(self, template_name: str = None) -> None:
        """Apply a saved ROI template to the current image (P5.2).
        
        If template_name is None, opens a dialog to select from available templates.
        Otherwise applies the named template directly.
        """
        available = self.roi_manager.list_templates()
        if not available:
            QtWidgets.QMessageBox.warning(
                self,
                "No templates available",
                "Create a template first by saving an ROI."
            )
            return

        # Select template if not provided
        if template_name is None:
            template_name, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Apply ROI Template",
                "Select template:",
                available
            )
            if not ok or not template_name:
                return

        # Apply template
        if self.roi_manager.apply_template_to_image(template_name, self.primary_image.id):
            # Update UI
            new_roi = self.roi_manager.get_active(self.primary_image.id)
            if new_roi:
                rect = (
                    new_roi.points[0][0] if new_roi.points else 0,
                    new_roi.points[0][1] if new_roi.points else 0,
                    new_roi.points[1][0] - new_roi.points[0][0] if len(new_roi.points) > 1 else 100,
                    new_roi.points[1][1] - new_roi.points[0][1] if len(new_roi.points) > 1 else 100,
                )
                self.controller.set_roi(rect, shape=new_roi.roi_type)
                self._sync_roi_controls()
                self._request_ui_refresh("roi-crop")
                self.recorder.record("apply_roi_template", {"template": template_name})
                QtWidgets.QMessageBox.information(
                    self,
                    "Template applied",
                    f"Applied template '{template_name}' to current image."
                )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Template not found",
                f"Template '{template_name}' could not be found."
            )
