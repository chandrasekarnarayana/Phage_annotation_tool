"""Review queue panel for assisted-annotation triage workflows."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.panels.suggestion_explain_panel import SuggestionExplainPanel


class ReviewQueuePanel(QtWidgets.QWidget):
    """Right-dock panel showing current uncertain suggestion and queue progress."""

    accept_requested = QtCore.Signal()
    accept_next_requested = QtCore.Signal()
    accept_all_green_requested = QtCore.Signal()
    reject_requested = QtCore.Signal()
    skip_requested = QtCore.Signal()
    next_uncertain_requested = QtCore.Signal()
    apply_offset_requested = QtCore.Signal(int, float, float)
    suggestion_row_selected = QtCore.Signal(int)
    decision_requested = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review_queue_panel")
        self.setStyleSheet(
            "#review_queue_panel QGroupBox { margin-top: 8px; }"
            "#review_queue_panel QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.header_lbl = QtWidgets.QLabel("Assist Queue")
        self.header_lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
        layout.addWidget(self.header_lbl)

        controls_row = QtWidgets.QHBoxLayout()
        controls_row.setSpacing(6)
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItem("All", "all")
        self.filter_combo.addItem("High confidence", "high_confidence")
        self.filter_combo.addItem("Uncertain", "high_uncertainty")
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItem("Confidence", "confidence")
        self.sort_combo.addItem("Uncertainty", "uncertainty")
        controls_row.addWidget(QtWidgets.QLabel("Filter:"))
        controls_row.addWidget(self.filter_combo, 1)
        controls_row.addWidget(QtWidgets.QLabel("Sort:"))
        controls_row.addWidget(self.sort_combo, 1)
        layout.addLayout(controls_row)

        self.remaining_lbl = QtWidgets.QLabel("Queue: 0 uncertain")
        self.remaining_lbl.setStyleSheet("font-size: 11px; color: #546e7a;")
        layout.addWidget(self.remaining_lbl)

        current_group = QtWidgets.QGroupBox("Current Suggestion")
        current_layout = QtWidgets.QVBoxLayout(current_group)
        current_layout.setContentsMargins(8, 8, 8, 8)
        current_layout.setSpacing(4)
        self.coords_lbl = QtWidgets.QLabel("Position: (x=-, y=-)")
        self.score_lbl = QtWidgets.QLabel("Confidence: n/a")
        self.assist_lbl = QtWidgets.QLabel("Status: -")
        self.details_lbl = QtWidgets.QLabel("")
        self.details_lbl.setWordWrap(True)
        self.details_lbl.setStyleSheet("font-size: 10px; color: #37474f;")
        current_layout.addWidget(self.coords_lbl)
        current_layout.addWidget(self.score_lbl)
        current_layout.addWidget(self.assist_lbl)
        current_layout.addWidget(self.details_lbl)
        layout.addWidget(current_group)

        table_group = QtWidgets.QGroupBox("Queue")
        table_layout = QtWidgets.QVBoxLayout(table_group)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(4)
        self.suggestions_table = QtWidgets.QTableWidget(0, 6, table_group)
        self.suggestions_table.setHorizontalHeaderLabels(
            ["#", "X", "Y", "T/Z", "Confidence", "Action"]
        )
        self.suggestions_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.suggestions_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.suggestions_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.suggestions_table.verticalHeader().setVisible(False)
        self.suggestions_table.setAlternatingRowColors(True)
        self.suggestions_table.setMinimumHeight(150)
        self.suggestions_table.verticalHeader().setDefaultSectionSize(24)
        self.suggestions_table.setStyleSheet(
            "QTableWidget { gridline-color: #e5e7eb; }"
            "QHeaderView::section { padding: 4px 6px; }"
        )
        header = self.suggestions_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.suggestions_table.itemSelectionChanged.connect(self._emit_selected_suggestion_row)
        table_layout.addWidget(self.suggestions_table)
        decision_row = QtWidgets.QHBoxLayout()
        decision_row.setSpacing(6)
        self.mark_accept_btn = QtWidgets.QPushButton("Set Accepted")
        self.mark_reject_btn = QtWidgets.QPushButton("Set Rejected")
        self.mark_proposed_btn = QtWidgets.QPushButton("Set Proposed")
        for btn in (self.mark_accept_btn, self.mark_reject_btn, self.mark_proposed_btn):
            btn.setMinimumHeight(26)
            decision_row.addWidget(btn)
        table_layout.addLayout(decision_row)
        layout.addWidget(table_group)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)
        self.accept_btn = QtWidgets.QPushButton("Accept")
        self.accept_next_btn = QtWidgets.QPushButton("Accept + Next")
        self.reject_btn = QtWidgets.QPushButton("Reject")
        self.skip_btn = QtWidgets.QPushButton("Skip")
        for btn in (self.accept_btn, self.accept_next_btn, self.reject_btn, self.skip_btn):
            btn.setMinimumHeight(30)
        btn_row.addWidget(self.accept_btn)
        btn_row.addWidget(self.accept_next_btn)
        btn_row.addWidget(self.reject_btn)
        btn_row.addWidget(self.skip_btn)
        layout.addLayout(btn_row)

        next_row = QtWidgets.QHBoxLayout()
        next_row.setSpacing(6)
        self.next_uncertain_btn = QtWidgets.QPushButton("Next uncertain")
        self.accept_green_btn = QtWidgets.QPushButton("Accept All Green")
        self.next_uncertain_btn.setMinimumHeight(30)
        self.accept_green_btn.setMinimumHeight(30)
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

        reasoning_group = QtWidgets.QGroupBox("Reasoning")
        reasoning_layout = QtWidgets.QVBoxLayout(reasoning_group)
        reasoning_layout.setContentsMargins(0, 0, 0, 0)
        self.explain_panel = SuggestionExplainPanel(parent=reasoning_group)
        reasoning_layout.addWidget(self.explain_panel)
        layout.addWidget(reasoning_group)

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
        self.mark_accept_btn.clicked.connect(
            lambda: self._emit_decision_for_selected("accepted")
        )
        self.mark_reject_btn.clicked.connect(
            lambda: self._emit_decision_for_selected("rejected")
        )
        self.mark_proposed_btn.clicked.connect(
            lambda: self._emit_decision_for_selected("proposed")
        )

    def set_suggestions(self, rows: list[dict[str, str]], current_row: int) -> None:
        """Populate suggested-points table and keep selected row in sync."""
        status_bg = {
            "accepted": QtGui.QColor("#e8f5e9"),
            "rejected": QtGui.QColor("#ffebee"),
            "proposed": QtGui.QColor("#fffde7"),
        }
        status_fg = {
            "accepted": QtGui.QColor("#1b5e20"),
            "rejected": QtGui.QColor("#b71c1c"),
            "proposed": QtGui.QColor("#7f6000"),
        }
        self.suggestions_table.blockSignals(True)
        self.suggestions_table.setRowCount(len(rows))
        for ridx, row in enumerate(rows):
            key = str(row.get("status", "proposed")).strip().lower()
            t_val = str(row.get("t", "-"))
            z_val = str(row.get("z", "-"))
            t_z = f"{t_val}/{z_val}" if t_val != "-" or z_val != "-" else "-"
            action_state = str(row.get("state", "proposed")).upper()
            if key == "accepted":
                action_state = "✓ ACCEPT"
            elif key == "rejected":
                action_state = "✗ REJECT"
            values = [
                str(row.get("index", ridx + 1)),
                str(row.get("x", "-")),
                str(row.get("y", "-")),
                t_z,
                str(row.get("acceptance", "n/a")),
                action_state,
            ]
            for cidx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if cidx == 0:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, str(row.get("suggestion_id", "")))
                if key in status_bg:
                    item.setBackground(status_bg[key])
                if cidx == 4 and key in status_fg:
                    item.setForeground(status_fg[key])
                if cidx == 5 and key in status_fg:
                    item.setForeground(status_fg[key])
                self.suggestions_table.setItem(ridx, cidx, item)
        if rows:
            row = max(0, min(int(current_row), len(rows) - 1))
            self.suggestions_table.selectRow(row)
            self.suggestions_table.scrollToItem(
                self.suggestions_table.item(row, 0),
                QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter,
            )
        self.suggestions_table.blockSignals(False)

    def _emit_selected_suggestion_row(self) -> None:
        """Emit selected row for controller-driven focus actions."""
        indexes = self.suggestions_table.selectionModel().selectedRows()
        if not indexes:
            return
        row = int(indexes[0].row())
        self.suggestion_row_selected.emit(row)

    def _selected_suggestion_id(self) -> str:
        """Return selected suggestion id from table row metadata."""
        indexes = self.suggestions_table.selectionModel().selectedRows()
        if not indexes:
            return ""
        row = int(indexes[0].row())
        item = self.suggestions_table.item(row, 0)
        if item is None:
            return ""
        return str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")

    def _emit_decision_for_selected(self, status: str) -> None:
        """Emit desired decision for the currently selected suggestion row."""
        suggestion_id = self._selected_suggestion_id()
        if not suggestion_id:
            return
        self.decision_requested.emit(suggestion_id, str(status))
