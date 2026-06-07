"""Extracted method group 2 for RoiControlsMixin."""

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



class RoiControlsStyleMixin:
    """Method group 2 extracted from RoiControlsMixin."""

    def _roi_mgr_measure_inline(self) -> None:
        """Measure ROIs and render the results directly in the embedded ROI panel."""
        if self.primary_image.array is None:
            self._status_warning("Load an image before measuring.", timeout_ms=2500, source="roi.measure")
            return
        rois = self.roi_manager.list_rois(self.primary_image.id)
        if not rois:
            self._status_warning("Add ROIs before measuring.", timeout_ms=2500, source="roi.measure")
            return
        rows = self._roi_measurement_rows(self.primary_image.array, rois, int(self.primary_image.id))
        self._last_roi_measurements = rows
        if getattr(self, "roi_measure_summary_lbl", None) is not None:
            self.roi_measure_summary_lbl.setText(
                self._roi_measurement_summary_text(
                    rows,
                    len(rois),
                    int(self.primary_image.array.shape[0]),
                    int(self.primary_image.id),
                )
            )
        table = getattr(self, "roi_measure_table", None)
        if table is not None:
            headers = list(rows[0].keys()) if rows else []
            table.clear()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(rows))
            for ridx, row in enumerate(rows):
                for cidx, key in enumerate(headers):
                    value = row[key]
                    text = f"{value:.4f}" if isinstance(value, float) else str(value)
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    table.setItem(ridx, cidx, item)
            table.resizeColumnsToContents()
        self._status_success(
            f"Measured {len(rows)} ROI-frame rows.",
            timeout_ms=2500,
            source="roi.measure",
        )
    def _roi_mgr_export_measurements_inline(self) -> None:
        """Export the latest inline ROI measurement results to CSV."""
        rows = list(getattr(self, "_last_roi_measurements", []) or [])
        if not rows:
            self._status_info(
                "Run ROI measurement first.",
                timeout_ms=2500,
                source="roi.measure",
            )
            return
        path_text = str(
            getattr(self, "roi_measure_export_path_edit", None).text()
            if getattr(self, "roi_measure_export_path_edit", None) is not None
            else ""
        ).strip()
        path = pathlib.Path(path_text) if path_text else self._roi_measurement_default_path()
        try:
            self._write_roi_measurements_csv(path, rows)
            if getattr(self, "roi_measure_export_path_edit", None) is not None:
                self.roi_measure_export_path_edit.setText(str(path))
            self._status_success(
                f"Exported ROI measurements to {path}.",
                timeout_ms=3000,
                source="roi.measure",
            )
        except Exception as exc:
            logger.error(f"Failed to export inline ROI measurements: {exc}")
            self._status_error(
                f"Failed to export ROI measurements: {exc}",
                timeout_ms=3500,
                source="roi.measure",
            )
    def _roi_mgr_add(self) -> None:
        """Handle the roi mgr add helper flow."""
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
            """Apply apply for the current workflow."""
            if self.roi_shape == "none" or self.roi_rect[2] <= 0 or self.roi_rect[3] <= 0:
                self._status_warning(
                    "Set an ROI first.",
                    timeout_ms=2500,
                    source="roi.add",
                )
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
            
            # Use undoable command
            cmd = AddRoiCommand(self.roi_manager, self.primary_image.id, roi)
            if self.roi_manager.execute_command(cmd):
                self.roi_manager.set_active(roi.roi_id)
                self._refresh_roi_manager()
                self._sync_active_roi(roi)
                dlg.accept()
            else:
                self._status_error(
                    "Failed to add ROI.",
                    timeout_ms=3500,
                    source="roi.add",
                )

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()
    def _roi_mgr_delete(self) -> None:
        """Delete selected ROI(s) - supports multi-select."""
        # Get all selected ROIs (multi-select support)
        selected_rois = self.roi_manager_widget.get_selected_rois() if hasattr(self.roi_manager_widget, 'get_selected_rois') else []
        
        if not selected_rois:
            # Fallback to single selection
            roi = self._roi_mgr_selected()
            if roi is None:
                logger.warning("Delete requested but no ROI selected")
                return
            selected_rois = [roi]
        
        # Use undoable command
        if len(selected_rois) == 1:
            cmd = DeleteRoiCommand(self.roi_manager, self.primary_image.id, selected_rois[0].roi_id)
        else:
            roi_ids = [roi.roi_id for roi in selected_rois]
            cmd = BatchDeleteRoisCommand(self.roi_manager, self.primary_image.id, roi_ids)
        
        if self.roi_manager.execute_command(cmd):
            logger.info(f"Deleted {len(selected_rois)} ROI(s) with undo support")
        else:
            logger.error(f"Failed to delete ROI(s)")
        self._refresh_roi_manager()
        self._request_ui_refresh("roi-controls")
    def _roi_mgr_deselect(self) -> None:
        """Deselect active ROI without deleting it (Fiji parity F-118)."""
        if self.roi_manager.active_roi_id is None:
            logger.debug("Deselect: no active ROI")
            return
        self.roi_manager.set_active(None)
        if self.roi_manager_widget:
            self.roi_manager_widget.table.clearSelection()
        logger.info(f"ROI deselected (id was {self.roi_manager.active_roi_id})")
        self._request_ui_refresh("roi-controls")
    def _roi_mgr_update(self) -> None:
        """Update selected ROI geometry from editor, preserving identity (Fiji parity F-119)."""
        roi = self._roi_mgr_selected()
        if roi is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", 
                "Select an ROI to update.\n\nUpdate replaces the geometry of the selected ROI with the current editor state."
            )
            logger.warning("Update requested but no ROI selected")
            return
        
        # Get current editor state
        current_rect = self.controller.view_state.roi_spec.rect
        current_shape = self.controller.view_state.roi_spec.shape
        
        if current_shape == "none":
            QtWidgets.QMessageBox.warning(
                self, "No Editor Selection",
                "Draw or select an ROI in the editor first."
            )
            logger.warning(f"Update failed: no active editor selection")
            return
        
        # Replace geometry, keep identity
        if current_shape == "circle":
            x, y, w, h = current_rect
            new_points = [(x + w / 2, y + h / 2), (x + w / 2 + min(w, h) / 2, y + h / 2)]
        elif current_shape == "box":
            x, y, w, h = current_rect
            new_points = [(x, y), (x + w, y + h)]
        else:
            new_points = [(current_rect[0], current_rect[1]), (current_rect[0] + current_rect[2], current_rect[1] + current_rect[3])]
        
        # Use undoable command
        cmd = UpdateRoiGeometryCommand(
            self.roi_manager, 
            self.primary_image.id, 
            roi.roi_id, 
            new_points, 
            current_shape
        )
        if self.roi_manager.execute_command(cmd):
            logger.info(f"ROI updated: id={roi.roi_id}, name={roi.name}, type={current_shape}, rect={current_rect}")
            self._refresh_roi_manager()
        else:
            logger.error(f"Failed to update ROI geometry")
    def _roi_mgr_rename(self) -> None:
        """Handle the roi mgr rename helper flow."""
        roi = self._roi_mgr_selected()
        if roi is None:
            logger.warning("Rename requested but no ROI selected")
            return
        old_name = roi.name
        text, ok = QtWidgets.QInputDialog.getText(self, "Rename ROI", "Name", text=roi.name)
        if ok and text and text != old_name:
            # Use undoable command
            cmd = RenameRoiCommand(self.roi_manager, self.primary_image.id, roi.roi_id, text)
            if self.roi_manager.execute_command(cmd):
                logger.info(f"ROI renamed: id={roi.roi_id}, {old_name} → {text}")
                self._refresh_roi_manager()
            else:
                logger.error(f"Failed to rename ROI")
