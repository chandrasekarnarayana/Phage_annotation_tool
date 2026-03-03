"""Right-dock status details panel for overflow operational context."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets


class StatusDetailsPanel(QtWidgets.QWidget):
    """Compact, structured status details that don't fit in the bottom status bar."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QtWidgets.QLabel("Status Details")
        title.setStyleSheet("font-weight: 600;")
        root.addWidget(title)

        context_group = QtWidgets.QGroupBox("Annotation Context")
        context_form = QtWidgets.QFormLayout(context_group)
        context_form.setContentsMargins(8, 8, 8, 8)
        self.dataset_lbl = QtWidgets.QLabel("-")
        self.tz_lbl = QtWidgets.QLabel("-")
        self.scope_lbl = QtWidgets.QLabel("-")
        self.target_lbl = QtWidgets.QLabel("-")
        self.modality_lbl = QtWidgets.QLabel("-")
        self.label_lbl = QtWidgets.QLabel("-")
        context_form.addRow("Dataset", self.dataset_lbl)
        context_form.addRow("T/Z", self.tz_lbl)
        context_form.addRow("Scope", self.scope_lbl)
        context_form.addRow("Target", self.target_lbl)
        context_form.addRow("Modality", self.modality_lbl)
        context_form.addRow("Label", self.label_lbl)
        root.addWidget(context_group)

        assist_group = QtWidgets.QGroupBox("Assist and QC")
        assist_form = QtWidgets.QFormLayout(assist_group)
        assist_form.setContentsMargins(8, 8, 8, 8)
        self.assist_lbl = QtWidgets.QLabel("-")
        self.context_lbl = QtWidgets.QLabel("-")
        self.context_lbl.setWordWrap(True)
        self.suggestions_lbl = QtWidgets.QLabel("-")
        self.qc_lbl = QtWidgets.QLabel("-")
        self.results_lbl = QtWidgets.QLabel("-")
        assist_form.addRow("Assist", self.assist_lbl)
        assist_form.addRow("Context", self.context_lbl)
        assist_form.addRow("Suggestions", self.suggestions_lbl)
        assist_form.addRow("QC", self.qc_lbl)
        assist_form.addRow("Results", self.results_lbl)
        root.addWidget(assist_group)

        system_group = QtWidgets.QGroupBox("System")
        system_form = QtWidgets.QFormLayout(system_group)
        system_form.setContentsMargins(8, 8, 8, 8)
        self.points_lbl = QtWidgets.QLabel("-")
        self.roi_area_lbl = QtWidgets.QLabel("-")
        self.density_lbl = QtWidgets.QLabel("-")
        self.fps_lbl = QtWidgets.QLabel("-")
        self.autosave_lbl = QtWidgets.QLabel("-")
        self.cache_lbl = QtWidgets.QLabel("-")
        self.jobs_lbl = QtWidgets.QLabel("-")
        self.diag_lbl = QtWidgets.QLabel("-")
        self.diag_lbl.setWordWrap(True)
        system_form.addRow("Points", self.points_lbl)
        system_form.addRow("ROI area", self.roi_area_lbl)
        system_form.addRow("Density", self.density_lbl)
        system_form.addRow("Playback", self.fps_lbl)
        system_form.addRow("Autosave", self.autosave_lbl)
        system_form.addRow("Cache", self.cache_lbl)
        system_form.addRow("Jobs", self.jobs_lbl)
        system_form.addRow("Diagnostics", self.diag_lbl)
        root.addWidget(system_group)
        root.addStretch(1)
