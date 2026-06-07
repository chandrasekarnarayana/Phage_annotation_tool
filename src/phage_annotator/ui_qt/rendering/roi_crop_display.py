"""Extracted method group 3 for RoiCropMixin."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode



class RoiCropDisplayMixin:
    """Method group 3 extracted from RoiCropMixin."""

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
        """Synchronize crop controls for the current workflow."""
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
        """Apply crop for the current workflow."""
        if self.crop_rect is None:
            return data
        return self._apply_crop_rect(data, self.crop_rect, (data.shape[0], data.shape[1]))
    def _on_panel_toggle(self, key: str, checked: bool) -> None:
        """Handle the on panel toggle helper flow."""
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
        """Handle the panel grid shape helper flow."""
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
        """Handle the rebuild figure layout helper flow."""
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
