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

class RoiControlsBatchMixin:
    """ROI batch visibility, color, slice-binding, and tag management."""

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
            """Document the add_tag flow."""
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
            """Document the remove_tag flow."""
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
