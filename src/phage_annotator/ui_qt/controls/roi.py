"""ROI manager and ROI measurement handlers with Fiji-parity support."""

from __future__ import annotations

import csv
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
            
            # Use undoable command
            cmd = AddRoiCommand(self.roi_manager, self.primary_image.id, roi)
            if self.roi_manager.execute_command(cmd):
                self.roi_manager.set_active(roi.roi_id)
                self._refresh_roi_manager()
                self._sync_active_roi(roi)
                dlg.accept()
            else:
                self._set_status("Failed to add ROI")

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
        self._refresh_image()

    def _roi_mgr_deselect(self) -> None:
        """Deselect active ROI without deleting it (Fiji parity F-118)."""
        if self.roi_manager.active_roi_id is None:
            logger.debug("Deselect: no active ROI")
            return
        self.roi_manager.set_active(None)
        if self.roi_manager_widget:
            self.roi_manager_widget.table.clearSelection()
        logger.info(f"ROI deselected (id was {self.roi_manager.active_roi_id})")
        self._refresh_image()

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
            self._refresh_image()
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
        n_frames = arr.shape[0]
        
        # Build results table
        results = []
        logger.info(f"Measuring {len(rois)} ROIs over {n_frames} frames...")
        
        for t in range(n_frames):
            frame = arr[t, 0, :, :]  # Assume (T, Z, Y, X)
            
            for roi in rois:
                try:
                    mask = roi_mask_from_points(frame.shape, roi.roi_type, roi.points)
                    vals = frame[mask]
                    
                    if vals.size == 0:
                        continue
                    
                    # Standard metrics (Fiji-compatible)
                    area_px2 = float(mask.sum())
                    mean_px = float(vals.mean())
                    min_px = float(vals.min())
                    max_px = float(vals.max())
                    int_sum = float(vals.sum())
                    
                    # Centroid
                    y_idx, x_idx = np.where(mask)
                    cx = float(x_idx.mean()) if len(x_idx) > 0 else 0.0
                    cy = float(y_idx.mean()) if len(y_idx) > 0 else 0.0
                    
                    results.append({
                        "Frame": t,
                        "ROI_Name": roi.name,
                        "ROI_Type": roi.roi_type,
                        "Area_px2": area_px2,
                        "Mean": mean_px,
                        "Min": min_px,
                        "Max": max_px,
                        "Centroid_X": cx,
                        "Centroid_Y": cy,
                        "IntegralSum": int_sum,
                    })
                except Exception as e:
                    logger.warning(f"Failed to measure ROI {roi.name} at frame {t}: {e}")
                    continue
        
        logger.info(f"Measured {len(results)} ROI-frame combinations")
        
        # Display results table with CSV export option
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"ROI Measurements ({len(results)} rows)")
        dlg.resize(1000, 600)
        layout = QtWidgets.QVBoxLayout(dlg)
        
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
            table.resizeColumnsToContents()
        
        layout.addWidget(table)
        
        # Button row: CSV export
        btn_row = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QPushButton("Export CSV")
        close_btn = QtWidgets.QPushButton("Close")
        
        def _export_csv():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg, "Export Results", str(pathlib.Path.cwd() / "roi_measurements.csv"), "CSV (*.csv)"
            )
            if path:
                try:
                    with open(path, "w", newline="") as f:
                        if results:
                            writer = csv.DictWriter(f, fieldnames=results[0].keys())
                            writer.writeheader()
                            writer.writerows(results)
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
            self._refresh_image()

    def _roi_mgr_show_all_toggled(self, checked: bool) -> None:
        """Toggle overlay of all ROIs on canvas (Fiji parity F-120)."""
        if not hasattr(self, '_roi_show_all_enabled'):
            self._roi_show_all_enabled = False
        self._roi_show_all_enabled = checked
        logger.info(f"Show All ROIs: {'ON' if checked else 'OFF'}")
        self._refresh_image()

    def _roi_mgr_show_current_slice_only_toggled(self, checked: bool) -> None:
        """Toggle filtering ROIs to show only current z/t/c slice."""
        if not hasattr(self, '_roi_show_current_slice_only'):
            self._roi_show_current_slice_only = False
        self._roi_show_current_slice_only = checked
        
        # Get current slice indices from view_state
        current_z = getattr(self.controller.view_state, 'z', 0)
        current_t = getattr(self.controller.view_state, 't', 0)
        current_c = getattr(self.controller.view_state, 'c', 0)
        
        logger.info(f"Show Current Slice Only: {'ON' if checked else 'OFF'} (z={current_z}, t={current_t}, c={current_c})")
        self._refresh_image()

    def _roi_mgr_batch_bind_to_slice(self) -> None:
        """Bind all selected ROIs to current z/t/c slice."""
        # Get all selected ROIs
        selected_rois = self.roi_manager_widget.get_selected_rois() if hasattr(self.roi_manager_widget, 'get_selected_rois') else []
        
        if not selected_rois:
            logger.warning("Bind to slice: no ROIs selected")
            self._set_status("Select ROIs to bind to current slice")
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
        self._set_status(f"Bound {bind_count} ROI(s) to slice z={current_z}, t={current_t}, c={current_c}")
        self._refresh_roi_manager()

    def _roi_mgr_batch_color_change(self) -> None:
        """Change color for all selected ROIs."""
        # Get all selected ROIs
        selected_rois = self.roi_manager_widget.get_selected_rois() if hasattr(self.roi_manager_widget, 'get_selected_rois') else []
        
        if not selected_rois:
            logger.warning("Batch color change: no ROIs selected")
            self._set_status("Select ROIs to change color")
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
        self._set_status(f"Changed color for {len(selected_rois)} ROI(s)")
        self._refresh_roi_manager()
        self._refresh_image()

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
            self._set_status("Nothing to undo")
            return
        
        if self.roi_manager.undo():
            logger.info("ROI operation undone")
            self._set_status("Undone")
            self._refresh_roi_manager()
            self._refresh_image()
        else:
            logger.error("Failed to undo ROI operation")
            self._set_status("Undo failed")

    def _roi_mgr_redo(self) -> None:
        """Redo last undone ROI operation."""
        if not self.roi_manager.can_redo():
            logger.debug("Redo: no operations to redo")
            self._set_status("Nothing to redo")
            return
        
        if self.roi_manager.redo():
            logger.info("ROI operation redone")
            self._set_status("Redone")
            self._refresh_roi_manager()
            self._refresh_image()
        else:
            logger.error("Failed to redo ROI operation")
            self._set_status("Redo failed")

    def _roi_mgr_manage_tags(self) -> None:
        """Open tag management dialog for selected ROI."""
        roi = self._roi_mgr_selected()
        if roi is None:
            logger.warning("Manage tags: no ROI selected")
            self._set_status("Select an ROI to manage tags")
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
                self._set_status("Tag name cannot be empty")
                return
            if tag in roi.tags:
                self._set_status(f"Tag '{tag}' already exists")
                return
            
            cmd = AddTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
            if self.roi_manager.execute_command(cmd):
                roi.tags.append(tag)
                tag_list.addItem(tag)
                tag_input.clear()
                logger.info(f"Added tag '{tag}' to ROI '{roi.name}'")
                layout.itemAt(0).widget().setText(f"Current tags: {', '.join(roi.tags)}")
            else:
                self._set_status(f"Failed to add tag '{tag}'")
        
        def _remove_tag():
            items = tag_list.selectedItems()
            if not items:
                self._set_status("Select a tag to remove")
                return
            
            tag = items[0].text()
            cmd = RemoveTagCommand(self.roi_manager, self.primary_image.id, roi.roi_id, tag)
            if self.roi_manager.execute_command(cmd):
                roi.tags.remove(tag)
                tag_list.takeItem(tag_list.row(items[0]))
                logger.info(f"Removed tag '{tag}' from ROI '{roi.name}'")
                layout.itemAt(0).widget().setText(f"Current tags: {', '.join(roi.tags)}")
            else:
                self._set_status(f"Failed to remove tag '{tag}'")
        
        add_btn.clicked.connect(_add_tag)
        remove_btn.clicked.connect(_remove_tag)
        close_btn.clicked.connect(dlg.accept)
        
        dlg.exec()
        self._refresh_roi_manager()

    def _roi_mgr_filter_by_tag(self) -> None:
        """Filter ROIs by tag."""
        all_tags = self.roi_manager.get_all_tags(self.primary_image.id)
        if not all_tags:
            self._set_status("No tags available")
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
            self._set_status(f"Showing ROIs with tags: {', '.join(selected_tags) if selected_tags else 'all'}")
            dlg.accept()
        
        ok_btn.clicked.connect(_apply_filter)
        cancel_btn.clicked.connect(dlg.reject)
        
        dlg.exec()

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
