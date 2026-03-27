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

        self.header_lbl = QtWidgets.QLabel("Assist Details")
        self.header_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.header_lbl)
        self.assist_state_lbl = QtWidgets.QLabel("Assist: Heuristic")
        self.assist_state_lbl.setStyleSheet("font-weight: 600; color: #9e9e9e;")
        layout.addWidget(self.assist_state_lbl)

        summary_group = QtWidgets.QGroupBox("Summary")
        summary_layout = QtWidgets.QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(8, 8, 8, 8)
        self.coords_lbl = QtWidgets.QLabel("(x=-, y=-, t=-, z=-)")
        self.class_lbl = QtWidgets.QLabel("class: n/a")
        self.score_lbl = QtWidgets.QLabel("generator score: n/a")
        self.calib_lbl = QtWidgets.QLabel("Acceptance likelihood (p_accept): n/a")
        self.uncertainty_lbl = QtWidgets.QLabel("uncertainty: n/a")
        self.calib_lbl.setToolTip(
            "Acceptance likelihood (p_accept) predicts your acceptance behavior, "
            "not ground-truth correctness."
        )
        for widget in (self.coords_lbl, self.class_lbl, self.score_lbl, self.calib_lbl, self.uncertainty_lbl):
            widget.setWordWrap(True)
            summary_layout.addWidget(widget)
        layout.addWidget(summary_group)

        nearest_group = QtWidgets.QGroupBox("Nearest Truth")
        nearest_layout = QtWidgets.QVBoxLayout(nearest_group)
        nearest_layout.setContentsMargins(8, 8, 8, 8)
        self.nn_lbl = QtWidgets.QLabel("nearest accepted distance: n/a")
        self.label_match_lbl = QtWidgets.QLabel("label match: n/a")
        self.nn_lbl.setWordWrap(True)
        self.label_match_lbl.setWordWrap(True)
        nearest_layout.addWidget(self.nn_lbl)
        nearest_layout.addWidget(self.label_match_lbl)
        layout.addWidget(nearest_group)

        context_group = QtWidgets.QGroupBox("Context")
        context_layout = QtWidgets.QVBoxLayout(context_group)
        context_layout.setContentsMargins(8, 8, 8, 8)
        self.context_lbl = QtWidgets.QLabel("confidence mode: heuristic")
        self.stale_lbl = QtWidgets.QLabel("staleness: n/a")
        self.modality_lbl = QtWidgets.QLabel("modality evidence: n/a")
        self.control_lbl = QtWidgets.QLabel("control contradiction: n/a")
        self.context_lbl.setWordWrap(True)
        self.stale_lbl.setWordWrap(True)
        self.modality_lbl.setWordWrap(True)
        self.control_lbl.setWordWrap(True)
        context_layout.addWidget(self.context_lbl)
        context_layout.addWidget(self.stale_lbl)
        context_layout.addWidget(self.modality_lbl)
        context_layout.addWidget(self.control_lbl)
        layout.addWidget(context_group)

        comp_group = QtWidgets.QGroupBox("Features")
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
