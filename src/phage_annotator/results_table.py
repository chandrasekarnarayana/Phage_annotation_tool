"""Results table dock widget."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Dict

from matplotlib.backends.qt_compat import QtWidgets

RESULT_COLUMNS = [
    "image_name",
    "t",
    "z",
    "roi_id",
    "mean",
    "std",
    "min",
    "max",
    "area_pixels",
    "area_um2",
]


class ResultsTableWidget(QtWidgets.QWidget):
    """Dock widget for measurement results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        btn_row = QtWidgets.QHBoxLayout()
        self.measure_btn = QtWidgets.QPushButton("Measure current slice")
        self.measure_t_btn = QtWidgets.QPushButton("Measure over time (T)")
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.copy_btn = QtWidgets.QPushButton("Copy")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        for btn in [
            self.measure_btn,
            self.measure_t_btn,
            self.clear_btn,
            self.copy_btn,
            self.export_btn,
        ]:
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QtWidgets.QTableWidget(0, len(RESULT_COLUMNS))
        self.table.setHorizontalHeaderLabels(RESULT_COLUMNS)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

    def add_row(self, row: Dict[str, object]) -> None:
        self.table.blockSignals(True)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, key in enumerate(RESULT_COLUMNS):
            self.table.setItem(r, c, QtWidgets.QTableWidgetItem(str(row.get(key, ""))))
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()

    def clear(self) -> None:
        self.table.setRowCount(0)

    def copy_to_clipboard(self) -> None:
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(RESULT_COLUMNS)
        for row in range(self.table.rowCount()):
            writer.writerow(
                [self.table.item(row, col).text() for col in range(self.table.columnCount())]
            )
        QtWidgets.QApplication.clipboard().setText(sio.getvalue())

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(RESULT_COLUMNS)
            for row in range(self.table.rowCount()):
                writer.writerow(
                    [self.table.item(row, col).text() for col in range(self.table.columnCount())]
                )
