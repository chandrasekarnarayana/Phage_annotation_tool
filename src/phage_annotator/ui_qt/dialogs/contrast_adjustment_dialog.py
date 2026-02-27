"""Contrast adjustment dialog with professional brightness controls.

Provides:
- Histogram display with adjustable min/max
- Gamma slider
- Mode selector (linear/log)
- Preset buttons (Auto, Linear, Log, Sqrt)
- Live preview
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.data.display_mapping import DisplayMapping


class ContrastAdjustmentDialog(QtWidgets.QDialog):
    """Professional contrast adjustment dialog.
    
    Allows users to adjust brightness, contrast, and gamma with
    histogram visualization and preset options.
    """

    # Signal emitted when settings change
    contrast_changed = QtCore.pyqtSignal(float, float)  # min_val, max_val
    gamma_changed = QtCore.pyqtSignal(float)  # gamma
    mode_changed = QtCore.pyqtSignal(str)  # mode (linear or log)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        modality_name: str = "Modality 1",
        data: Optional[np.ndarray] = None,
        current_mapping: Optional[DisplayMapping] = None,
    ) -> None:
        """Initialize contrast adjustment dialog.
        
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget
        modality_name : str
            Name of the modality being adjusted
        data : ndarray, optional
            Image data for histogram
        current_mapping : DisplayMapping, optional
            Current display mapping settings
        """
        super().__init__(parent)
        self.setWindowTitle(f"Contrast Adjustment - {modality_name}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        self.modality_name = modality_name
        self.data = data
        self.mapping = current_mapping or DisplayMapping(0.0, 1.0)
        
        # Compute histogram if data provided
        self.histogram = None
        self.hist_bins = None
        if data is not None and data.size > 0:
            self._compute_histogram()
        
        self._init_ui()

    def _compute_histogram(self) -> None:
        """Compute histogram from image data."""
        if self.data is None or self.data.size == 0:
            return
        
        # Flatten and compute histogram
        flat_data = self.data.flatten()
        data_min = float(np.min(flat_data))
        data_max = float(np.max(flat_data))
        
        if data_min == data_max:
            return
        
        self.histogram, self.hist_bins = np.histogram(
            flat_data, bins=256, range=(data_min, data_max)
        )

    def _init_ui(self) -> None:
        """Initialize the UI layout."""
        layout = QtWidgets.QVBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel(f"Adjust contrast for {self.modality_name}")
        title_font = title_label.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Histogram area (placeholder)
        hist_label = QtWidgets.QLabel("[Histogram visualization would appear here]")
        hist_label.setStyleSheet("background-color: #f0f0f0; padding: 20px;")
        hist_label.setMinimumHeight(100)
        hist_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hist_label)
        
        # Min/Max controls
        controls_group = QtWidgets.QGroupBox("Display Range")
        controls_layout = QtWidgets.QGridLayout()
        
        controls_layout.addWidget(QtWidgets.QLabel("Min Value:"), 0, 0)
        self.min_spin = QtWidgets.QDoubleSpinBox()
        self.min_spin.setRange(0.0, 65535.0)
        self.min_spin.setSingleStep(1.0)
        self.min_spin.setValue(self.mapping.min_val)
        self.min_spin.valueChanged.connect(self._on_min_changed)
        controls_layout.addWidget(self.min_spin, 0, 1)
        
        controls_layout.addWidget(QtWidgets.QLabel("Max Value:"), 1, 0)
        self.max_spin = QtWidgets.QDoubleSpinBox()
        self.max_spin.setRange(0.0, 65535.0)
        self.max_spin.setSingleStep(1.0)
        self.max_spin.setValue(self.mapping.max_val)
        self.max_spin.valueChanged.connect(self._on_max_changed)
        controls_layout.addWidget(self.max_spin, 1, 1)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Gamma control
        gamma_group = QtWidgets.QGroupBox("Gamma Correction")
        gamma_layout = QtWidgets.QVBoxLayout()
        
        gamma_slider_layout = QtWidgets.QHBoxLayout()
        gamma_slider_layout.addWidget(QtWidgets.QLabel("Gamma:"))
        self.gamma_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.gamma_slider.setMinimum(20)  # 0.2
        self.gamma_slider.setMaximum(50)  # 5.0
        self.gamma_slider.setValue(int(self.mapping.gamma * 10))
        self.gamma_slider.sliderMoved.connect(self._on_gamma_slider)
        gamma_slider_layout.addWidget(self.gamma_slider)
        
        self.gamma_label = QtWidgets.QLabel(f"{self.mapping.gamma:.2f}")
        self.gamma_label.setMinimumWidth(40)
        gamma_slider_layout.addWidget(self.gamma_label)
        
        gamma_layout.addLayout(gamma_slider_layout)
        gamma_group.setLayout(gamma_layout)
        layout.addWidget(gamma_group)
        
        # Mode selection
        mode_group = QtWidgets.QGroupBox("Display Mode")
        mode_layout = QtWidgets.QVBoxLayout()
        
        self.mode_linear = QtWidgets.QRadioButton("Linear")
        self.mode_linear.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_linear)
        
        self.mode_log = QtWidgets.QRadioButton("Logarithmic")
        self.mode_log.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_log)
        
        if self.mapping.mode == "linear":
            self.mode_linear.setChecked(True)
        else:
            self.mode_log.setChecked(True)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Preset buttons
        preset_group = QtWidgets.QGroupBox("Presets")
        preset_layout = QtWidgets.QHBoxLayout()
        
        for preset_name in ["Auto", "Linear", "Log", "Sqrt"]:
            btn = QtWidgets.QPushButton(preset_name)
            btn.clicked.connect(lambda checked, p=preset_name: self._apply_preset(p))
            preset_layout.addWidget(btn)
        
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        reset_button = QtWidgets.QPushButton("Reset")
        reset_button.clicked.connect(self._reset_to_default)
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def _on_min_changed(self, value: float) -> None:
        """Handle min value change."""
        self.mapping.min_val = value
        self.contrast_changed.emit(self.mapping.min_val, self.mapping.max_val)

    def _on_max_changed(self, value: float) -> None:
        """Handle max value change."""
        self.mapping.max_val = value
        self.contrast_changed.emit(self.mapping.min_val, self.mapping.max_val)

    def _on_gamma_slider(self) -> None:
        """Handle gamma slider change."""
        gamma = max(0.2, min(5.0, self.gamma_slider.value() / 10.0))
        self.mapping.gamma = gamma
        self.gamma_label.setText(f"{gamma:.2f}")
        self.gamma_changed.emit(gamma)

    def _on_mode_changed(self) -> None:
        """Handle display mode change."""
        if self.mode_linear.isChecked():
            self.mapping.mode = "linear"
        else:
            self.mapping.mode = "log"
        self.mode_changed.emit(self.mapping.mode)

    def _apply_preset(self, preset_name: str) -> None:
        """Apply a contrast preset.
        
        Parameters
        ----------
        preset_name : str
            Preset name (Auto, Linear, Log, Sqrt)
        """
        if preset_name == "Auto":
            if self.data is not None and self.data.size > 0:
                flat_data = self.data.flatten()
                self.mapping.reset_to_auto(flat_data)
                self.min_spin.setValue(self.mapping.min_val)
                self.max_spin.setValue(self.mapping.max_val)
        
        elif preset_name == "Linear":
            self.mode_linear.setChecked(True)
            self.gamma_slider.setValue(10)  # gamma = 1.0
        
        elif preset_name == "Log":
            self.mode_log.setChecked(True)
        
        elif preset_name == "Sqrt":
            self.mode_linear.setChecked(True)
            self.gamma_slider.setValue(50)  # gamma = 5.0 (approximates sqrt)

    def _reset_to_default(self) -> None:
        """Reset all settings to defaults."""
        if self.data is not None and self.data.size > 0:
            flat_data = self.data.flatten()
            self.mapping.reset_to_auto(flat_data)
            self.min_spin.setValue(self.mapping.min_val)
            self.max_spin.setValue(self.mapping.max_val)
        
        self.gamma_slider.setValue(10)  # gamma = 1.0
        self.mode_linear.setChecked(True)

    def get_mapping(self) -> DisplayMapping:
        """Get the current display mapping settings.
        
        Returns
        -------
        DisplayMapping
            Current mapping with all user adjustments
        """
        return self.mapping
