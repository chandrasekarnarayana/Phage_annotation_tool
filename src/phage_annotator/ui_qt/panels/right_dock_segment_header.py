"""Segmented header for right-dock discoverability (Table / Queue / Why)."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class RightDockSegmentHeader(QtWidgets.QWidget):
    """Clickable segmented header with live badges for right-dock tabs."""

    segment_requested = QtCore.Signal(str)
    review_pack_toggled = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.table_btn = QtWidgets.QPushButton("Table (0)")
        self.table_btn.setCheckable(True)
        self.queue_btn = QtWidgets.QPushButton("Queue (0)")
        self.queue_btn.setCheckable(True)
        self.why_btn = QtWidgets.QPushButton("Why?")
        self.why_btn.setCheckable(True)
        self.pack_btn = QtWidgets.QPushButton("Review Pack")

        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        for btn in (self.table_btn, self.queue_btn, self.why_btn):
            btn.setMinimumHeight(26)
            group.addButton(btn)
            layout.addWidget(btn)
        self.pack_btn.setMinimumHeight(26)
        self.pack_btn.setToolTip("Toggle Review Context Pack (Table + Queue + Why)")
        layout.addWidget(self.pack_btn)

        self.setStyleSheet(
            "QPushButton { padding: 4px 10px; border: 1px solid #c5c5c5; border-radius: 5px; }"
            "QPushButton:checked { background-color: #1976d2; color: #ffffff; font-weight: 700; border-color: #1565c0; }"
        )

        self.table_btn.clicked.connect(lambda: self.segment_requested.emit("table"))
        self.queue_btn.clicked.connect(lambda: self.segment_requested.emit("queue"))
        self.why_btn.clicked.connect(lambda: self.segment_requested.emit("why"))
        self.pack_btn.clicked.connect(self.review_pack_toggled.emit)

    def set_counts(self, *, table_count: int, queue_count: int) -> None:
        """Refresh visible count badges."""
        t = int(max(0, table_count))
        q = int(max(0, queue_count))
        self.table_btn.setText(f"Table ({t})")
        self.queue_btn.setText(f"Queue ({q} ⚠)" if q > 0 else "Queue (0)")

    def set_active(self, segment: str) -> None:
        """Mark one segment as active."""
        seg = str(segment).strip().lower()
        if seg == "queue":
            self.queue_btn.setChecked(True)
        elif seg == "why":
            self.why_btn.setChecked(True)
        else:
            self.table_btn.setChecked(True)
