"""ROI manager and ROI measurement handlers."""

from __future__ import annotations

import pathlib
import time
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi_manager import Roi, save_rois_json, load_rois_json
from phage_annotator.analysis import roi_mask_from_points, roi_mean_timeseries, roi_stats


class RoiControlsMixin:
    """Mixin for ROI manager and ROI measurement handlers."""
    def _refresh_roi_manager(self) -> None:
        if self.roi_manager_widget is None:
            return
        rois = self.roi_manager.list_rois(self.primary_image.id)
        self.roi_manager_widget.set_rois(rois)
    def _roi_mgr_add(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Add ROI")
        layout = QtWidgets.QFormLayout(dlg)
        name_edit = QtWidgets.QLineEdit("ROI")
        type_combo = QtWidgets.QComboBox()
        type_combo.addItems(["box", "circle", "polygon"])
        layout.addRow("Name", name_edit)
        layout.addRow("Type", type_combo)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            if self.roi_shape == "none" or self.roi_rect[2] <= 0 or self.roi_rect[3] <= 0:
                self._set_status("Set an ROI first.")
                return
            roi_type = type_combo.currentText()
            roi_id = int(time.time() * 1000)
            if roi_type == "circle":
                x, y, w, h = self.roi_rect
                points = [(x + w / 2, y + h / 2), (x + w / 2 + min(w, h) / 2, y + h / 2)]
            elif roi_type == "polygon":
                x, y, w, h = self.roi_rect
                points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            else:
                x, y, w, h = self.roi_rect
                points = [(x, y), (x + w, y + h)]
            roi = Roi(roi_id=roi_id, name=name_edit.text(), roi_type=roi_type, points=points)
            self.roi_manager.add_roi(self.primary_image.id, roi)
            self.roi_manager.set_active(roi.roi_id)
            self._refresh_roi_manager()
            self._sync_active_roi(roi)
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()
    def _roi_mgr_delete(self) -> None:
        roi = self._roi_mgr_selected()
        if roi is None:
            return
        self.roi_manager.delete_roi(self.primary_image.id, roi.roi_id)
        self._refresh_roi_manager()
        self._refresh_image()
    def _roi_mgr_rename(self) -> None:
        roi = self._roi_mgr_selected()
        if roi is None:
            return
        text, ok = QtWidgets.QInputDialog.getText(self, "Rename ROI", "Name", text=roi.name)
        if ok and text:
            roi.name = text
            self._refresh_roi_manager()
    def _roi_mgr_duplicate(self) -> None:
        roi = self._roi_mgr_selected()
        if roi is None:
            return
        roi_id = int(time.time() * 1000)
        copy = Roi(roi_id=roi_id, name=f"{roi.name} Copy", roi_type=roi.roi_type, points=list(roi.points), color=roi.color)
        self.roi_manager.add_roi(self.primary_image.id, copy)
        self._refresh_roi_manager()
    def _roi_mgr_save(self) -> None:
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if not rois:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save ROIs", str(pathlib.Path.cwd() / "rois.json"), "ROI JSON (*.json)"
            )
        if not path:
            return
        save_rois_json(pathlib.Path(path), rois)
    def _roi_mgr_load(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load ROIs", str(pathlib.Path.cwd()), "ROI JSON (*.json)")
        if not path:
            return
        rois = load_rois_json(pathlib.Path(path))
        self.roi_manager.rois_by_image[self.primary_image.id] = rois
        if rois:
            self.roi_manager.set_active(rois[0].roi_id)
            self._sync_active_roi(rois[0])
            self._refresh_roi_manager()
            self._refresh_image()
    def _roi_mgr_measure(self) -> None:
        if self.primary_image.array is None:
            return
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if not rois:
            return
        arr = self.primary_image.array
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("ROI Mean Over Time")
        layout = QtWidgets.QVBoxLayout(dlg)
        table = QtWidgets.QTableWidget(arr.shape[0], len(rois) + 1)
        headers = ["Frame"] + [roi.name for roi in rois]
        table.setHorizontalHeaderLabels(headers)
        for t in range(arr.shape[0]):
            table.setItem(t, 0, QtWidgets.QTableWidgetItem(str(t)))
            for col, roi in enumerate(rois, start=1):
                mask = roi_mask_from_points(arr.shape[2:], roi.roi_type, roi.points)
                means = roi_mean_timeseries(arr, mask)
                for row, val in enumerate(means):
                    table.setItem(row, col, QtWidgets.QTableWidgetItem(f"{val:.4f}"))
                    table.resizeColumnsToContents()
                    layout.addWidget(table)
                    dlg.resize(700, 400)
                    dlg.exec()
    def _roi_mgr_selection_changed(self) -> None:
        roi = self._roi_mgr_selected()
        if roi is None:
            return
        self.roi_manager.set_active(roi.roi_id)
        self._sync_active_roi(roi)
        self._refresh_image()
    def _roi_mgr_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self.roi_manager_widget is None:
            return
        row = item.row()
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if row < 0 or row >= len(rois):
            return
        roi = rois[row]
        if item.column() == 0:
            roi.name = item.text()
        elif item.column() == 2:
            roi.color = item.text()
        elif item.column() == 3:
            roi.visible = item.checkState() == QtCore.Qt.CheckState.Checked
            self._refresh_image()
    def _roi_mgr_selected(self) -> Optional[Roi]:
        if self.roi_manager_widget is None:
            return None
        rows = {idx.row() for idx in self.roi_manager_widget.table.selectionModel().selectedRows()}
        if not rows:
            return None
        rois = self.roi_manager.list_rois(self.primary_image.id)
        row = min(rows)
        if 0 <= row < len(rois):
            return rois[row]
        return None
    def _sync_active_roi(self, roi: Roi) -> None:
        if roi.roi_type == "circle":
            (cx, cy), (px, py) = roi.points[:2]
            r = float(np.hypot(px - cx, py - cy))
            rect = (cx - r, cy - r, 2 * r, 2 * r)
            self.controller.set_roi(rect, shape="circle")
            self.roi_rect = rect
            self.roi_shape = "circle"
        elif roi.roi_type == "box":
            (x0, y0), (x1, y1) = roi.points[:2]
            rect = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            self.controller.set_roi(rect, shape="box")
            self.roi_rect = rect
            self.roi_shape = "box"
        else:
            # Fallback to bounding box for polygon types.
            xs = [p[0] for p in roi.points]
            ys = [p[1] for p in roi.points]
            rect = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            self.controller.set_roi(rect, shape="box")
            self.roi_rect = rect
            self.roi_shape = "box"
        self._sync_roi_controls()
