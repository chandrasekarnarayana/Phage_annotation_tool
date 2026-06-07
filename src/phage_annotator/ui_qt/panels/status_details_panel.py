"""Right-dock status details panel for overflow operational context."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class StatusDetailsPanel(QtWidgets.QWidget):
    """Compact, structured status details that don't fit in the bottom status bar."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self.setObjectName("status_details_panel")
        self.setStyleSheet(
            "#status_details_panel QGroupBox { margin-top: 8px; }"
            "#status_details_panel QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; }"
            "#status_details_panel QLabel { padding: 1px 0; }"
        )
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        title = QtWidgets.QLabel("Status Details")
        title.setStyleSheet("font-weight: 600;")
        root.addWidget(title)

        context_group = QtWidgets.QGroupBox("Annotation Context")
        context_form = QtWidgets.QFormLayout(context_group)
        context_form.setContentsMargins(8, 8, 8, 8)
        context_form.setHorizontalSpacing(10)
        context_form.setVerticalSpacing(6)
        context_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.dataset_lbl = QtWidgets.QLabel("-")
        self.tz_lbl = QtWidgets.QLabel("-")
        self.scope_lbl = QtWidgets.QLabel("-")
        self.target_lbl = QtWidgets.QLabel("-")
        self.sync_group_lbl = QtWidgets.QLabel("-")
        self.sync_modes_lbl = QtWidgets.QLabel("-")
        self.write_mode_lbl = QtWidgets.QLabel("-")
        self.write_context_lbl = QtWidgets.QLabel("-")
        self.write_context_lbl.setWordWrap(True)
        self.binding_lbl = QtWidgets.QLabel("-")
        self.binding_lbl.setWordWrap(True)
        self.modality_lbl = QtWidgets.QLabel("-")
        self.label_lbl = QtWidgets.QLabel("-")
        context_form.addRow("Dataset", self.dataset_lbl)
        context_form.addRow("T/Z", self.tz_lbl)
        context_form.addRow("Scope", self.scope_lbl)
        context_form.addRow("Target", self.target_lbl)
        context_form.addRow("Sync Group", self.sync_group_lbl)
        context_form.addRow("Sync Modes", self.sync_modes_lbl)
        context_form.addRow("Write Mode", self.write_mode_lbl)
        context_form.addRow("Context Key", self.write_context_lbl)
        context_form.addRow("Bound File", self.binding_lbl)
        context_form.addRow("Modality", self.modality_lbl)
        context_form.addRow("Label", self.label_lbl)
        root.addWidget(context_group)

        assist_group = QtWidgets.QGroupBox("Assist and QC")
        assist_form = QtWidgets.QFormLayout(assist_group)
        assist_form.setContentsMargins(8, 8, 8, 8)
        assist_form.setHorizontalSpacing(10)
        assist_form.setVerticalSpacing(6)
        assist_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
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
        system_form.setHorizontalSpacing(10)
        system_form.setVerticalSpacing(6)
        system_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
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
