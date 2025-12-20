"""Annotation table, status bar, and view stats helpers."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotations import Keypoint
from phage_annotator.tools import Tool


class TableStatusMixin:
    """Mixin for annotation table and status rendering."""

    def _populate_table(self) -> None:
        """Populate the table from current keypoints."""
        pts = self._current_keypoints()
        self._table_rows = list(pts)
        self.annot_table.blockSignals(True)
        self.annot_table.setRowCount(len(pts))
        for row, kp in enumerate(pts):
            self.annot_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(kp.t)))
            self.annot_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(kp.z)))
            self.annot_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{kp.y:.2f}"))
            self.annot_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{kp.x:.2f}"))
            self.annot_table.setItem(row, 4, QtWidgets.QTableWidgetItem(kp.label))
        self.annot_table.blockSignals(False)
        self.annot_table.resizeColumnsToContents()

    def _on_table_selection(self) -> None:
        if self._block_table:
            return
        self._refresh_image()

    def _on_table_item_changed(self, item: "QtWidgets.QTableWidgetItem") -> None:
        if self._block_table:
            return
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self._table_rows):
            return
        kp = self._table_rows[row]
        text = item.text()
        try:
            if col == 0:
                new_kp = Keypoint(kp.image_id, kp.image_name, int(text), kp.z, kp.y, kp.x, kp.label)
            elif col == 1:
                new_kp = Keypoint(kp.image_id, kp.image_name, kp.t, int(text), kp.y, kp.x, kp.label)
            elif col == 2:
                new_kp = Keypoint(
                    kp.image_id, kp.image_name, kp.t, kp.z, float(text), kp.x, kp.label
                )
            elif col == 3:
                new_kp = Keypoint(
                    kp.image_id, kp.image_name, kp.t, kp.z, kp.y, float(text), kp.label
                )
            elif col == 4:
                new_kp = Keypoint(kp.image_id, kp.image_name, kp.t, kp.z, kp.y, kp.x, text)
            else:
                return
        except ValueError:
            return
        self.controller.update_annotation(self.primary_image.id, kp, new_kp)
        self._mark_dirty()
        self._refresh_image()

    def _delete_selected_annotations(self) -> None:
        if self.annot_table.selectionModel() is None:
            return
        rows = sorted({idx.row() for idx in self.annot_table.selectionModel().selectedRows()})
        if not rows or not self._table_rows:
            return
        removed: List[Keypoint] = []
        for row in reversed(rows):
            if 0 <= row < len(self._table_rows):
                removed.append(self._table_rows[row])
        if removed:
            self.controller.delete_annotations(self.primary_image.id, removed)
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            self._refresh_image()
            self._update_status()
            self._mark_dirty()

    def _update_status(self) -> None:
        total = sum(len(v) for v in self.annotations.values())
        current = len(
            [kp for kp in self._current_keypoints() if kp.t == self.t_slider.value() or kp.t == -1]
        )
        pts_view, area_um2 = self._view_density_stats()
        density_txt = ""
        if area_um2 > 0:
            density = pts_view / area_um2 if area_um2 > 0 else 0.0
            density_txt = f" | View pts: {pts_view} | Area: {area_um2:.2f} um^2 | Density: {density:.3f} /um^2"
        cache_mb, cache_items = self.proj_cache.stats()
        cache_txt = f" | Cache: {cache_mb} MB | Items: {cache_items}"
        self._status_base = f"Label: {self.current_label} | Current slice pts: {current} | Total pts: {total} | Speed {self.speed_slider.value()} fps{density_txt}{cache_txt}"
        self._render_status()
        if self.tool_label is not None and self.tool_router is not None:
            self.tool_label.setText(f"Tool: {self._tool_label(self.tool_router.tool)}")
        if self.cache_stats_label is not None:
            self.cache_stats_label.setText(f"Cache: {cache_mb} MB | Items: {cache_items}")
        self._update_buffer_stats()

    def _set_status(self, text: str) -> None:
        """Set a transient status message; base status persists during playback."""
        self._status_extra = text
        self._render_status()

    def _render_status(self) -> None:
        if self._status_extra:
            self.status.setText(f"{self._status_base} | {self._status_extra}")
        else:
            self.status.setText(self._status_base)

    def _tool_label(self, tool: Tool) -> str:
        labels = {
            Tool.PAN_ZOOM: "Pan/Zoom",
            Tool.ANNOTATE_POINT: "Annotate",
            Tool.ROI_BOX: "ROI Box",
            Tool.ROI_CIRCLE: "ROI Circle",
            Tool.ROI_EDIT: "ROI Edit",
            Tool.PROFILE_LINE: "Profile Line",
            Tool.ERASER: "Eraser",
        }
        return labels.get(tool, tool.value)

    def _label_color(self, label: str, faded: bool = False) -> str:
        palette = {
            "phage": "#1f77b4",
            "not_phage": "#ff7f0e",
            "background": "#2ca02c",
            "other": "#d62728",
        }
        color = palette.get(label, "#2ca02c")
        if faded:
            color = "#cccccc"
        return color

    def _view_density_stats(self) -> Tuple[int, float]:
        axes = [
            ax
            for ax in [
                self.ax_frame,
                self.ax_mean,
                self.ax_comp,
                self.ax_support,
                self.ax_std,
            ]
            if ax is not None
        ]
        if not axes:
            return 0, 0.0
        scale = self._axis_scale(axes[0])
        xlim, ylim = axes[0].get_xlim(), axes[0].get_ylim()
        xlim = (xlim[0] * scale, xlim[1] * scale)
        ylim = (ylim[0] * scale, ylim[1] * scale)
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        circle_mode = self.roi_shape == "circle"
        circle_center = None
        circle_r = None
        if circle_mode and roi_active:
            rx, ry, rw, rh = self.roi_rect
            circle_center = (rx + rw / 2, ry + rh / 2)
            circle_r = min(rw, rh) / 2
        pts = self._current_keypoints()
        pts_view = 0
        for kp in pts:
            if kp.x < xlim[0] or kp.x > xlim[1] or kp.y < ylim[1] or kp.y > ylim[0]:
                continue
            if roi_active:
                if circle_mode and circle_center and circle_r is not None:
                    if (kp.x - circle_center[0]) ** 2 + (
                        kp.y - circle_center[1]
                    ) ** 2 > circle_r**2:
                        continue
                else:
                    rx, ry, rw, rh = self.roi_rect
                    if not (rx <= kp.x <= rx + rw and ry <= kp.y <= ry + rh):
                        continue
            pts_view += 1
        width = abs(xlim[1] - xlim[0])
        height = abs(ylim[1] - ylim[0])
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        area_um2 = (width * height) * (px_um**2) if px_um else 0.0
        return pts_view, area_um2

    def _point_in_roi(self, x: float, y: float) -> bool:
        if self.roi_shape == "none":
            return True
        rx, ry, rw, rh = self.roi_rect
        if rw <= 0 or rh <= 0:
            return True
        if self.roi_shape == "box":
            return rx <= x <= rx + rw and ry <= y <= ry + rh
        cx, cy = rx + rw / 2, ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r**2

    def _current_keypoints(self) -> List[Keypoint]:
        pts = self.annotations.get(self.primary_image.id, [])
        if self.filter_current_chk.isChecked():
            t = self.t_slider.value()
            z = self.z_slider.value()
            pts = [kp for kp in pts if (kp.t in (t, -1) and kp.z in (z, -1))]
        return pts

    def _restore_zoom(self, data_shape: Tuple[int, int]) -> None:
        axes = [
            ax
            for ax in [
                self.ax_frame,
                self.ax_mean,
                self.ax_comp,
                self.ax_support,
                self.ax_std,
            ]
            if ax is not None
        ]
        if not axes:
            return
        if self.link_zoom:
            if self._last_zoom_linked is None:
                self._last_zoom_linked = (
                    (0.0, float(data_shape[1])),
                    (float(data_shape[0]), 0.0),
                )
            for ax in axes:
                scale = self._axis_scale(ax)
                default_xlim = (0, data_shape[1] / scale)
                default_ylim = (data_shape[0] / scale, 0)
                xlim_full, ylim_full = self._last_zoom_linked
                xlim = (xlim_full[0] / scale, xlim_full[1] / scale)
                ylim = (ylim_full[0] / scale, ylim_full[1] / scale)
                ax.set_xlim(xlim if self._valid_zoom(xlim_full, ylim_full) else default_xlim)
                ax.set_ylim(ylim if self._valid_zoom(xlim_full, ylim_full) else default_ylim)
        else:
            for ax in axes:
                scale = self._axis_scale(ax)
                default_xlim = (0, data_shape[1] / scale)
                default_ylim = (data_shape[0] / scale, 0)
                if ax.get_xlim() == (0.0, 1.0) or ax.get_ylim() == (0.0, 1.0):
                    ax.set_xlim(default_xlim)
                    ax.set_ylim(default_ylim)

    def _capture_zoom_state(self) -> None:
        axes = [
            ax
            for ax in [
                self.ax_frame,
                self.ax_mean,
                self.ax_comp,
                self.ax_support,
                self.ax_std,
            ]
            if ax is not None
        ]
        if not axes:
            return
        ax = axes[0]
        scale = self._axis_scale(ax)
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        xlim_full = (xlim[0] * scale, xlim[1] * scale)
        ylim_full = (ylim[0] * scale, ylim[1] * scale)
        if self._valid_zoom(xlim_full, ylim_full):
            self._last_zoom_linked = (xlim_full, ylim_full)

    @staticmethod
    def _valid_zoom(xlim: Tuple[float, float], ylim: Tuple[float, float]) -> bool:
        if xlim[0] == xlim[1] or ylim[0] == ylim[1]:
            return False
        if any(np.isnan(xlim)) or any(np.isnan(ylim)):
            return False
        return True
