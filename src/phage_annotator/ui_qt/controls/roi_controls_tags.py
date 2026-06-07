"""Extracted method group 5 for RoiControlsMixin."""

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



class RoiControlsTagsMixin:
    """Method group 5 extracted from RoiControlsMixin."""

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
            """Apply filter for the current workflow."""
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
        """Handle the roi mgr selected helper flow."""
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
        """Synchronize active roi for the current workflow."""
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
