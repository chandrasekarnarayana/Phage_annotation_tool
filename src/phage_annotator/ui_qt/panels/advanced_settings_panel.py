"""Compact right-dock panel for infrequent expert settings."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class AdvancedSettingsPanel(QtWidgets.QWidget):
    """Right-side expert settings for calibration and infrequent controls."""

    pixel_size_changed = QtCore.Signal(float)
    axis_mode_changed = QtCore.Signal(str)
    open_metadata_requested = QtCore.Signal()
    open_preferences_requested = QtCore.Signal()
    retry_project_relink_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        self.setObjectName("advanced_settings_panel")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        title = QtWidgets.QLabel("Advanced Settings")
        title.setStyleSheet("font-weight: 600;")
        root.addWidget(title)

        image_group = QtWidgets.QGroupBox("Current Image")
        image_form = QtWidgets.QFormLayout(image_group)
        image_form.setContentsMargins(8, 8, 8, 8)
        self.image_name_lbl = QtWidgets.QLabel("-")
        self.image_name_lbl.setWordWrap(True)
        self.effective_pixel_lbl = QtWidgets.QLabel("-")
        self.pixel_source_lbl = QtWidgets.QLabel("-")
        self.pixel_source_lbl.setWordWrap(True)
        image_form.addRow("Image", self.image_name_lbl)
        image_form.addRow("Effective pixel size", self.effective_pixel_lbl)
        image_form.addRow("Source", self.pixel_source_lbl)
        root.addWidget(image_group)

        calib_group = QtWidgets.QGroupBox("Calibration")
        calib_form = QtWidgets.QFormLayout(calib_group)
        calib_form.setContentsMargins(8, 8, 8, 8)
        self.pixel_size_spin = QtWidgets.QDoubleSpinBox(calib_group)
        self.pixel_size_spin.setRange(0.000001, 1000.0)
        self.pixel_size_spin.setDecimals(6)
        self.pixel_size_spin.setSingleStep(0.001)
        self.pixel_size_spin.setSuffix(" um/px")
        self.pixel_size_spin.setToolTip("Default pixel size used when image metadata is missing or overridden.")
        self.axis_mode_combo = QtWidgets.QComboBox(calib_group)
        self.axis_mode_combo.addItems(["auto", "time", "depth"])
        self.axis_mode_combo.setToolTip("Interpretation of the 3D axis for the active image.")
        calib_form.addRow("Default pixel size", self.pixel_size_spin)
        calib_form.addRow("3D axis mode", self.axis_mode_combo)
        root.addWidget(calib_group)

        access_group = QtWidgets.QGroupBox("More")
        access_layout = QtWidgets.QVBoxLayout(access_group)
        access_layout.setContentsMargins(8, 8, 8, 8)
        access_layout.setSpacing(6)
        self.open_metadata_btn = QtWidgets.QPushButton("Open Metadata")
        self.open_preferences_btn = QtWidgets.QPushButton("Open Preferences")
        access_layout.addWidget(self.open_metadata_btn)
        access_layout.addWidget(self.open_preferences_btn)
        root.addWidget(access_group)

        relink_group = QtWidgets.QGroupBox("Project Relink")
        relink_layout = QtWidgets.QVBoxLayout(relink_group)
        relink_layout.setContentsMargins(8, 8, 8, 8)
        relink_layout.setSpacing(6)
        self.relink_summary_lbl = QtWidgets.QLabel("No relink activity.")
        self.relink_summary_lbl.setWordWrap(True)
        relink_layout.addWidget(self.relink_summary_lbl)
        relink_btn_row = QtWidgets.QHBoxLayout()
        self.retry_auto_relink_btn = QtWidgets.QPushButton("Retry Auto")
        self.retry_manual_relink_btn = QtWidgets.QPushButton("Manual Link")
        relink_btn_row.addWidget(self.retry_auto_relink_btn)
        relink_btn_row.addWidget(self.retry_manual_relink_btn)
        relink_layout.addLayout(relink_btn_row)
        root.addWidget(relink_group)
        root.addStretch(1)

        self.pixel_size_spin.valueChanged.connect(self.pixel_size_changed.emit)
        self.axis_mode_combo.currentTextChanged.connect(self.axis_mode_changed.emit)
        self.open_metadata_btn.clicked.connect(self.open_metadata_requested.emit)
        self.open_preferences_btn.clicked.connect(self.open_preferences_requested.emit)
        self.retry_auto_relink_btn.clicked.connect(lambda: self.retry_project_relink_requested.emit("auto"))
        self.retry_manual_relink_btn.clicked.connect(lambda: self.retry_project_relink_requested.emit("manual"))

    def set_state(
        self,
        *,
        image_name: str,
        effective_pixel_size_um: float | None,
        pixel_source: str,
        default_pixel_size_um: float,
        axis_mode: str,
        relink_summary: str = "No relink activity.",
        relink_retry_enabled: bool = False,
    ) -> None:
        """Refresh panel values from the active window/session state."""
        self.image_name_lbl.setText(str(image_name or "-"))
        if effective_pixel_size_um and effective_pixel_size_um > 0:
            self.effective_pixel_lbl.setText(f"{float(effective_pixel_size_um):.6f} um/px")
        else:
            self.effective_pixel_lbl.setText("unknown")
        self.pixel_source_lbl.setText(str(pixel_source or "-"))

        self.pixel_size_spin.blockSignals(True)
        self.pixel_size_spin.setValue(max(0.000001, float(default_pixel_size_um or 0.069)))
        self.pixel_size_spin.blockSignals(False)

        idx = self.axis_mode_combo.findText(str(axis_mode or "auto").strip().lower())
        self.axis_mode_combo.blockSignals(True)
        if idx >= 0:
            self.axis_mode_combo.setCurrentIndex(idx)
        self.axis_mode_combo.blockSignals(False)
        self.relink_summary_lbl.setText(str(relink_summary or "No relink activity."))
        self.retry_auto_relink_btn.setEnabled(bool(relink_retry_enabled))
        self.retry_manual_relink_btn.setEnabled(bool(relink_retry_enabled))
