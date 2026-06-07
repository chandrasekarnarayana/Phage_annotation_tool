"""ROI manager and ROI measurement handlers with Fiji-parity support."""

from __future__ import annotations

import csv
import datetime as dt
import logging
import pathlib
import time
from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.roi.manager import Roi, save_rois_json, load_rois_json
from phage_annotator.roi.commands import (
    AddRoiCommand,
    DeleteRoiCommand,
    RenameRoiCommand,
    UpdateRoiGeometryCommand,
    BatchDeleteRoisCommand,
    AddTagCommand,
    RemoveTagCommand,
)
from phage_annotator.analysis.core import roi_mask_from_points, roi_mean_timeseries

logger = logging.getLogger(__name__)

class RoiControlsIOMixin:
    """ROI manager file IO, measurement, selection, and undo/redo."""

    def _roi_mgr_duplicate(self) -> None:
        """Document the roi_mgr_duplicate flow."""
        roi = self._roi_mgr_selected()
        if roi is None:
            logger.warning("Duplicate requested but no ROI selected")
            return
        roi_id = int(time.time() * 1000)
        copy = Roi(
            roi_id=roi_id,
            name=f"{roi.name} Copy",
            roi_type=roi.roi_type,
            points=list(roi.points),
            color=roi.color,
            visible=roi.visible
        )
        self.roi_manager.add_roi(self.primary_image.id, copy)
        logger.info(f"ROI duplicated: id={roi.roi_id} → {roi_id}, name={copy.name}")
        self._refresh_roi_manager()

    def _roi_mgr_save(self) -> None:
        """Document the roi_mgr_save flow."""
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if not rois:
            QtWidgets.QMessageBox.information(self, "No ROIs", "No ROIs to save.")
            logger.info("Save requested but no ROIs present")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save ROIs", str(pathlib.Path.cwd() / "rois.json"), "ROI JSON (*.json)"
        )
        if not path:
            logger.debug("Save cancelled by user")
            return
        try:
            save_rois_json(pathlib.Path(path), rois)
            QtWidgets.QMessageBox.information(self, "Success", f"Saved {len(rois)} ROIs to:\n{path}")
        except Exception as e:
            logger.error(f"Failed to save ROIs: {e}")
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")

    def _roi_mgr_load(self) -> None:
        """Document the roi_mgr_load flow."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load ROIs", str(pathlib.Path.cwd()), "ROI JSON (*.json)"
        )
        if not path:
            logger.debug("Load cancelled by user")
            return
        try:
            rois = load_rois_json(pathlib.Path(path))
            self.roi_manager.rois_by_image[self.primary_image.id] = rois
            if rois:
                self.roi_manager.set_active(rois[0].roi_id)
                self._sync_active_roi(rois[0])
            self._refresh_roi_manager()
            self._request_ui_refresh("roi-controls")
            QtWidgets.QMessageBox.information(self, "Success", f"Loaded {len(rois)} ROIs from:\n{path}")
            logger.info(f"Loaded {len(rois)} ROIs from {path}")
        except Exception as e:
            logger.error(f"Failed to load ROIs: {e}")
            QtWidgets.QMessageBox.critical(self, "Load Error", f"Failed to load:\n{e}")

    def _roi_mgr_measure(self) -> None:
        """Measure ROI metrics over time (standard columns: Area, Mean, Min, Max, Centroid XY, IntSum)."""
        if self.primary_image.array is None:
            logger.warning("Measure requested but no image loaded")
            return
        
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if not rois:
            QtWidgets.QMessageBox.warning(self, "No ROIs", "Add ROIs before measuring.")
            logger.warning("Measure requested but no ROIs present")
            return
        
        arr = self.primary_image.array
        n_frames = int(arr.shape[0])
        logger.info(f"Measuring {len(rois)} ROIs over {n_frames} frames...")
        results = self._roi_measurement_rows(arr, rois, int(self.primary_image.id))
        
        logger.info(f"Measured {len(results)} ROI-frame combinations")
        
        # Display results table with CSV export option
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"ROI Measurements ({len(results)} rows)")
        dlg.resize(1000, 600)
        layout = QtWidgets.QVBoxLayout(dlg)
        summary = QtWidgets.QLabel(self._roi_measurement_summary_text(results, len(rois), n_frames, int(self.primary_image.id)))
        layout.addWidget(summary)
        
        # Results table
        table = QtWidgets.QTableWidget(len(results), len(results[0]) if results else 0)
        if results:
            headers = list(results[0].keys())
            table.setHorizontalHeaderLabels(headers)
            for row, data in enumerate(results):
                for col, key in enumerate(headers):
                    item = QtWidgets.QTableWidgetItem(f"{data[key]:.4f}" if isinstance(data[key], float) else str(data[key]))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Read-only
                    table.setItem(row, col, item)
            table.setSortingEnabled(True)
            table.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)
            table.resizeColumnsToContents()
        
        layout.addWidget(table)
        
        # Button row: CSV export
        btn_row = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QPushButton("Export CSV")
        close_btn = QtWidgets.QPushButton("Close")
        
        def _export_csv():
            """Document the export_csv flow."""
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg, "Export Results", str(self._roi_measurement_default_path()), "CSV (*.csv)"
            )
            if path:
                try:
                    self._write_roi_measurements_csv(pathlib.Path(path), results)
                    QtWidgets.QMessageBox.information(dlg, "Success", f"Exported {len(results)} rows to:\n{path}")
                    logger.info(f"ROI measurements exported to {path}")
                except Exception as e:
                    logger.error(f"Failed to export CSV: {e}")
                    QtWidgets.QMessageBox.critical(dlg, "Export Error", f"Failed:\n{e}")
        
        export_btn.clicked.connect(_export_csv)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        
        dlg.exec()

    def _roi_mgr_selection_changed(self) -> None:
        """Document the roi_mgr_selection_changed flow."""
        roi = self._roi_mgr_selected()
        if roi is None:
            self._sync_roi_inline_editor(None)
            return
        self.roi_manager.set_active(roi.roi_id)
        self._sync_roi_inline_editor(roi)
        self._sync_active_roi(roi)
        self._request_ui_refresh("roi-controls")

    def _roi_mgr_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        """Document the roi_mgr_item_changed flow."""
        if self.roi_manager_widget is None:
            return
        row = item.row()
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if row < 0 or row >= len(rois):
            return
        roi = rois[row]
        if item.column() == 0:  # Name
            roi.name = item.text()
            logger.debug(f"ROI {roi.roi_id} name changed to: {roi.name}")
        elif item.column() == 2:  # Z position
            text = item.text().strip().lower()
            roi.z_index = -1 if text == "all" else int(text) if text.isdigit() else roi.z_index
            logger.debug(f"ROI {roi.roi_id} z_index changed to: {roi.z_index}")
        elif item.column() == 3:  # T position
            text = item.text().strip().lower()
            roi.t_index = -1 if text == "all" else int(text) if text.isdigit() else roi.t_index
            logger.debug(f"ROI {roi.roi_id} t_index changed to: {roi.t_index}")
        elif item.column() == 4:  # C position
            text = item.text().strip().lower()
            roi.c_index = -1 if text == "all" else int(text) if text.isdigit() else roi.c_index
            logger.debug(f"ROI {roi.roi_id} c_index changed to: {roi.c_index}")
        elif item.column() == 5:  # Color
            roi.color = item.text()
            logger.debug(f"ROI {roi.roi_id} color changed to: {roi.color}")
        elif item.column() == 6:  # Visible
            roi.visible = item.checkState() == QtCore.Qt.CheckState.Checked
            logger.debug(f"ROI {roi.roi_id} visibility toggled: {roi.visible}")
            self._request_ui_refresh("roi-controls")

    def _copy_roi_diagnostics(self) -> None:
        """Copy ROI manager diagnostics to clipboard (for debugging)."""
        diag = f"""ROI Manager Diagnostics:
- Active ROI ID: {self.roi_manager.active_roi_id}
- Total ROIs: {sum(len(rois) for rois in self.roi_manager.rois_by_image.values())}
- Images with ROIs: {len(self.roi_manager.rois_by_image)}
- Templates saved: {len(self.roi_manager.roi_templates)}
- Primary image ID: {self.primary_image.id if self.primary_image else 'None'}
- Primary image shape: {self.primary_image.array.shape if self.primary_image and self.primary_image.array is not None else 'None'}
"""
        QtWidgets.QApplication.clipboard().setText(diag)
        QtWidgets.QMessageBox.information(self, "Copied", "Diagnostics copied to clipboard")
        logger.debug(f"ROI diagnostics copied:\n{diag}")

    def _roi_mgr_undo(self) -> None:
        """Undo last ROI operation."""
        if not self.roi_manager.can_undo():
            logger.debug("Undo: no operations to undo")
            self._status_info("Nothing to undo.", timeout_ms=2000, source="roi.undo")
            return
        
        if self.roi_manager.undo():
            logger.info("ROI operation undone")
            self._status_success("Undone.", timeout_ms=2000, source="roi.undo")
            self._refresh_roi_manager()
            self._request_ui_refresh("roi-controls")
        else:
            logger.error("Failed to undo ROI operation")
            self._status_error("Undo failed.", timeout_ms=3000, source="roi.undo")

    def _roi_mgr_redo(self) -> None:
        """Redo last undone ROI operation."""
        if not self.roi_manager.can_redo():
            logger.debug("Redo: no operations to redo")
            self._status_info("Nothing to redo.", timeout_ms=2000, source="roi.redo")
            return
        
        if self.roi_manager.redo():
            logger.info("ROI operation redone")
            self._status_success("Redone.", timeout_ms=2000, source="roi.redo")
            self._refresh_roi_manager()
            self._request_ui_refresh("roi-controls")
        else:
            logger.error("Failed to redo ROI operation")
            self._status_error("Redo failed.", timeout_ms=3000, source="roi.redo")
