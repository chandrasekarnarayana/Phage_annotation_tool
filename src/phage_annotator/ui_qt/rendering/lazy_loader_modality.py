"""Extracted method group 1 for RoiCropMixin."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode



class LazyLoaderModalityMixin:
    """Method group 1 extracted from RoiCropMixin."""

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
        """Handle the current layout spec helper flow."""
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
        """Handle the roi mask helper flow."""
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
        """Handle the roi values helper flow."""
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
        """Synchronize roi controls for the current workflow."""
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
