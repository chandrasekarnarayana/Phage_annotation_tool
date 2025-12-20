"""Qt widget for Deep-STORM inference controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


@dataclass
class DeepStormUiValues:
    """Snapshot of Deep-STORM parameter values from the UI."""

    model_path: str
    patch_size: int
    overlap: int
    upsample: int
    sigma_px: float
    normalize_mode: str
    output_mode: str
    window_size: int
    aggregation_mode: str


class DeepStormDockWidget(QtWidgets.QWidget):
    """Parameter panel for Deep-STORM inference."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        model_row = QtWidgets.QHBoxLayout()
        self.model_path_edit = QtWidgets.QLineEdit()
        self.browse_btn = QtWidgets.QToolButton()
        self.browse_btn.setText("…")
        model_row.addWidget(self.model_path_edit)
        model_row.addWidget(self.browse_btn)
        layout.addWidget(QtWidgets.QLabel("Model (.pt)"))
        layout.addLayout(model_row)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        layout.addLayout(form)

        self.patch_combo = QtWidgets.QComboBox()
        self.patch_combo.addItems(["64", "96", "128"])
        self.patch_combo.setCurrentText("64")
        form.addRow("Patch size", self.patch_combo)

        self.overlap_spin = QtWidgets.QSpinBox()
        self.overlap_spin.setRange(0, 64)
        self.overlap_spin.setValue(16)
        form.addRow("Overlap", self.overlap_spin)

        self.upsample_spin = QtWidgets.QSpinBox()
        self.upsample_spin.setRange(2, 16)
        self.upsample_spin.setValue(8)
        form.addRow("Upsample", self.upsample_spin)

        self.sigma_spin = QtWidgets.QDoubleSpinBox()
        self.sigma_spin.setRange(1.0, 1.8)
        self.sigma_spin.setDecimals(2)
        self.sigma_spin.setValue(1.3)
        form.addRow("Sigma (px)", self.sigma_spin)

        self.normalize_combo = QtWidgets.QComboBox()
        self.normalize_combo.addItems(["per_patch", "global_roi"])
        form.addRow("Normalize", self.normalize_combo)

        self.output_combo = QtWidgets.QComboBox()
        self.output_combo.addItems(["sr_image", "density_map"])
        form.addRow("Output mode", self.output_combo)

        self.window_spin = QtWidgets.QSpinBox()
        self.window_spin.setRange(1, 9)
        self.window_spin.setValue(5)
        form.addRow("Window size", self.window_spin)

        self.agg_combo = QtWidgets.QComboBox()
        self.agg_combo.addItems(["mean", "stack"])
        form.addRow("Aggregation", self.agg_combo)

        btn_row = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run Deep-STORM")
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

        export_row = QtWidgets.QHBoxLayout()
        self.export_csv_btn = QtWidgets.QPushButton("Export CSV")
        self.export_sr_btn = QtWidgets.QPushButton("Export SR Image")
        self.add_ann_btn = QtWidgets.QPushButton("Add to Annotations")
        export_row.addWidget(self.export_csv_btn)
        export_row.addWidget(self.export_sr_btn)
        export_row.addWidget(self.add_ann_btn)
        layout.addLayout(export_row)

        layout.addStretch(1)

    def values(self) -> DeepStormUiValues:
        """Return a typed snapshot of the current UI values."""
        return DeepStormUiValues(
            model_path=str(self.model_path_edit.text()).strip(),
            patch_size=int(self.patch_combo.currentText()),
            overlap=int(self.overlap_spin.value()),
            upsample=int(self.upsample_spin.value()),
            sigma_px=float(self.sigma_spin.value()),
            normalize_mode=str(self.normalize_combo.currentText()),
            output_mode=str(self.output_combo.currentText()),
            window_size=int(self.window_spin.value()),
            aggregation_mode=str(self.agg_combo.currentText()),
        )
