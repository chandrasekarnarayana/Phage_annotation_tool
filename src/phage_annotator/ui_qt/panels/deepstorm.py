"""Qt dock widget for Deep-STORM super-resolution inference.

Provides a parameter panel for loading a trained Deep-STORM PyTorch model
and running tiled super-resolution reconstruction over the active image ROI.
The panel follows the same scientific parameter conventions as the ThunderSTORM
SMLM panel and the ONNX density panel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

logger = logging.getLogger(__name__)


@dataclass
class DeepStormUiValues:
    """Typed snapshot of Deep-STORM parameter values from the UI.

    All pixel-domain values carry the ``_px`` suffix; nanometre-domain values
    carry the ``_nm`` suffix to prevent unit-conversion errors.
    """

    model_path: str
    device: str
    patch_size: int
    overlap: int
    upsample: int
    pixel_size_nm: float
    sigma_px: float
    normalize_mode: str
    output_mode: str
    window_size: int
    aggregation_mode: str
    detection_thr_sigma: float


class DeepStormDockWidget(QtWidgets.QWidget):
    """Parameter panel for Deep-STORM super-resolution inference.

    Supports TorchScript (``.pt``, ``.pth``) and state-dict PyTorch checkpoints.
    Runs tiled patch inference with Hanning-window overlap blending and extracts
    approximate sub-pixel localisation positions from the SR reconstruction.

    Parameters
    ----------
    parent:
        Optional parent Qt widget.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget(scroll)
        scroll.setWidget(container)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        root.addWidget(scroll)

        self._build_model_group(layout)
        self._build_acquisition_group(layout)
        self._build_inference_group(layout)
        self._build_detection_group(layout)
        self._build_run_controls(layout)
        self._build_export_controls(layout)
        self._build_results_group(layout)
        layout.addStretch(1)

    def _build_model_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        grp = QtWidgets.QGroupBox("Model")
        grp.setToolTip(
            "Load a trained Deep-STORM PyTorch model (.pt / .pth).\n"
            "Both TorchScript and state-dict checkpoints are supported."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        model_row = QtWidgets.QHBoxLayout()
        self.model_path_edit = QtWidgets.QLineEdit()
        self.model_path_edit.setPlaceholderText("Path to Deep-STORM model (.pt / .pth)…")
        self.browse_btn = QtWidgets.QToolButton()
        self.browse_btn.setText("…")
        self.browse_btn.setToolTip("Browse for a PyTorch model file.")
        self.browse_btn.clicked.connect(self._browse_model)
        model_row.addWidget(self.model_path_edit)
        model_row.addWidget(self.browse_btn)
        model_widget = QtWidgets.QWidget()
        model_widget.setLayout(model_row)
        model_widget.layout().setContentsMargins(0, 0, 0, 0)
        g.addRow("Model file", model_widget)

        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setToolTip(
            "Inference compute device.\n"
            "auto: selects CUDA if available, otherwise CPU.\n"
            "cpu: forces CPU inference (always available, slower).\n"
            "cuda: NVIDIA GPU via CUDA (fastest; requires PyTorch-CUDA build).\n"
            "mps: Apple Silicon Metal Performance Shaders."
        )
        self.device_combo.addItem("Auto (best available)", "auto")
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.addItem("CUDA (NVIDIA GPU)", "cuda")
        self.device_combo.addItem("MPS (Apple Silicon)", "mps")
        self._populate_devices()
        g.addRow("Device", self.device_combo)

        self.model_status = QtWidgets.QLabel("No model loaded.")
        self.model_status.setWordWrap(True)
        g.addRow("Status", self.model_status)

        layout.addWidget(grp)

    def _build_acquisition_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        grp = QtWidgets.QGroupBox("Acquisition")
        grp.setToolTip("Physical acquisition parameters for converting pixel coordinates to nanometres.")
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.pixel_size_spin = QtWidgets.QDoubleSpinBox()
        self.pixel_size_spin.setRange(1.0, 1000.0)
        self.pixel_size_spin.setDecimals(2)
        self.pixel_size_spin.setSingleStep(5.0)
        self.pixel_size_spin.setValue(100.0)
        self.pixel_size_spin.setSuffix(" nm/px")
        self.pixel_size_spin.setToolTip(
            "Camera pixel size at the sample plane.\n"
            "= physical pixel pitch ÷ total magnification.\n"
            "Used to scale SR localisation coordinates to nanometres."
        )
        g.addRow("Pixel size", self.pixel_size_spin)

        layout.addWidget(grp)

    def _build_inference_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        grp = QtWidgets.QGroupBox("Inference Parameters")
        grp.setToolTip(
            "Controls the tiled patch inference: tile size, overlap, "
            "super-resolution upsampling factor, and frame aggregation."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.patch_combo = QtWidgets.QComboBox()
        for sz in [32, 48, 64, 96, 128, 192, 256]:
            self.patch_combo.addItem(str(sz), sz)
        self.patch_combo.setCurrentText("64")
        self.patch_combo.setToolTip(
            "Tile side length in pixels fed to the model.\n"
            "Must match the patch size used during model training.\n"
            "Larger patches require more GPU memory."
        )
        g.addRow("Patch size (px)", self.patch_combo)

        self.overlap_spin = QtWidgets.QSpinBox()
        self.overlap_spin.setRange(0, 64)
        self.overlap_spin.setValue(16)
        self.overlap_spin.setSingleStep(4)
        self.overlap_spin.setToolTip(
            "Overlap between adjacent tiles in pixels.\n"
            "Tiles are blended with a Hanning window to suppress seam artefacts.\n"
            "Recommended: 20–25 % of patch_size."
        )
        g.addRow("Overlap (px)", self.overlap_spin)

        self.upsample_spin = QtWidgets.QSpinBox()
        self.upsample_spin.setRange(2, 20)
        self.upsample_spin.setValue(8)
        self.upsample_spin.setToolTip(
            "SR upsampling factor relative to the raw camera frame.\n"
            "The reconstructed SR image is (H × upsample) × (W × upsample).\n"
            "Must match the upsampling used during model training.\n"
            "Example: 100 nm/px × 8× = 12.5 nm/px effective SR resolution."
        )
        g.addRow("Upsample factor", self.upsample_spin)

        self.normalize_combo = QtWidgets.QComboBox()
        self.normalize_combo.addItem("Per-patch (recommended)", "per_patch")
        self.normalize_combo.addItem("Global ROI", "global_roi")
        self.normalize_combo.setToolTip(
            "Input normalisation strategy.\n"
            "Per-patch: each tile is normalised independently (z-score).\n"
            "Global ROI: normalisation is computed over the full ROI.\n"
            "Per-patch is more robust for non-uniform illumination."
        )
        g.addRow("Normalise", self.normalize_combo)

        self.output_combo = QtWidgets.QComboBox()
        self.output_combo.addItem("SR image (intensity map)", "sr_image")
        self.output_combo.addItem("Density map (count map)", "density_map")
        self.output_combo.setToolTip(
            "SR image: model output interpreted as a super-resolution intensity reconstruction.\n"
            "Density map: output interpreted as a particle density estimate per pixel."
        )
        g.addRow("Output mode", self.output_combo)

        self.window_spin = QtWidgets.QSpinBox()
        self.window_spin.setRange(1, 21)
        self.window_spin.setValue(5)
        self.window_spin.setToolTip(
            "Number of consecutive raw frames aggregated before inference.\n"
            "Temporal averaging reduces shot noise but requires the emitter "
            "to remain active across all frames in the window."
        )
        g.addRow("Frame window", self.window_spin)

        self.agg_combo = QtWidgets.QComboBox()
        self.agg_combo.addItem("Mean (temporal average)", "mean")
        self.agg_combo.addItem("Stack (feed as channels)", "stack")
        self.agg_combo.setToolTip(
            "Frame aggregation mode.\n"
            "Mean: temporal mean projection — reduces noise, assumes stationarity.\n"
            "Stack: each frame is a model input channel (requires multi-channel model)."
        )
        g.addRow("Aggregation", self.agg_combo)

        layout.addWidget(grp)

    def _build_detection_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        grp = QtWidgets.QGroupBox("Localisation Extraction")
        grp.setToolTip(
            "Parameters for extracting discrete particle positions from "
            "the SR reconstruction via local maxima detection."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.sigma_spin = QtWidgets.QDoubleSpinBox()
        self.sigma_spin.setRange(0.5, 5.0)
        self.sigma_spin.setDecimals(2)
        self.sigma_spin.setSingleStep(0.1)
        self.sigma_spin.setValue(1.3)
        self.sigma_spin.setToolTip(
            "Gaussian smoothing σ applied to the SR image before local-maxima "
            "detection. Set to ≈ 1 SR pixel to suppress single-pixel noise peaks."
        )
        g.addRow("Smoothing σ (SR px)", self.sigma_spin)

        self.det_thr_spin = QtWidgets.QDoubleSpinBox()
        self.det_thr_spin.setRange(0.5, 20.0)
        self.det_thr_spin.setDecimals(2)
        self.det_thr_spin.setSingleStep(0.5)
        self.det_thr_spin.setValue(3.0)
        self.det_thr_spin.setToolTip(
            "Detection threshold in multiples of the median absolute deviation (MAD).\n"
            "Peaks below median + k × MAD are rejected as background.\n"
            "Reduce to detect weaker emitters; increase to suppress false positives.\n"
            "Typical range: 2–5 MAD σ."
        )
        g.addRow("Threshold (MAD σ)", self.det_thr_spin)

        layout.addWidget(grp)

    def _build_run_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        btn_row = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run Deep-STORM")
        self.run_btn.setToolTip(
            "Run Deep-STORM super-resolution reconstruction over the active ROI."
        )
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("Idle — load a model to begin.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _build_export_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        export_grp = QtWidgets.QGroupBox("Export")
        export_layout = QtWidgets.QGridLayout(export_grp)

        self.export_csv_btn = QtWidgets.QPushButton("Export localisations CSV")
        self.export_csv_btn.setToolTip(
            "Export detected localisation positions (x, y, score) to a CSV file "
            "compatible with SMLM analysis tools."
        )
        self.export_csv_btn.setEnabled(False)

        self.export_sr_btn = QtWidgets.QPushButton("Export SR image (TIFF)")
        self.export_sr_btn.setToolTip(
            "Save the full super-resolution reconstruction as a 32-bit TIFF."
        )
        self.export_sr_btn.setEnabled(False)

        self.add_ann_btn = QtWidgets.QPushButton("Add to Annotations")
        self.add_ann_btn.setToolTip(
            "Import SR localisation centroids as point annotations in the "
            "annotation layer for downstream review and QC."
        )
        self.add_ann_btn.setEnabled(False)

        export_layout.addWidget(self.export_csv_btn, 0, 0)
        export_layout.addWidget(self.export_sr_btn, 0, 1)
        export_layout.addWidget(self.add_ann_btn, 1, 0, 1, 2)
        layout.addWidget(export_grp)

    def _build_results_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        results_grp = QtWidgets.QGroupBox("Localisation Results")
        rl = QtWidgets.QVBoxLayout(results_grp)

        summary_row = QtWidgets.QHBoxLayout()
        self.results_summary_lbl = QtWidgets.QLabel("No localisations yet.")
        summary_row.addWidget(self.results_summary_lbl)
        summary_row.addStretch(1)
        self.show_points_chk = QtWidgets.QCheckBox("Overlay on canvas")
        self.show_points_chk.setChecked(True)
        self.show_points_chk.setToolTip(
            "Render SR localisation positions as overlay points on the main canvas."
        )
        summary_row.addWidget(self.show_points_chk)
        rl.addLayout(summary_row)

        self.results_table = QtWidgets.QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(
            ["X (SR px)", "Y (SR px)", "X (nm)", "Y (nm)"]
        )
        self.results_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.results_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setMinimumHeight(120)
        rl.addWidget(self.results_table)

        layout.addWidget(results_grp)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_devices(self) -> None:
        try:
            import torch
            if not torch.cuda.is_available():
                idx = self.device_combo.findData("cuda")
                if idx >= 0:
                    model = self.device_combo.model()
                    item = model.item(idx)
                    if item:
                        item.setEnabled(False)
            # MPS (Apple Silicon)
            if not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
                idx = self.device_combo.findData("mps")
                if idx >= 0:
                    model = self.device_combo.model()
                    item = model.item(idx)
                    if item:
                        item.setEnabled(False)
        except ImportError:
            pass

    def _browse_model(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Deep-STORM model",
            str(Path.home()),
            "PyTorch models (*.pt *.pth);;All files (*)",
        )
        if path:
            self.model_path_edit.setText(path)
            self.model_status.setText(f"Model selected: {Path(path).name}")

    def _resolve_device(self) -> str:
        requested = str(self.device_combo.currentData() or "auto")
        if requested != "auto":
            return requested
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def values(self) -> DeepStormUiValues:
        """Return a typed snapshot of the current UI parameter values."""
        return DeepStormUiValues(
            model_path=str(self.model_path_edit.text()).strip(),
            device=self._resolve_device(),
            patch_size=int(self.patch_combo.currentData() or self.patch_combo.currentText()),
            overlap=int(self.overlap_spin.value()),
            upsample=int(self.upsample_spin.value()),
            pixel_size_nm=float(self.pixel_size_spin.value()),
            sigma_px=float(self.sigma_spin.value()),
            normalize_mode=str(self.normalize_combo.currentData() or "per_patch"),
            output_mode=str(self.output_combo.currentData() or "sr_image"),
            window_size=int(self.window_spin.value()),
            aggregation_mode=str(self.agg_combo.currentData() or "mean"),
            detection_thr_sigma=float(self.det_thr_spin.value()),
        )

    def set_localizations(self, localizations: list, sr_pixel_size_nm: float = 100.0) -> None:
        """Populate the results table with Deep-STORM localisation objects."""
        self.results_table.setRowCount(len(localizations))
        for row, loc in enumerate(localizations):
            x_sr = float(getattr(loc, "x_px", 0.0))
            y_sr = float(getattr(loc, "y_px", 0.0))
            x_nm = x_sr * sr_pixel_size_nm
            y_nm = y_sr * sr_pixel_size_nm
            for col, (val, fmt) in enumerate([
                (x_sr, "{:.2f}"),
                (y_sr, "{:.2f}"),
                (x_nm, "{:.1f}"),
                (y_nm, "{:.1f}"),
            ]):
                self.results_table.setItem(row, col, QtWidgets.QTableWidgetItem(fmt.format(val)))
        self.results_table.resizeColumnsToContents()
        n = len(localizations)
        self.results_summary_lbl.setText(
            f"{n:,} SR localisation{'s' if n != 1 else ''} extracted."
        )
        if n > 0:
            self.export_csv_btn.setEnabled(True)
            self.export_sr_btn.setEnabled(True)
            self.add_ann_btn.setEnabled(True)
