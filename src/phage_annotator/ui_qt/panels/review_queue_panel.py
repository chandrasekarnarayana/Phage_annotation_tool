"""Review queue panel for assisted-annotation triage workflows."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class ReviewQueuePanel(QtWidgets.QWidget):
    """Right-dock panel showing current uncertain suggestion and queue progress."""

    accept_requested = QtCore.Signal()
    accept_next_requested = QtCore.Signal()
    accept_all_green_requested = QtCore.Signal()
    reject_requested = QtCore.Signal()
    skip_requested = QtCore.Signal()
    next_uncertain_requested = QtCore.Signal()
    apply_offset_requested = QtCore.Signal(int, float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self.header_lbl = QtWidgets.QLabel("Review Queue - T:- Z:-")
        self.header_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.header_lbl)
        self.context_lbl = QtWidgets.QLabel("Effective Assist Context: -")
        self.context_lbl.setWordWrap(True)
        self.context_lbl.setStyleSheet("color: #37474f;")
        layout.addWidget(self.context_lbl)
        self.context_delta_lbl = QtWidgets.QLabel("")
        self.context_delta_lbl.setWordWrap(True)
        self.context_delta_lbl.setStyleSheet("color: #ef6c00;")
        self.context_delta_lbl.setVisible(False)
        layout.addWidget(self.context_delta_lbl)
        self.legend_lbl = QtWidgets.QLabel(
            "Legend: <span style='color:#9e9e9e;'>■ heuristic</span> | "
            "<span style='color:#2e7d32;'>■ high</span> | "
            "<span style='color:#f9a825;'>■ medium</span> | "
            "<span style='color:#c62828;'>■ low</span>"
        )
        self.legend_lbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
        layout.addWidget(self.legend_lbl)

        self.remaining_lbl = QtWidgets.QLabel("Uncertain remaining: 0")
        layout.addWidget(self.remaining_lbl)
        self.telemetry_lbl = QtWidgets.QLabel("Throughput: n/a")
        self.telemetry_lbl.setStyleSheet("color: #546e7a;")
        layout.addWidget(self.telemetry_lbl)
        self.calib_spark_lbl = QtWidgets.QLabel("Calibration: -")
        self.calib_spark_lbl.setStyleSheet("color: #546e7a;")
        layout.addWidget(self.calib_spark_lbl)
        self.first_run_hint_lbl = QtWidgets.QLabel(
            "Tip: Use A/R/N/P for fast triage. Check context line before bulk actions."
        )
        self.first_run_hint_lbl.setWordWrap(True)
        self.first_run_hint_lbl.setStyleSheet("color: #455a64; font-style: italic;")
        layout.addWidget(self.first_run_hint_lbl)

        current_group = QtWidgets.QGroupBox("Current")
        current_layout = QtWidgets.QVBoxLayout(current_group)
        current_layout.setContentsMargins(8, 8, 8, 8)
        self.coords_lbl = QtWidgets.QLabel("(x=-, y=-)")
        self.score_lbl = QtWidgets.QLabel("Acceptance likelihood (p_accept): n/a")
        self.stale_lbl = QtWidgets.QLabel("staleness: n/a")
        self.assist_lbl = QtWidgets.QLabel("Assist state: Off")
        self.details_lbl = QtWidgets.QLabel("")
        self.details_lbl.setWordWrap(True)
        current_layout.addWidget(self.coords_lbl)
        current_layout.addWidget(self.score_lbl)
        current_layout.addWidget(self.stale_lbl)
        current_layout.addWidget(self.assist_lbl)
        current_layout.addWidget(self.details_lbl)
        layout.addWidget(current_group)

        btn_row = QtWidgets.QHBoxLayout()
        self.accept_btn = QtWidgets.QPushButton("Accept")
        self.accept_next_btn = QtWidgets.QPushButton("Accept + Next")
        self.reject_btn = QtWidgets.QPushButton("Reject")
        self.skip_btn = QtWidgets.QPushButton("Skip")
        btn_row.addWidget(self.accept_btn)
        btn_row.addWidget(self.accept_next_btn)
        btn_row.addWidget(self.reject_btn)
        btn_row.addWidget(self.skip_btn)
        layout.addLayout(btn_row)

        next_row = QtWidgets.QHBoxLayout()
        self.next_uncertain_btn = QtWidgets.QPushButton("Next uncertain")
        self.accept_green_btn = QtWidgets.QPushButton("Accept All Green")
        next_row.addWidget(self.next_uncertain_btn)
        next_row.addWidget(self.accept_green_btn)
        layout.addLayout(next_row)

        offset_group = QtWidgets.QGroupBox("Offset correction")
        offset_layout = QtWidgets.QGridLayout(offset_group)
        offset_layout.setContentsMargins(8, 8, 8, 8)
        offset_layout.setHorizontalSpacing(6)
        offset_layout.setVerticalSpacing(4)
        self.offset_count_spin = QtWidgets.QSpinBox(offset_group)
        self.offset_count_spin.setRange(1, 1)
        self.offset_count_spin.setValue(1)
        self.offset_dx_spin = QtWidgets.QDoubleSpinBox(offset_group)
        self.offset_dx_spin.setRange(-500.0, 500.0)
        self.offset_dx_spin.setDecimals(2)
        self.offset_dx_spin.setValue(0.0)
        self.offset_dy_spin = QtWidgets.QDoubleSpinBox(offset_group)
        self.offset_dy_spin.setRange(-500.0, 500.0)
        self.offset_dy_spin.setDecimals(2)
        self.offset_dy_spin.setValue(0.0)
        self.apply_offset_btn = QtWidgets.QPushButton("Apply XY offset", offset_group)
        offset_layout.addWidget(QtWidgets.QLabel("Top-N"), 0, 0)
        offset_layout.addWidget(self.offset_count_spin, 0, 1)
        offset_layout.addWidget(QtWidgets.QLabel("dx"), 0, 2)
        offset_layout.addWidget(self.offset_dx_spin, 0, 3)
        offset_layout.addWidget(QtWidgets.QLabel("dy"), 0, 4)
        offset_layout.addWidget(self.offset_dy_spin, 0, 5)
        offset_layout.addWidget(self.apply_offset_btn, 1, 0, 1, 6)
        layout.addWidget(offset_group)

        self.progress_lbl = QtWidgets.QLabel("Progress: 0 / 0")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_lbl)
        layout.addWidget(self.progress_bar)
        layout.addStretch(1)

        self.accept_btn.clicked.connect(self.accept_requested.emit)
        self.accept_next_btn.clicked.connect(self.accept_next_requested.emit)
        self.accept_next_btn.setToolTip("Shortcut cadence: A then N")
        self.accept_green_btn.clicked.connect(self.accept_all_green_requested.emit)
        self.reject_btn.clicked.connect(self.reject_requested.emit)
        self.skip_btn.clicked.connect(self.skip_requested.emit)
        self.next_uncertain_btn.clicked.connect(self.next_uncertain_requested.emit)
        self.apply_offset_btn.clicked.connect(
            lambda: self.apply_offset_requested.emit(
                int(self.offset_count_spin.value()),
                float(self.offset_dx_spin.value()),
                float(self.offset_dy_spin.value()),
            )
        )
