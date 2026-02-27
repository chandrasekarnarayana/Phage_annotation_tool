"""Explainability panel for assisted suggestion trust cues."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class SuggestionExplainPanel(QtWidgets.QWidget):
    """Panel showing why the current suggestion was proposed."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.header_lbl = QtWidgets.QLabel("Why Was This Suggested?")
        self.header_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.header_lbl)
        self.assist_state_lbl = QtWidgets.QLabel("Assist: Heuristic")
        self.assist_state_lbl.setStyleSheet("font-weight: 600; color: #9e9e9e;")
        layout.addWidget(self.assist_state_lbl)

        self.coords_lbl = QtWidgets.QLabel("(x=-, y=-, t=-, z=-)")
        self.score_lbl = QtWidgets.QLabel("generator score: n/a")
        self.calib_lbl = QtWidgets.QLabel("calibrated p_accept: n/a")
        self.nn_lbl = QtWidgets.QLabel("nearest accepted distance: n/a")
        self.stale_lbl = QtWidgets.QLabel("staleness: n/a")
        layout.addWidget(self.coords_lbl)
        layout.addWidget(self.score_lbl)
        layout.addWidget(self.calib_lbl)
        layout.addWidget(self.nn_lbl)
        layout.addWidget(self.stale_lbl)

        comp_group = QtWidgets.QGroupBox("Score Components")
        comp_layout = QtWidgets.QVBoxLayout(comp_group)
        comp_layout.setContentsMargins(8, 8, 8, 8)
        self.components_txt = QtWidgets.QPlainTextEdit()
        self.components_txt.setReadOnly(True)
        self.components_txt.setMaximumBlockCount(200)
        comp_layout.addWidget(self.components_txt)
        layout.addWidget(comp_group)

        patch_group = QtWidgets.QGroupBox("Local Patch Preview")
        patch_layout = QtWidgets.QVBoxLayout(patch_group)
        patch_layout.setContentsMargins(8, 8, 8, 8)
        self.patch_lbl = QtWidgets.QLabel("No suggestion selected.")
        self.patch_lbl.setMinimumHeight(140)
        self.patch_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        patch_layout.addWidget(self.patch_lbl)
        layout.addWidget(patch_group)
        layout.addStretch(1)
