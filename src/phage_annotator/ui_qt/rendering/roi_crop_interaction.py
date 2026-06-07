"""ROI and crop helpers."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode

class RoiCropInteractionMixin:
    """ROI shape interaction, sync group, mask/value helpers, and controls sync."""

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

    def _roi_mask(self, shape: Tuple[int, ...]) -> np.ndarray:
        """Document the roi_mask flow."""
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
        """Document the roi_values flow."""
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
        """Document the sync_roi_controls flow."""
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
        """Document the on_roi_shape_change flow."""
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
