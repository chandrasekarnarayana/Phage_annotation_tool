"""ROI Manager dock UI with Fiji-like interactions."""

from __future__ import annotations

from typing import List

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.roi.manager import Roi, RoiManager


class RoiManagerWidget(QtWidgets.QWidget):
    """Dock widget for managing multiple ROIs with Fiji-parity controls."""

    # Signals for external handlers
    deselect_requested = QtCore.pyqtSignal()
    update_requested = QtCore.pyqtSignal()
    show_all_toggled = QtCore.pyqtSignal(bool)
    show_current_slice_only_toggled = QtCore.pyqtSignal(bool)  # position binding
    batch_delete_requested = QtCore.pyqtSignal(list)  # batch operations, emits list of roi_ids
    batch_color_requested = QtCore.pyqtSignal(list)  # batch color change, emits list of roi_ids
    batch_bind_to_slice_requested = QtCore.pyqtSignal(list)  # batch slice binding, emits list of roi_ids

    def __init__(self, manager: RoiManager, parent=None) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self.manager = manager
        self._current_rois: List[Roi] = []  # cache for multi-select support
        self._all_rois: List[Roi] = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ROI list table
        self.table = QtWidgets.QTableWidget(0, 7)  # Added z/t/c columns
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Z", "T", "C", "Color", "Visible"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)  # multi-select
        layout.addWidget(self.table)

        # first row of buttons
        btn_row1 = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add")
        self.add_btn.setToolTip("Add new ROI from current selection")
        self.del_btn = QtWidgets.QPushButton("Delete")
        self.del_btn.setToolTip("Delete selected ROI(s) - multi-select supported")
        self.deselect_btn = QtWidgets.QPushButton("Deselect")
        self.deselect_btn.setToolTip("Deselect ROI without deleting")
        self.rename_btn = QtWidgets.QPushButton("Rename")
        self.rename_btn.setToolTip("Rename selected ROI")
        for btn in [self.add_btn, self.del_btn, self.deselect_btn, self.rename_btn]:
            btn_row1.addWidget(btn)
        layout.addLayout(btn_row1)

        # second row of buttons
        btn_row2 = QtWidgets.QHBoxLayout()
        self.update_btn = QtWidgets.QPushButton("Update")
        self.update_btn.setToolTip("Update selected ROI geometry from editor")
        self.dup_btn = QtWidgets.QPushButton("Duplicate")
        self.dup_btn.setToolTip("Duplicate selected ROI")
        self.show_all_btn = QtWidgets.QPushButton("Show All")
        self.show_all_btn.setCheckable(True)
        self.show_all_btn.setToolTip("Toggle overlay of all ROIs on canvas")
        self.show_current_slice_only_btn = QtWidgets.QPushButton("Current Slice Only")
        self.show_current_slice_only_btn.setCheckable(True)
        self.show_current_slice_only_btn.setToolTip("Display only ROIs on current z/t/c slice")
        for btn in [self.update_btn, self.dup_btn, self.show_all_btn, self.show_current_slice_only_btn]:
            btn_row2.addWidget(btn)
        layout.addLayout(btn_row2)

        # third row of buttons (file I/O + measurement)
        btn_row3 = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save ROIs")
        self.save_btn.setToolTip("Export ROIs to JSON file")
        self.load_btn = QtWidgets.QPushButton("Load ROIs")
        self.load_btn.setToolTip("Import ROIs from JSON file")
        self.measure_btn = QtWidgets.QPushButton("Measure")
        self.measure_btn.setToolTip("Compute metrics for all ROIs over time")
        for btn in [self.save_btn, self.load_btn, self.measure_btn]:
            btn_row3.addWidget(btn)
        layout.addLayout(btn_row3)
        
        # fourth row of buttons (tags)
        btn_row4 = QtWidgets.QHBoxLayout()
        self.manage_tags_btn = QtWidgets.QPushButton("Manage Tags")
        self.manage_tags_btn.setToolTip("Add/remove tags for selected ROI")
        self.filter_by_tag_btn = QtWidgets.QPushButton("Filter by Tag")
        self.filter_by_tag_btn.setToolTip("Show only ROIs with selected tags")
        for btn in [self.manage_tags_btn, self.filter_by_tag_btn]:
            btn_row4.addWidget(btn)
        layout.addLayout(btn_row4)
        
        # Tag filter UI
        self._tag_filter: List[str] = []  # Currently active tag filter

    def set_rois(self, rois: List[Roi]) -> None:
        """Populate table with ROIs, preserving selection if possible."""
        self._all_rois = list(rois)
        display_rois = (
            [
                roi for roi in self._all_rois
                if any(tag in getattr(roi, "tags", []) for tag in self._tag_filter)
            ]
            if self._tag_filter
            else list(self._all_rois)
        )
        self._current_rois = display_rois
        self.table.blockSignals(True)
        self.table.setRowCount(len(display_rois))
        for row, roi in enumerate(display_rois):
            # Name
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(roi.name))
            # Type
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(roi.roi_type))
            # Z position (position display)
            z_text = "all" if roi.z_index == -1 else str(roi.z_index)
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(z_text))
            # T position (position display)
            t_text = "all" if roi.t_index == -1 else str(roi.t_index)
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(t_text))
            # C position (position display)
            c_text = "all" if roi.c_index == -1 else str(roi.c_index)
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(c_text))
            # Color
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(roi.color))
            # Visible
            chk = QtWidgets.QTableWidgetItem()
            chk.setCheckState(
                QtCore.Qt.CheckState.Checked if roi.visible else QtCore.Qt.CheckState.Unchecked
            )
            self.table.setItem(row, 6, chk)
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)

    def get_selected_rows(self) -> list:
        """Get list of selected row indices (multi-select)."""
        return sorted(set(idx.row() for idx in self.table.selectedIndexes()))

    def get_selected_rois(self) -> List[Roi]:
        """Get list of selected ROI objects (multi-select)."""
        selected_rows = self.get_selected_rows()
        return [self._current_rois[row] for row in selected_rows if row < len(self._current_rois)]
    
    def set_tag_filter(self, tags: List[str]) -> None:
        """Filter ROIs by tags.
        
        Args:
            tags: List of tags to filter by (empty list = show all)
        """
        self._tag_filter = tags
        self.set_rois(self._all_rois)
    
    def get_tag_filter(self) -> List[str]:
        """Get currently active tag filter."""
        return self._tag_filter
