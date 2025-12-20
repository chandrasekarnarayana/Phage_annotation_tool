"""Qt panel for Fiji-style thresholding controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.thresholding import AUTO_METHODS


@dataclass
class ThresholdUiValues:
    """Snapshot of thresholding controls."""

    target: str
    region_roi: bool
    scope: str
    sample_count: int
    method: str
    manual_low_pct: int
    manual_high_pct: int
    invert_mask: bool
    background: str
    smooth_sigma: float
    preview: bool
    min_area_px: int
    fill_holes: bool
    open_radius_px: int
    close_radius_px: int
    despeckle: bool
    watershed_split: bool


class ThresholdPanel(QtWidgets.QWidget):
    """Threshold control panel with preview and post-processing."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        layout.addLayout(form)

        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.addItems(["Frame", "Mean", "Composite", "Support"])
        form.addRow("Target", self.target_combo)

        self.region_chk = QtWidgets.QCheckBox("ROI only")
        self.region_chk.setChecked(True)
        form.addRow("Region", self.region_chk)

        self.scope_combo = QtWidgets.QComboBox()
        self.scope_combo.addItems(["Current slice", "Sampled stack"])
        form.addRow("Scope", self.scope_combo)

        self.sample_spin = QtWidgets.QSpinBox()
        self.sample_spin.setRange(2, 200)
        self.sample_spin.setValue(20)
        form.addRow("Sample frames", self.sample_spin)

        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.addItems(["Manual"] + AUTO_METHODS)
        form.addRow("Method", self.method_combo)

        manual_box = QtWidgets.QGroupBox("Manual threshold (percentiles)")
        manual_layout = QtWidgets.QGridLayout(manual_box)
        self.low_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.low_slider.setRange(0, 100)
        self.low_slider.setValue(20)
        self.high_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.high_slider.setRange(0, 100)
        self.high_slider.setValue(99)
        self.low_label = QtWidgets.QLabel("Low: 20%")
        self.high_label = QtWidgets.QLabel("High: 99%")
        manual_layout.addWidget(self.low_label, 0, 0)
        manual_layout.addWidget(self.low_slider, 0, 1)
        manual_layout.addWidget(self.high_label, 1, 0)
        manual_layout.addWidget(self.high_slider, 1, 1)
        layout.addWidget(manual_box)

        auto_row = QtWidgets.QHBoxLayout()
        self.auto_btn = QtWidgets.QPushButton("Auto")
        self.auto_value = QtWidgets.QLabel("Auto: —")
        auto_row.addWidget(self.auto_btn)
        auto_row.addWidget(self.auto_value)
        auto_row.addStretch(1)
        layout.addLayout(auto_row)

        opts_box = QtWidgets.QGroupBox("Options")
        opts_layout = QtWidgets.QFormLayout(opts_box)
        self.invert_chk = QtWidgets.QCheckBox("Invert mask")
        self.preview_chk = QtWidgets.QCheckBox("Preview overlay")
        self.preview_chk.setChecked(True)
        self.background_combo = QtWidgets.QComboBox()
        self.background_combo.addItems(["dark", "bright"])
        self.smooth_spin = QtWidgets.QDoubleSpinBox()
        self.smooth_spin.setRange(0.0, 2.0)
        self.smooth_spin.setDecimals(2)
        self.smooth_spin.setValue(0.0)
        opts_layout.addRow(self.invert_chk)
        opts_layout.addRow("Background", self.background_combo)
        opts_layout.addRow("Smooth (sigma px)", self.smooth_spin)
        opts_layout.addRow(self.preview_chk)
        layout.addWidget(opts_box)

        post_box = QtWidgets.QGroupBox("Postprocess")
        post_layout = QtWidgets.QFormLayout(post_box)
        self.min_area_spin = QtWidgets.QSpinBox()
        self.min_area_spin.setRange(0, 10000)
        self.min_area_spin.setValue(5)
        self.fill_holes_chk = QtWidgets.QCheckBox("Fill holes")
        self.open_spin = QtWidgets.QSpinBox()
        self.open_spin.setRange(0, 5)
        self.open_spin.setValue(1)
        self.close_spin = QtWidgets.QSpinBox()
        self.close_spin.setRange(0, 5)
        self.close_spin.setValue(1)
        self.despeckle_chk = QtWidgets.QCheckBox("Despeckle")
        self.watershed_chk = QtWidgets.QCheckBox("Watershed split")
        post_layout.addRow("Min area (px)", self.min_area_spin)
        post_layout.addRow(self.fill_holes_chk)
        post_layout.addRow("Open radius", self.open_spin)
        post_layout.addRow("Close radius", self.close_spin)
        post_layout.addRow(self.despeckle_chk)
        post_layout.addRow(self.watershed_chk)
        layout.addWidget(post_box)

        btn_row = QtWidgets.QHBoxLayout()
        self.create_mask_btn = QtWidgets.QPushButton("Create mask layer")
        self.create_roi_btn = QtWidgets.QPushButton("Create ROI from mask")
        self.analyze_btn = QtWidgets.QPushButton("Analyze Particles…")
        self.apply_btn = QtWidgets.QPushButton("Apply (Destructive)")
        btn_row.addWidget(self.create_mask_btn)
        btn_row.addWidget(self.create_roi_btn)
        btn_row.addWidget(self.analyze_btn)
        btn_row.addWidget(self.apply_btn)
        layout.addLayout(btn_row)

        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.low_slider.valueChanged.connect(self._sync_labels)
        self.high_slider.valueChanged.connect(self._sync_labels)
        self._sync_labels()
        self._apply_tooltips()

    def values(self) -> ThresholdUiValues:
        """Return a typed snapshot of current UI values."""
        return ThresholdUiValues(
            target=self.target_combo.currentText(),
            region_roi=self.region_chk.isChecked(),
            scope=self.scope_combo.currentText(),
            sample_count=int(self.sample_spin.value()),
            method=self.method_combo.currentText(),
            manual_low_pct=int(self.low_slider.value()),
            manual_high_pct=int(self.high_slider.value()),
            invert_mask=self.invert_chk.isChecked(),
            background=self.background_combo.currentText(),
            smooth_sigma=float(self.smooth_spin.value()),
            preview=self.preview_chk.isChecked(),
            min_area_px=int(self.min_area_spin.value()),
            fill_holes=self.fill_holes_chk.isChecked(),
            open_radius_px=int(self.open_spin.value()),
            close_radius_px=int(self.close_spin.value()),
            despeckle=self.despeckle_chk.isChecked(),
            watershed_split=self.watershed_chk.isChecked(),
        )

    def _sync_labels(self) -> None:
        low = int(self.low_slider.value())
        high = int(self.high_slider.value())
        if low > high:
            high = low
            self.high_slider.blockSignals(True)
            self.high_slider.setValue(high)
            self.high_slider.blockSignals(False)
        self.low_label.setText(f"Low: {low}%")
        self.high_label.setText(f"High: {high}%")

    def _apply_tooltips(self) -> None:
        sigma_tip = "sigma_px ≈ FWHM/2.35; start 1.1–1.6 px."
        thr_tip = "Threshold 2–6 sigma."
        fit_tip = "Fit radius 3–5 px."
        self.smooth_spin.setToolTip(sigma_tip)
        self.auto_btn.setToolTip(thr_tip)
        self.low_slider.setToolTip(thr_tip)
        self.high_slider.setToolTip(thr_tip)
        self.open_spin.setToolTip(fit_tip)
