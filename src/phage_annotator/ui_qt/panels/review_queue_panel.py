"""Review queue panel for assisted-annotation triage workflows."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.panels.suggestion_explain_panel import SuggestionExplainPanel
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


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
    suggest_points_requested = QtCore.Signal()
    clear_suggestions_requested = QtCore.Signal()
    show_suggestions_toggled = QtCore.Signal(bool)

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

        # Header with keyboard help button
        header_row = QtWidgets.QHBoxLayout()
        self.header_lbl = QtWidgets.QLabel("Assist Queue")
        self.header_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #1976d2;")
        header_row.addWidget(self.header_lbl)
        header_row.addStretch()
        self.help_btn = QtWidgets.QPushButton("?")
        self.help_btn.setMaximumWidth(24)
        self.help_btn.setMaximumHeight(24)
        self.help_btn.setToolTip("Show keyboard shortcuts")
        self.help_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.help_btn.setStyleSheet(
            "QPushButton { background-color: #2196f3; color: white; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background-color: #1976d2; }"
        )
        header_row.addWidget(self.help_btn)
        layout.addLayout(header_row)

        controls_row = QtWidgets.QHBoxLayout()
        controls_row.setSpacing(6)
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItem("All", "all")
        self.filter_combo.addItem("High confidence", "high_confidence")
        self.filter_combo.addItem("Uncertain", "high_uncertainty")
        self.filter_combo.setStyleSheet(
            "QComboBox { padding: 4px; border: 1px solid #ccc; border-radius: 3px; }"
            "QComboBox:hover { border: 1px solid #999; }"
        )
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItem("Confidence", "confidence")
        self.sort_combo.addItem("Uncertainty", "uncertainty")
        self.sort_combo.setStyleSheet(
            "QComboBox { padding: 4px; border: 1px solid #ccc; border-radius: 3px; }"
            "QComboBox:hover { border: 1px solid #999; }"
        )
        controls_row.addWidget(QtWidgets.QLabel("Filter:"))
        controls_row.addWidget(self.filter_combo, 1)
        controls_row.addWidget(QtWidgets.QLabel("Sort:"))
        controls_row.addWidget(self.sort_combo, 1)
        layout.addLayout(controls_row)

        # Add quick action buttons for suggest and clear
        quick_actions_row = QtWidgets.QHBoxLayout()
        quick_actions_row.setSpacing(6)
        self.suggest_btn = QtWidgets.QPushButton("💡 Suggest Points")
        self.clear_btn = QtWidgets.QPushButton("🗑️ Clear Suggestions")
        self.suggest_btn.setMinimumHeight(26)
        self.clear_btn.setMinimumHeight(26)
        self.suggest_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.clear_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.suggest_btn.setStyleSheet(
            "QPushButton { background-color: #2196f3; color: white; font-weight: 500; border-radius: 3px; }"
            "QPushButton:hover { background-color: #1976d2; }"
            "QPushButton:pressed { background-color: #1565c0; }"
        )
        self.clear_btn.setStyleSheet(
            "QPushButton { background-color: #757575; color: white; font-weight: 500; border-radius: 3px; }"
            "QPushButton:hover { background-color: #616161; }"
            "QPushButton:pressed { background-color: #424242; }"
        )
        self.suggest_btn.setToolTip("Generate suggestions for the current image\nMenu: Assist → Suggest Points")
        self.clear_btn.setToolTip("Clear all current suggestions\nMenu: Assist → Clear Suggestions")
        quick_actions_row.addWidget(self.suggest_btn)
        quick_actions_row.addWidget(self.clear_btn)
        quick_actions_row.addStretch(1)
        layout.addLayout(quick_actions_row)

        self.show_suggestions_chk = QtWidgets.QCheckBox("Show suggestions on canvas")
        self.show_suggestions_chk.setChecked(True)
        self.show_suggestions_chk.setToolTip("Toggle suggestion markers on the canvas without clearing the queue.")
        layout.addWidget(self.show_suggestions_chk)


        self.remaining_lbl = QtWidgets.QLabel("Queue: 0 uncertain")
        self.remaining_lbl.setStyleSheet("font-size: 11px; color: #546e7a; padding: 6px; background-color: #f5f5f5; border-radius: 3px;")
        layout.addWidget(self.remaining_lbl)

        current_group = QtWidgets.QGroupBox("Current Suggestion")
        current_group.setStyleSheet(
            "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
        )
        current_layout = QtWidgets.QVBoxLayout(current_group)
        current_layout.setContentsMargins(8, 8, 8, 8)
        current_layout.setSpacing(4)
        self.coords_lbl = QtWidgets.QLabel("Position: (x=-, y=-)")
        self.coords_lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #1976d2;")
        self.score_lbl = QtWidgets.QLabel("Confidence: n/a")
        self.score_lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #388e3c;")
        self.assist_lbl = QtWidgets.QLabel("Status: -")
        self.assist_lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #f57c00;")
        self.details_lbl = QtWidgets.QLabel("")
        self.details_lbl.setWordWrap(True)
        self.details_lbl.setStyleSheet("font-size: 10px; color: #37474f; padding: 4px; background-color: #fafafa; border-radius: 3px;")
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
        self.mark_accept_btn = QtWidgets.QPushButton("✓ Mark Accepted")
        self.mark_reject_btn = QtWidgets.QPushButton("✗ Mark Rejected")
        self.mark_proposed_btn = QtWidgets.QPushButton("⊕ Mark Proposed")
        for btn in (self.mark_accept_btn, self.mark_reject_btn, self.mark_proposed_btn):
            btn.setMinimumHeight(26)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.mark_accept_btn.setStyleSheet(
            "QPushButton { background-color: #4caf50; color: white; font-weight: 500; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.mark_reject_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; font-weight: 500; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        self.mark_proposed_btn.setStyleSheet(
            "QPushButton { background-color: #ffc107; color: black; font-weight: 500; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background-color: #ffb300; }"
        )
        self.mark_accept_btn.setToolTip("Change selected suggestion status to Accepted")
        self.mark_reject_btn.setToolTip("Change selected suggestion status to Rejected")
        self.mark_proposed_btn.setToolTip("Change selected suggestion status back to Proposed (undecided)")
        decision_row.addWidget(self.mark_accept_btn)
        decision_row.addWidget(self.mark_reject_btn)
        decision_row.addWidget(self.mark_proposed_btn)
        layout.addWidget(table_group)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)
        self.accept_btn = QtWidgets.QPushButton("✓ Accept")
        self.accept_next_btn = QtWidgets.QPushButton("✓ Accept + Next")
        self.reject_btn = QtWidgets.QPushButton("✗ Reject")
        self.skip_btn = QtWidgets.QPushButton("⊗ Skip")
        for btn in (self.accept_btn, self.accept_next_btn, self.reject_btn, self.skip_btn):
            btn.setMinimumHeight(30)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        # Color the buttons for clarity
        self.accept_btn.setStyleSheet(
            "QPushButton { background-color: #4caf50; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:pressed { background-color: #3d8b40; }"
        )
        self.accept_next_btn.setStyleSheet(
            "QPushButton { background-color: #2196f3; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0b7dda; }"
            "QPushButton:pressed { background-color: #0a5bb9; }"
        )
        self.reject_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #da190b; }"
            "QPushButton:pressed { background-color: #ba0000; }"
        )
        self.skip_btn.setStyleSheet(
            "QPushButton { background-color: #ff9800; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #e68900; }"
            "QPushButton:pressed { background-color: #cc7700; }"
        )
        # Add helpful tooltips
        self.accept_btn.setToolTip("Accept current suggestion and add to annotations\nKeyboard: A")
        self.accept_next_btn.setToolTip("Accept and automatically move to next uncertain suggestion\nKeyboard: A → N")
        self.reject_btn.setToolTip("Reject current suggestion as a false positive\nKeyboard: R")
        self.skip_btn.setToolTip("Skip to next suggestion without deciding\nKeyboard: N")
        btn_row.addWidget(self.accept_btn)
        btn_row.addWidget(self.accept_next_btn)
        btn_row.addWidget(self.reject_btn)
        btn_row.addWidget(self.skip_btn)
        layout.addLayout(btn_row)

        self.advanced_toggle_btn = QtWidgets.QToolButton(self)
        self.advanced_toggle_btn.setText("Advanced Assist Controls")
        self.advanced_toggle_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle_btn.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.advanced_toggle_btn.setCheckable(True)
        self.advanced_toggle_btn.setChecked(False)
        self.advanced_toggle_btn.setStyleSheet(
            "QToolButton { font-weight: 600; color: #455a64; padding: 4px 2px; border: none; }"
            "QToolButton:hover { color: #1976d2; }"
        )
        self.advanced_toggle_btn.setToolTip(
            "Show batch actions, decision-state tools, offset correction, and confidence details."
        )
        layout.addWidget(self.advanced_toggle_btn)

        self.advanced_container = QtWidgets.QWidget(self)
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(10)

        decision_group = QtWidgets.QGroupBox("Selected Queue Item")
        decision_group.setStyleSheet(
            "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
        )
        decision_group_layout = QtWidgets.QVBoxLayout(decision_group)
        decision_group_layout.setContentsMargins(8, 8, 8, 8)
        decision_group_layout.addLayout(decision_row)
        advanced_layout.addWidget(decision_group)

        next_row = QtWidgets.QHBoxLayout()
        next_row.setSpacing(6)
        self.next_uncertain_btn = QtWidgets.QPushButton("↓ Next Uncertain")
        self.accept_green_btn = QtWidgets.QPushButton("✓ Accept All High Conf")
        self.next_uncertain_btn.setMinimumHeight(30)
        self.accept_green_btn.setMinimumHeight(30)
        self.next_uncertain_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.accept_green_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.next_uncertain_btn.setStyleSheet(
            "QPushButton { background-color: #757575; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #616161; }"
            "QPushButton:pressed { background-color: #424242; }"
        )
        self.accept_green_btn.setStyleSheet(
            "QPushButton { background-color: #8bc34a; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #7cb342; }"
            "QPushButton:pressed { background-color: #689f38; }"
        )
        self.next_uncertain_btn.setToolTip("Jump to next uncertain suggestion\nKeyboard: W")
        self.accept_green_btn.setToolTip("Batch accept all high-confidence suggestions (score ≥ 0.75)")
        next_row.addWidget(self.next_uncertain_btn)
        next_row.addWidget(self.accept_green_btn)
        advanced_layout.addLayout(next_row)

        offset_group = QtWidgets.QGroupBox("Offset correction")
        offset_group.setStyleSheet(
            "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
        )
        offset_layout = QtWidgets.QGridLayout(offset_group)
        offset_layout.setContentsMargins(8, 8, 8, 8)
        offset_layout.setHorizontalSpacing(6)
        offset_layout.setVerticalSpacing(4)
        self.offset_count_spin = QtWidgets.QSpinBox(offset_group)
        self.offset_count_spin.setRange(1, 1)
        self.offset_count_spin.setValue(1)
        self.offset_count_spin.setToolTip("Number of top suggestions to correct")
        self.offset_dx_spin = QtWidgets.QDoubleSpinBox(offset_group)
        self.offset_dx_spin.setRange(-500.0, 500.0)
        self.offset_dx_spin.setDecimals(2)
        self.offset_dx_spin.setValue(0.0)
        self.offset_dx_spin.setToolTip("X-axis offset in pixels")
        self.offset_dy_spin = QtWidgets.QDoubleSpinBox(offset_group)
        self.offset_dy_spin.setRange(-500.0, 500.0)
        self.offset_dy_spin.setDecimals(2)
        self.offset_dy_spin.setValue(0.0)
        self.offset_dy_spin.setToolTip("Y-axis offset in pixels")
        self.apply_offset_btn = QtWidgets.QPushButton("📍 Apply XY offset", offset_group)
        self.apply_offset_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.apply_offset_btn.setStyleSheet(
            "QPushButton { background-color: #9c27b0; color: white; font-weight: 600; border-radius: 4px; }"
            "QPushButton:hover { background-color: #7b1fa2; }"
            "QPushButton:pressed { background-color: #6a0dad; }"
        )
        offset_layout.addWidget(QtWidgets.QLabel("Top-N"), 0, 0)
        offset_layout.addWidget(self.offset_count_spin, 0, 1)
        offset_layout.addWidget(QtWidgets.QLabel("dx"), 0, 2)
        offset_layout.addWidget(self.offset_dx_spin, 0, 3)
        offset_layout.addWidget(QtWidgets.QLabel("dy"), 0, 4)
        offset_layout.addWidget(self.offset_dy_spin, 0, 5)
        offset_layout.addWidget(self.apply_offset_btn, 1, 0, 1, 6)
        advanced_layout.addWidget(offset_group)

        reasoning_group = QtWidgets.QGroupBox("Confidence Details")
        reasoning_group.setStyleSheet(
            "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
        )
        reasoning_layout = QtWidgets.QVBoxLayout(reasoning_group)
        reasoning_layout.setContentsMargins(0, 0, 0, 0)
        self.explain_panel = SuggestionExplainPanel(parent=reasoning_group)
        reasoning_layout.addWidget(self.explain_panel)
        advanced_layout.addWidget(reasoning_group)
        self.advanced_container.setVisible(False)
        layout.addWidget(self.advanced_container)

        self.progress_lbl = QtWidgets.QLabel("Progress: 0 / 0")
        self.progress_lbl.setStyleSheet("font-weight: 500; font-size: 11px; color: #546e7a;")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background-color: #e0e0e0;"
            "  border: 1px solid #bdbdbd;"
            "  border-radius: 4px;"
            "  text-align: center;"
            "}"
            "QProgressBar::chunk {"
            "  background-color: #4caf50;"
            "  border-radius: 3px;"
            "}"
        )
        self.progress_bar.setTextVisible(True)
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
        self.suggest_btn.clicked.connect(self.suggest_points_requested.emit)
        self.clear_btn.clicked.connect(self.clear_suggestions_requested.emit)
        self.show_suggestions_chk.toggled.connect(self.show_suggestions_toggled.emit)
        self.help_btn.clicked.connect(self._show_keyboard_shortcuts)
        self.apply_offset_btn.clicked.connect(
            lambda: self.apply_offset_requested.emit(
                int(self.offset_count_spin.value()),
                float(self.offset_dx_spin.value()),
                float(self.offset_dy_spin.value()),
            )
        )
        self.advanced_toggle_btn.toggled.connect(self._toggle_advanced_controls)
        self.mark_accept_btn.clicked.connect(
            lambda: self._emit_decision_for_selected("accepted")
        )
        self.mark_reject_btn.clicked.connect(
            lambda: self._emit_decision_for_selected("rejected")
        )
        self.mark_proposed_btn.clicked.connect(
            lambda: self._emit_decision_for_selected("proposed")
        )

    def _show_keyboard_shortcuts(self) -> None:
        """Show a helpful dialog with keyboard shortcuts for assist workflow."""
        shortcuts = [
            ("A", "Accept current suggestion"),
            ("R", "Reject current suggestion"),
            ("N", "Skip to next suggestion"),
            ("W", "Jump to next uncertain"),
            ("A → N", "Accept & move to next (fast workflow)"),
            ("Space", "Pan view to suggestion"),
        ]
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Assist Keyboard Shortcuts")
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        
        text = "Quick Keyboard Reference:\n\n"
        for key, desc in shortcuts:
            text += f"  {key:<8} → {desc}\n"
        text += "\n💡 Tip: Hover over buttons for more details"
        
        msg_box.setText(text)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def _toggle_advanced_controls(self, checked: bool) -> None:
        """Show or hide advanced assist controls."""
        self.advanced_container.setVisible(bool(checked))
        self.advanced_toggle_btn.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if bool(checked) else QtCore.Qt.ArrowType.RightArrow
        )

    def set_suggestions(self, rows: list[dict[str, str]], current_row: int) -> None:
        """Populate suggested-points table and keep selected row in sync."""
        logger = get_panel_logger("assist")
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
        
        # Log suggestion queue update
        accepted = sum(1 for r in rows if str(r.get("status", "")).lower() == "accepted")
        rejected = sum(1 for r in rows if str(r.get("status", "")).lower() == "rejected")
        proposed = len(rows) - accepted - rejected
        logger.log_action(
            "suggestion_queue_updated",
            total_suggestions=len(rows),
            accepted_count=accepted,
            rejected_count=rejected,
            proposed_count=proposed,
            current_row_idx=current_row,
        )
        
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
