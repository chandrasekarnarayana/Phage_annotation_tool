"""Advanced controls builder for the review queue panel."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.panels.suggestion_explain_panel import SuggestionExplainPanel


def add_advanced_controls(panel: object, layout: QtWidgets.QVBoxLayout, decision_row: QtWidgets.QHBoxLayout) -> None:
    """Create the collapsible advanced assist controls region."""
    panel.advanced_toggle_btn = QtWidgets.QToolButton(panel)
    panel.advanced_toggle_btn.setText("Advanced Assist Controls")
    panel.advanced_toggle_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    panel.advanced_toggle_btn.setArrowType(QtCore.Qt.ArrowType.RightArrow)
    panel.advanced_toggle_btn.setCheckable(True)
    panel.advanced_toggle_btn.setChecked(False)
    panel.advanced_toggle_btn.setStyleSheet(
        "QToolButton { font-weight: 600; color: #455a64; padding: 4px 2px; border: none; }"
        "QToolButton:hover { color: #1976d2; }"
    )
    panel.advanced_toggle_btn.setToolTip(
        "Show batch actions, decision-state tools, offset correction, and confidence details."
    )
    layout.addWidget(panel.advanced_toggle_btn)

    panel.advanced_container = QtWidgets.QWidget(panel)
    advanced_layout = QtWidgets.QVBoxLayout(panel.advanced_container)
    advanced_layout.setContentsMargins(0, 0, 0, 0)
    advanced_layout.setSpacing(10)
    _add_decision_group(advanced_layout, decision_row)
    _add_next_actions(panel, advanced_layout)
    _add_offset_controls(panel, advanced_layout)
    _add_reasoning_group(panel, advanced_layout)
    panel.advanced_container.setVisible(False)
    layout.addWidget(panel.advanced_container)


def _add_decision_group(advanced_layout: QtWidgets.QVBoxLayout, decision_row: QtWidgets.QHBoxLayout) -> None:
    """Add the selected-item decision group to the advanced region."""
    decision_group = QtWidgets.QGroupBox("Selected Queue Item")
    decision_group.setStyleSheet(
        "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
    )
    decision_group_layout = QtWidgets.QVBoxLayout(decision_group)
    decision_group_layout.setContentsMargins(8, 8, 8, 8)
    decision_group_layout.addLayout(decision_row)
    advanced_layout.addWidget(decision_group)


def _add_next_actions(panel: object, advanced_layout: QtWidgets.QVBoxLayout) -> None:
    """Add next-uncertain and batch-accept controls."""
    next_row = QtWidgets.QHBoxLayout()
    next_row.setSpacing(6)
    panel.next_uncertain_btn = QtWidgets.QPushButton("↓ Next Uncertain")
    panel.accept_green_btn = QtWidgets.QPushButton("✓ Accept All High Conf")
    for button in (panel.next_uncertain_btn, panel.accept_green_btn):
        button.setMinimumHeight(30)
        button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    panel.next_uncertain_btn.setStyleSheet(
        "QPushButton { background-color: #757575; color: white; font-weight: 600; border-radius: 4px; }"
        "QPushButton:hover { background-color: #616161; }"
        "QPushButton:pressed { background-color: #424242; }"
    )
    panel.accept_green_btn.setStyleSheet(
        "QPushButton { background-color: #8bc34a; color: white; font-weight: 600; border-radius: 4px; }"
        "QPushButton:hover { background-color: #7cb342; }"
        "QPushButton:pressed { background-color: #689f38; }"
    )
    panel.next_uncertain_btn.setToolTip("Jump to next uncertain suggestion\nKeyboard: W")
    panel.accept_green_btn.setToolTip("Batch accept all high-confidence suggestions (score ≥ 0.75)")
    next_row.addWidget(panel.next_uncertain_btn)
    next_row.addWidget(panel.accept_green_btn)
    advanced_layout.addLayout(next_row)


def _add_offset_controls(panel: object, advanced_layout: QtWidgets.QVBoxLayout) -> None:
    """Add top-N XY offset correction controls."""
    offset_group = QtWidgets.QGroupBox("Offset correction")
    offset_group.setStyleSheet(
        "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
    )
    offset_layout = QtWidgets.QGridLayout(offset_group)
    offset_layout.setContentsMargins(8, 8, 8, 8)
    offset_layout.setHorizontalSpacing(6)
    offset_layout.setVerticalSpacing(4)
    panel.offset_count_spin = QtWidgets.QSpinBox(offset_group)
    panel.offset_count_spin.setRange(1, 1)
    panel.offset_count_spin.setValue(1)
    panel.offset_count_spin.setToolTip("Number of top suggestions to correct")
    panel.offset_dx_spin = QtWidgets.QDoubleSpinBox(offset_group)
    panel.offset_dx_spin.setRange(-500.0, 500.0)
    panel.offset_dx_spin.setDecimals(2)
    panel.offset_dx_spin.setValue(0.0)
    panel.offset_dx_spin.setToolTip("X-axis offset in pixels")
    panel.offset_dy_spin = QtWidgets.QDoubleSpinBox(offset_group)
    panel.offset_dy_spin.setRange(-500.0, 500.0)
    panel.offset_dy_spin.setDecimals(2)
    panel.offset_dy_spin.setValue(0.0)
    panel.offset_dy_spin.setToolTip("Y-axis offset in pixels")
    panel.apply_offset_btn = QtWidgets.QPushButton("📍 Apply XY offset", offset_group)
    panel.apply_offset_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    panel.apply_offset_btn.setStyleSheet(
        "QPushButton { background-color: #9c27b0; color: white; font-weight: 600; border-radius: 4px; }"
        "QPushButton:hover { background-color: #7b1fa2; }"
        "QPushButton:pressed { background-color: #6a0dad; }"
    )
    for column, label in enumerate(("Top-N", "dx", "dy")):
        offset_layout.addWidget(QtWidgets.QLabel(label), 0, column * 2)
    offset_layout.addWidget(panel.offset_count_spin, 0, 1)
    offset_layout.addWidget(panel.offset_dx_spin, 0, 3)
    offset_layout.addWidget(panel.offset_dy_spin, 0, 5)
    offset_layout.addWidget(panel.apply_offset_btn, 1, 0, 1, 6)
    advanced_layout.addWidget(offset_group)


def _add_reasoning_group(panel: object, advanced_layout: QtWidgets.QVBoxLayout) -> None:
    """Add the confidence details explain panel."""
    reasoning_group = QtWidgets.QGroupBox("Confidence Details")
    reasoning_group.setStyleSheet(
        "QGroupBox { border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 6px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
    )
    reasoning_layout = QtWidgets.QVBoxLayout(reasoning_group)
    reasoning_layout.setContentsMargins(0, 0, 0, 0)
    panel.explain_panel = SuggestionExplainPanel(parent=reasoning_group)
    reasoning_layout.addWidget(panel.explain_panel)
    advanced_layout.addWidget(reasoning_group)
