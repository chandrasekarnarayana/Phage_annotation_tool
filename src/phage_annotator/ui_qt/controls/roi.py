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


class RoiControlsMixin:
    """Mixin for ROI manager and ROI measurement handlers."""
    def _roi_measurement_frame(self, arr: np.ndarray, t: int) -> np.ndarray:
        """Resolve a 2D measurement frame from T/Y/X or T/Z/Y/X image data."""
        frame = np.asarray(arr[t])
        if frame.ndim == 2:
            return frame
        if frame.ndim == 3:
            return np.asarray(frame[0])
        raise ValueError(f"Unsupported ROI measurement shape: {arr.shape}")

    def _roi_measurement_rows(self, arr: np.ndarray, rois: list[Roi], image_id: int) -> list[dict]:
        """Build deterministic ROI measurement rows with traceable ROI/image context."""
        results: list[dict] = []
        n_frames = int(arr.shape[0])
        image_shape = "x".join(str(int(v)) for v in np.shape(arr))
        for t in range(n_frames):
            try:
                frame = self._roi_measurement_frame(arr, t)
            except Exception as e:
                logger.warning(f"Failed to resolve ROI measurement frame at t={t}: {e}")
                continue

            for roi in rois:
                try:
                    mask = roi_mask_from_points(frame.shape, roi.roi_type, roi.points)
                    vals = frame[mask]

                    if vals.size == 0:
                        continue

                    y_idx, x_idx = np.where(mask)
                    results.append({
                        "Image_ID": int(image_id),
                        "Image_Shape": image_shape,
                        "Frame_T": int(t),
                        "ROI_ID": int(roi.roi_id),
                        "ROI_Name": roi.name,
                        "ROI_Type": roi.roi_type,
                        "ROI_Tags": ",".join(str(tag) for tag in getattr(roi, "tags", []) if str(tag).strip()),
                        "ROI_Z_Binding": int(getattr(roi, "z_index", -1)),
                        "ROI_T_Binding": int(getattr(roi, "t_index", -1)),
                        "ROI_C_Binding": int(getattr(roi, "c_index", -1)),
                        "Area_px2": float(mask.sum()),
                        "Mean_Intensity": float(vals.mean()),
                        "Min_Intensity": float(vals.min()),
                        "Max_Intensity": float(vals.max()),
                        "Centroid_X_px": float(x_idx.mean()) if len(x_idx) > 0 else 0.0,
                        "Centroid_Y_px": float(y_idx.mean()) if len(y_idx) > 0 else 0.0,
                        "Integral_Sum": float(vals.sum()),
                    })
                except Exception as e:
                    logger.warning(f"Failed to measure ROI {roi.name} at frame {t}: {e}")
                    continue
        results.sort(key=lambda row: (int(row["Frame_T"]), str(row["ROI_Name"]), int(row["ROI_ID"])))
        return results

    def _roi_measurement_summary_text(self, rows: list[dict], roi_count: int, frame_count: int, image_id: int) -> str:
        """Summarize ROI measurement scope and aggregate output for the dialog header."""
        if not rows:
            return f"Image {image_id} | {roi_count} ROI(s) | {frame_count} frame(s) | 0 measurement row(s)"
        mean_area = sum(float(row["Area_px2"]) for row in rows) / float(len(rows))
        mean_signal = sum(float(row["Mean_Intensity"]) for row in rows) / float(len(rows))
        return (
            f"Image {image_id} | {roi_count} ROI(s) | {frame_count} frame(s) | "
            f"{len(rows)} measurement row(s) | Mean area {mean_area:.1f} px^2 | "
            f"Mean signal {mean_signal:.3f}"
        )

    def _roi_measurement_default_path(self) -> pathlib.Path:
        """Return a traceable default CSV export path for ROI measurements."""
        image_id = int(getattr(getattr(self, "primary_image", None), "id", -1))
        stamp = dt.datetime.now().strftime("%Y%m%d")
        return pathlib.Path.cwd() / f"roi_measurements_image_{image_id}_{stamp}.csv"

    def _write_roi_measurements_csv(self, path: pathlib.Path, rows: list[dict]) -> None:
        """Write ROI measurements with stable metadata-rich columns."""
        with open(path, "w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

    def _refresh_roi_manager(self) -> None:
        if self.roi_manager_widget is None:
            return
        rois = self.roi_manager.list_rois(self.primary_image.id)
        self.roi_manager_widget.set_rois(rois)
        selected = self._roi_mgr_selected()
        self._sync_roi_inline_editor(selected)

    def _roi_current_points(self, roi_type: str) -> list[tuple[float, float]]:
        """Translate the current editor ROI rect into ROI points for persistence."""
        if self.roi_shape == "none" or self.roi_rect[2] <= 0 or self.roi_rect[3] <= 0:
            raise ValueError("Set an ROI first.")
        x, y, w, h = self.roi_rect
        kind = str(roi_type or "box").strip().lower()
        if kind == "circle":
            return [(x + w / 2, y + h / 2), (x + w / 2 + min(w, h) / 2, y + h / 2)]
        if kind == "polygon":
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return [(x, y), (x + w, y + h)]

    def _sync_roi_inline_editor(self, roi: Optional[Roi]) -> None:
        """Keep inline ROI panel fields aligned with the current selection."""
        if getattr(self, "roi_measure_export_path_edit", None) is not None:
            try:
                if not self.roi_measure_export_path_edit.text().strip():
                    self.roi_measure_export_path_edit.setText(str(self._roi_measurement_default_path()))
            except Exception:
                pass
        if roi is None:
            if getattr(self, "roi_inline_name_edit", None) is not None and not self.roi_inline_name_edit.hasFocus():
                self.roi_inline_name_edit.setText("")
            if getattr(self, "roi_inline_tags_edit", None) is not None and not self.roi_inline_tags_edit.hasFocus():
                self.roi_inline_tags_edit.setText("")
            return
        if getattr(self, "roi_inline_name_edit", None) is not None and not self.roi_inline_name_edit.hasFocus():
            self.roi_inline_name_edit.setText(str(getattr(roi, "name", "")))
        if getattr(self, "roi_inline_type_combo", None) is not None and not self.roi_inline_type_combo.hasFocus():
            idx = self.roi_inline_type_combo.findText(str(getattr(roi, "roi_type", "box")))
            if idx >= 0:
                self.roi_inline_type_combo.setCurrentIndex(idx)
        if getattr(self, "roi_inline_tags_edit", None) is not None and not self.roi_inline_tags_edit.hasFocus():
            self.roi_inline_tags_edit.setText(", ".join(str(tag) for tag in getattr(roi, "tags", []) if str(tag).strip()))

    def _roi_mgr_add_inline(self) -> None:
        """Add a saved ROI using the inline panel fields instead of a popup dialog."""
        roi_name = str(
            getattr(self, "roi_inline_name_edit", None).text()
            if getattr(self, "roi_inline_name_edit", None) is not None
            else ""
        ).strip() or "ROI"
        roi_type = str(
            getattr(self, "roi_inline_type_combo", None).currentText()
            if getattr(self, "roi_inline_type_combo", None) is not None
            else "box"
        ).strip().lower()
        try:
            points = self._roi_current_points(roi_type)
        except ValueError as exc:
            self._status_warning(str(exc), timeout_ms=2500, source="roi.add")
            return
        roi = Roi(
            roi_id=int(time.time() * 1000),
            name=roi_name,
            roi_type=roi_type,
            points=points,
        )
        cmd = AddRoiCommand(self.roi_manager, self.primary_image.id, roi)
        if self.roi_manager.execute_command(cmd):
            self.roi_manager.set_active(roi.roi_id)
            self._refresh_roi_manager()
            self._sync_active_roi(roi)
            self._status_success(
                f"Saved ROI '{roi_name}'.",
                timeout_ms=2500,
                source="roi.add",
            )
        else:
            self._status_error("Failed to add ROI.", timeout_ms=3500, source="roi.add")

    def _roi_mgr_rename_inline(self) -> None:
        """Rename the selected ROI from the inline panel field."""
        roi = self._roi_mgr_selected()
        if roi is None:
            self._status_info("Select an ROI to rename.", timeout_ms=2500, source="roi.rename")
            return
        new_name = str(
            getattr(self, "roi_inline_name_edit", None).text()
            if getattr(self, "roi_inline_name_edit", None) is not None
            else ""
        ).strip()
        if not new_name:
            self._status_warning("ROI name cannot be empty.", timeout_ms=2500, source="roi.rename")
            return
        if new_name == str(roi.name):
            return
        cmd = RenameRoiCommand(self.roi_manager, self.primary_image.id, roi.roi_id, new_name)
        if self.roi_manager.execute_command(cmd):
            self._refresh_roi_manager()
            self._status_success(
                f"Renamed ROI to '{new_name}'.",
                timeout_ms=2500,
                source="roi.rename",
            )
        else:
            self._status_error("Failed to rename ROI.", timeout_ms=3000, source="roi.rename")

    def _roi_mgr_apply_tags_inline(self) -> None:
        """Apply comma-separated tags from the inline panel to the selected ROI."""
        roi = self._roi_mgr_selected()
        if roi is None:
            self._status_info("Select an ROI to edit tags.", timeout_ms=2500, source="roi.tags")
            return
        raw = str(
            getattr(self, "roi_inline_tags_edit", None).text()
            if getattr(self, "roi_inline_tags_edit", None) is not None
            else ""
        )
        target_tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        current_tags = list(getattr(roi, "tags", []) or [])
        for tag in list(current_tags):
            if tag not in target_tags:
                cmd = RemoveTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
                self.roi_manager.execute_command(cmd)
        for tag in target_tags:
            if tag in current_tags:
                continue
            cmd = AddTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
            self.roi_manager.execute_command(cmd)
        self._refresh_roi_manager()
        self._status_success("Updated ROI tags.", timeout_ms=2500, source="roi.tags")

    def _roi_mgr_filter_by_tag_inline(self) -> None:
        """Filter the ROI list from the inline tag filter field."""
        if self.roi_manager_widget is None:
            return
        raw = str(
            getattr(self, "roi_inline_filter_edit", None).text()
            if getattr(self, "roi_inline_filter_edit", None) is not None
            else ""
        )
        tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        self.roi_manager_widget.set_tag_filter(tags)
        self._status_info(
            f"Showing ROIs with tags: {', '.join(tags) if tags else 'all'}.",
            timeout_ms=2500,
            source="roi.tags",
        )

    def _roi_mgr_clear_tag_filter_inline(self) -> None:
        """Clear any inline ROI tag filter and show the full list again."""
        if getattr(self, "roi_inline_filter_edit", None) is not None:
            self.roi_inline_filter_edit.clear()
        if self.roi_manager_widget is not None:
            self.roi_manager_widget.set_tag_filter([])
        self._status_info("Showing all ROIs.", timeout_ms=2000, source="roi.tags")

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
    def _roi_mgr_duplicate(self) -> None:
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
        roi = self._roi_mgr_selected()
        if roi is None:
            self._sync_roi_inline_editor(None)
            return
        self.roi_manager.set_active(roi.roi_id)
        self._sync_roi_inline_editor(roi)
        self._sync_active_roi(roi)
        self._request_ui_refresh("roi-controls")
    def _roi_mgr_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
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

    def _roi_mgr_show_all_toggled(self, checked: bool) -> None:
        """Toggle overlay of all ROIs on canvas (Fiji parity F-120)."""
        if not hasattr(self, '_roi_show_all_enabled'):
            self._roi_show_all_enabled = False
        self._roi_show_all_enabled = checked
        if getattr(self, "roi_show_all_chk", None) is not None and bool(self.roi_show_all_chk.isChecked()) != bool(checked):
            self.roi_show_all_chk.blockSignals(True)
            self.roi_show_all_chk.setChecked(bool(checked))
            self.roi_show_all_chk.blockSignals(False)
        if self.roi_manager_widget is not None and bool(self.roi_manager_widget.show_all_btn.isChecked()) != bool(checked):
            self.roi_manager_widget.show_all_btn.blockSignals(True)
            self.roi_manager_widget.show_all_btn.setChecked(bool(checked))
            self.roi_manager_widget.show_all_btn.blockSignals(False)
        logger.info(f"Show All ROIs: {'ON' if checked else 'OFF'}")
        self._request_ui_refresh("roi-controls")

    def _roi_mgr_show_current_slice_only_toggled(self, checked: bool) -> None:
        """Toggle filtering ROIs to show only current z/t/c slice."""
        if not hasattr(self, '_roi_show_current_slice_only'):
            self._roi_show_current_slice_only = False
        self._roi_show_current_slice_only = checked
        if getattr(self, "roi_show_current_slice_only_chk", None) is not None and bool(self.roi_show_current_slice_only_chk.isChecked()) != bool(checked):
            self.roi_show_current_slice_only_chk.blockSignals(True)
            self.roi_show_current_slice_only_chk.setChecked(bool(checked))
            self.roi_show_current_slice_only_chk.blockSignals(False)
        if (
            self.roi_manager_widget is not None
            and bool(self.roi_manager_widget.show_current_slice_only_btn.isChecked()) != bool(checked)
        ):
            self.roi_manager_widget.show_current_slice_only_btn.blockSignals(True)
            self.roi_manager_widget.show_current_slice_only_btn.setChecked(bool(checked))
            self.roi_manager_widget.show_current_slice_only_btn.blockSignals(False)
        
        # Get current slice indices from view_state
        current_z = getattr(self.controller.view_state, 'z', 0)
        current_t = getattr(self.controller.view_state, 't', 0)
        current_c = getattr(self.controller.view_state, 'c', 0)
        
        logger.info(f"Show Current Slice Only: {'ON' if checked else 'OFF'} (z={current_z}, t={current_t}, c={current_c})")
        self._request_ui_refresh("roi-controls")

    def _roi_mgr_batch_bind_to_slice(self) -> None:
        """Bind all selected ROIs to current z/t/c slice."""
        # Get all selected ROIs
        selected_rois = self.roi_manager_widget.get_selected_rois() if hasattr(self.roi_manager_widget, 'get_selected_rois') else []
        
        if not selected_rois:
            logger.warning("Bind to slice: no ROIs selected")
            self._status_info(
                "Select ROIs to bind to current slice.",
                timeout_ms=2500,
                source="roi.bind_slice",
            )
            return
        
        # Get current slice indices
        current_z = getattr(self.controller.view_state, 'z', 0)
        current_t = getattr(self.controller.view_state, 't', 0)
        current_c = getattr(self.controller.view_state, 'c', 0)
        
        # Bind each selected ROI
        bind_count = 0
        for roi in selected_rois:
            if self.roi_manager.set_roi_position(roi.roi_id, z=current_z, t=current_t, c=current_c):
                bind_count += 1
        
        logger.info(f"Batch bind to slice: {bind_count} ROI(s) bound to z={current_z}, t={current_t}, c={current_c}")
        self._status_success(
            f"Bound {bind_count} ROI(s) to slice z={current_z}, t={current_t}, c={current_c}.",
            timeout_ms=3000,
            source="roi.bind_slice",
        )
        self._refresh_roi_manager()

    def _roi_mgr_batch_color_change(self) -> None:
        """Change color for all selected ROIs."""
        # Get all selected ROIs
        selected_rois = self.roi_manager_widget.get_selected_rois() if hasattr(self.roi_manager_widget, 'get_selected_rois') else []
        
        if not selected_rois:
            logger.warning("Batch color change: no ROIs selected")
            self._status_info(
                "Select ROIs to change color.",
                timeout_ms=2500,
                source="roi.color",
            )
            return
        
        # Color picker dialog
        from matplotlib.backends.qt_compat import QtGui
        color = QtWidgets.QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        
        color_hex = color.name()
        
        # Apply color to all selected ROIs
        for roi in selected_rois:
            roi.color = color_hex
        
        logger.info(f"Batch color change: {len(selected_rois)} ROI(s) changed to {color_hex}")
        self._status_success(
            f"Changed color for {len(selected_rois)} ROI(s).",
            timeout_ms=3000,
            source="roi.color",
        )
        self._refresh_roi_manager()
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

    def _roi_mgr_manage_tags(self) -> None:
        """Open tag management dialog for selected ROI."""
        roi = self._roi_mgr_selected()
        if roi is None:
            logger.warning("Manage tags: no ROI selected")
            self._status_info(
                "Select an ROI to manage tags.",
                timeout_ms=2500,
                source="roi.tags",
            )
            return
        
        # Get all available tags
        all_tags = self.roi_manager.get_all_tags(self.primary_image.id)
        
        # Create dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Manage Tags for '{roi.name}'")
        dlg.setMinimumWidth(400)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Label
        layout.addWidget(QtWidgets.QLabel(f"Current tags: {', '.join(roi.tags) if roi.tags else 'none'}"))
        
        # Tag input
        layout.addWidget(QtWidgets.QLabel("Add tag:"))
        tag_input = QtWidgets.QLineEdit()
        tag_input.setPlaceholderText("Enter new tag name")
        layout.addWidget(tag_input)
        
        # Add button
        add_btn = QtWidgets.QPushButton("Add Tag")
        layout.addWidget(add_btn)
        
        # Existing tags list
        layout.addWidget(QtWidgets.QLabel("Remove tag:"))
        tag_list = QtWidgets.QListWidget()
        tag_list.addItems(roi.tags)
        layout.addWidget(tag_list)
        
        # Remove button
        remove_btn = QtWidgets.QPushButton("Remove Selected Tag")
        layout.addWidget(remove_btn)
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        layout.addWidget(close_btn)
        
        def _add_tag():
            tag = tag_input.text().strip()
            if not tag:
                self._status_warning(
                    "Tag name cannot be empty.",
                    timeout_ms=2500,
                    source="roi.tags",
                )
                return
            if tag in roi.tags:
                self._status_info(
                    f"Tag '{tag}' already exists.",
                    timeout_ms=2500,
                    source="roi.tags",
                )
                return
            
            cmd = AddTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
            if self.roi_manager.execute_command(cmd):
                roi.tags.append(tag)
                tag_list.addItem(tag)
                tag_input.clear()
                logger.info(f"Added tag '{tag}' to ROI '{roi.name}'")
                layout.itemAt(0).widget().setText(f"Current tags: {', '.join(roi.tags)}")
            else:
                self._status_error(
                    f"Failed to add tag '{tag}'.",
                    timeout_ms=3000,
                    source="roi.tags",
                )
        
        def _remove_tag():
            items = tag_list.selectedItems()
            if not items:
                self._status_info(
                    "Select a tag to remove.",
                    timeout_ms=2500,
                    source="roi.tags",
                )
                return
            
            tag = items[0].text()
            cmd = RemoveTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
            if self.roi_manager.execute_command(cmd):
                roi.tags.remove(tag)
                tag_list.takeItem(tag_list.row(items[0]))
                logger.info(f"Removed tag '{tag}' from ROI '{roi.name}'")
                layout.itemAt(0).widget().setText(f"Current tags: {', '.join(roi.tags)}")
            else:
                self._status_error(
                    f"Failed to remove tag '{tag}'.",
                    timeout_ms=3000,
                    source="roi.tags",
                )
        
        add_btn.clicked.connect(_add_tag)
        remove_btn.clicked.connect(_remove_tag)
        close_btn.clicked.connect(dlg.accept)
        
        dlg.exec()
        self._refresh_roi_manager()

    def _roi_mgr_filter_by_tag(self) -> None:
        """Filter ROIs by tag."""
        all_tags = self.roi_manager.get_all_tags(self.primary_image.id)
        if not all_tags:
            self._status_info(
                "No tags available.",
                timeout_ms=2500,
                source="roi.tags",
            )
            return
        
        # Create filter dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Filter ROIs by Tag")
        dlg.setMinimumWidth(300)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        layout.addWidget(QtWidgets.QLabel("Select tags to show (empty = show all):"))
        
        # Checkbox list of tags
        checkboxes = {}
        for tag in all_tags:
            checkbox = QtWidgets.QCheckBox(tag)
            checkboxes[tag] = checkbox
            layout.addWidget(checkbox)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("Apply")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        def _apply_filter():
            selected_tags = [tag for tag, checkbox in checkboxes.items() if checkbox.isChecked()]
            # Store filter in widget for display
            if hasattr(self.roi_manager_widget, 'set_tag_filter'):
                self.roi_manager_widget.set_tag_filter(selected_tags)
            logger.info(f"Filter ROIs by tags: {selected_tags if selected_tags else 'none (show all)'}")
            self._status_info(
                f"Showing ROIs with tags: {', '.join(selected_tags) if selected_tags else 'all'}.",
                timeout_ms=3000,
                source="roi.tags",
            )
            dlg.accept()
        
        ok_btn.clicked.connect(_apply_filter)
        cancel_btn.clicked.connect(dlg.reject)
        
        dlg.exec()

    def _roi_mgr_selected(self) -> Optional[Roi]:
        if self.roi_manager_widget is None:
            return None
        selected = self.roi_manager_widget.get_selected_rois() if hasattr(self.roi_manager_widget, "get_selected_rois") else []
        if selected:
            return selected[0]
        rows = {idx.row() for idx in self.roi_manager_widget.table.selectionModel().selectedRows()}
        if not rows:
            return None
        rois = list(getattr(self.roi_manager_widget, "_current_rois", []) or [])
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
        self._sync_roi_inline_editor(roi)
        self._request_ui_refresh("roi-controls")
