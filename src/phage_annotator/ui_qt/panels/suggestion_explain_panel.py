"""Explainability panel for assisted suggestion trust cues."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class SuggestionExplainPanel(QtWidgets.QWidget):
    """Panel showing why the current suggestion was proposed."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("suggestion_explain_panel")
        self.setStyleSheet(
            "#suggestion_explain_panel QGroupBox { margin-top: 8px; }"
            "#suggestion_explain_panel QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.header_lbl = QtWidgets.QLabel("Why Was This Suggested?")
        self.header_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.header_lbl)
        self.assist_state_lbl = QtWidgets.QLabel("Assist: Heuristic")
        self.assist_state_lbl.setStyleSheet("font-weight: 600; color: #9e9e9e;")
        layout.addWidget(self.assist_state_lbl)

        self.coords_lbl = QtWidgets.QLabel("(x=-, y=-, t=-, z=-)")
        self.score_lbl = QtWidgets.QLabel("generator score: n/a")
        self.calib_lbl = QtWidgets.QLabel("Acceptance likelihood (p_accept): n/a")
        self.calib_lbl.setToolTip(
            "Acceptance likelihood (p_accept) predicts your acceptance behavior, "
            "not ground-truth correctness."
        )
        self.nn_lbl = QtWidgets.QLabel("nearest accepted distance: n/a")
        self.stale_lbl = QtWidgets.QLabel("staleness: n/a")
        self.coords_lbl.setWordWrap(True)
        self.score_lbl.setWordWrap(True)
        self.calib_lbl.setWordWrap(True)
        self.nn_lbl.setWordWrap(True)
        self.stale_lbl.setWordWrap(True)
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
        self.components_txt.setMinimumHeight(110)
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
