"""ROI Manager dock UI."""

from __future__ import annotations

from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.roi_manager import Roi, RoiManager


class RoiManagerWidget(QtWidgets.QWidget):
    """Dock widget for managing multiple ROIs."""

    def __init__(self, manager: RoiManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Color", "Visible"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add")
        self.del_btn = QtWidgets.QPushButton("Delete")
        self.rename_btn = QtWidgets.QPushButton("Rename")
        self.dup_btn = QtWidgets.QPushButton("Duplicate")
        self.save_btn = QtWidgets.QPushButton("Save ROIs")
        self.load_btn = QtWidgets.QPushButton("Load ROIs")
        self.measure_btn = QtWidgets.QPushButton("Measure")
        for btn in [self.add_btn, self.del_btn, self.rename_btn, self.dup_btn, self.save_btn, self.load_btn]:
            btn_row.addWidget(btn)
        btn_row.addWidget(self.measure_btn)
        layout.addLayout(btn_row)

    def set_rois(self, rois: List[Roi]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(rois))
        for row, roi in enumerate(rois):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(roi.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(roi.roi_type))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(roi.color))
            chk = QtWidgets.QTableWidgetItem()
            chk.setCheckState(QtCore.Qt.CheckState.Checked if roi.visible else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 3, chk)
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
