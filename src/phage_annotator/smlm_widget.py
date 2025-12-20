"""Qt widget for ThunderSTORM-style SMLM controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


@dataclass
class SmlmUiValues:
    """Snapshot of SMLM parameter values from the UI."""

    sigma_px: float
    fit_radius_px: int
    filter_type: str
    dog_sigma1: float
    dog_sigma2: float
    detection_thr_sigma: float
    max_candidates_per_frame: int
    merge_radius_px: float
    min_photons: float
    max_uncertainty_nm: float
    upsample: int
    render_mode: str
    render_sigma_nm: float


class SmlmDockWidget(QtWidgets.QWidget):
    """Parameter panel for the ThunderSTORM-style pipeline."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        layout.addLayout(form)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["wavelet_bspline", "dog"])
        form.addRow("Filter", self.filter_combo)

        self.sigma_spin = QtWidgets.QDoubleSpinBox()
        self.sigma_spin.setRange(0.4, 6.0)
        self.sigma_spin.setDecimals(2)
        self.sigma_spin.setValue(1.3)
        form.addRow("Sigma (px)", self.sigma_spin)

        self.fit_radius_spin = QtWidgets.QSpinBox()
        self.fit_radius_spin.setRange(2, 12)
        self.fit_radius_spin.setValue(4)
        form.addRow("Fit radius (px)", self.fit_radius_spin)

        self.dog_sigma1_spin = QtWidgets.QDoubleSpinBox()
        self.dog_sigma1_spin.setRange(0.5, 5.0)
        self.dog_sigma1_spin.setDecimals(2)
        self.dog_sigma1_spin.setValue(1.0)
        form.addRow("DoG sigma1", self.dog_sigma1_spin)

        self.dog_sigma2_spin = QtWidgets.QDoubleSpinBox()
        self.dog_sigma2_spin.setRange(0.8, 8.0)
        self.dog_sigma2_spin.setDecimals(2)
        self.dog_sigma2_spin.setValue(2.0)
        form.addRow("DoG sigma2", self.dog_sigma2_spin)

        self.det_thr_spin = QtWidgets.QDoubleSpinBox()
        self.det_thr_spin.setRange(0.5, 10.0)
        self.det_thr_spin.setDecimals(2)
        self.det_thr_spin.setValue(3.0)
        form.addRow("Threshold (MAD σ)", self.det_thr_spin)

        self.max_candidates_spin = QtWidgets.QSpinBox()
        self.max_candidates_spin.setRange(100, 20000)
        self.max_candidates_spin.setValue(5000)
        form.addRow("Max candidates", self.max_candidates_spin)

        self.merge_radius_spin = QtWidgets.QDoubleSpinBox()
        self.merge_radius_spin.setRange(0.0, 5.0)
        self.merge_radius_spin.setDecimals(2)
        self.merge_radius_spin.setValue(1.0)
        form.addRow("Merge radius (px)", self.merge_radius_spin)

        self.min_photons_spin = QtWidgets.QDoubleSpinBox()
        self.min_photons_spin.setRange(0.0, 10000.0)
        self.min_photons_spin.setDecimals(1)
        self.min_photons_spin.setValue(50.0)
        form.addRow("Min photons", self.min_photons_spin)

        self.max_uncertainty_spin = QtWidgets.QDoubleSpinBox()
        self.max_uncertainty_spin.setRange(1.0, 200.0)
        self.max_uncertainty_spin.setDecimals(1)
        self.max_uncertainty_spin.setValue(30.0)
        form.addRow("Max uncertainty (nm)", self.max_uncertainty_spin)

        self.upsample_spin = QtWidgets.QSpinBox()
        self.upsample_spin.setRange(2, 16)
        self.upsample_spin.setValue(8)
        form.addRow("Upsample", self.upsample_spin)

        self.render_combo = QtWidgets.QComboBox()
        self.render_combo.addItems(["histogram", "gaussian"])
        form.addRow("Render mode", self.render_combo)

        self.render_sigma_spin = QtWidgets.QDoubleSpinBox()
        self.render_sigma_spin.setRange(1.0, 100.0)
        self.render_sigma_spin.setDecimals(1)
        self.render_sigma_spin.setValue(10.0)
        form.addRow("Render sigma (nm)", self.render_sigma_spin)

        btn_row = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run SMLM (ROI)")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)

        color_row = QtWidgets.QHBoxLayout()
        color_row.addWidget(QtWidgets.QLabel("Color by"))
        self.color_mode_combo = QtWidgets.QComboBox()
        self.color_mode_combo.addItems(["Photons", "Uncertainty"])
        color_row.addWidget(self.color_mode_combo)
        color_row.addStretch(1)
        layout.addLayout(color_row)

        export_row = QtWidgets.QHBoxLayout()
        self.export_csv_btn = QtWidgets.QPushButton("Export CSV")
        self.export_h5_btn = QtWidgets.QPushButton("Export HDF5")
        self.add_ann_btn = QtWidgets.QPushButton("Add to Annotations")
        export_row.addWidget(self.export_csv_btn)
        export_row.addWidget(self.export_h5_btn)
        export_row.addWidget(self.add_ann_btn)
        layout.addLayout(export_row)

        layout.addStretch(1)

    def values(self) -> SmlmUiValues:
        """Return a typed snapshot of the current UI values."""
        return SmlmUiValues(
            sigma_px=float(self.sigma_spin.value()),
            fit_radius_px=int(self.fit_radius_spin.value()),
            filter_type=str(self.filter_combo.currentText()),
            dog_sigma1=float(self.dog_sigma1_spin.value()),
            dog_sigma2=float(self.dog_sigma2_spin.value()),
            detection_thr_sigma=float(self.det_thr_spin.value()),
            max_candidates_per_frame=int(self.max_candidates_spin.value()),
            merge_radius_px=float(self.merge_radius_spin.value()),
            min_photons=float(self.min_photons_spin.value()),
            max_uncertainty_nm=float(self.max_uncertainty_spin.value()),
            upsample=int(self.upsample_spin.value()),
            render_mode=str(self.render_combo.currentText()),
            render_sigma_nm=float(self.render_sigma_spin.value()),
        )
