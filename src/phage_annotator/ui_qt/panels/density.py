"""Density model inference panel.

Provides a Qt dock widget for loading a PyTorch density prediction model and
running tiled inference over the current image frame. Integrates with
:mod:`phage_annotator.algorithms.density_infer` and
:class:`phage_annotator.algorithms.density_model.DensityPredictor`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class DensityPanel(QtWidgets.QWidget):
    """Dock panel for PyTorch-based particle density prediction.

    Loads a trained density regression model and runs tiled inference over the
    active image frame or ROI to produce a normalised density map and integrated
    count estimate.

    Parameters
    ----------
    parent:
        Optional parent Qt widget.
    """

    #: Emitted when inference completes with a (density_map, count_total, count_roi) tuple.
    inference_finished = QtCore.Signal(object, float, object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._predictor = None
        self._last_density_map: Optional[np.ndarray] = None
        self._last_count_total: float = 0.0
        self._last_count_roi: Optional[float] = None
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

        # ---- Model section -------------------------------------------
        model_group = QtWidgets.QGroupBox("Model")
        model_group.setToolTip(
            "Load a TorchScript (.pt) or state-dict PyTorch density prediction model."
        )
        mg = QtWidgets.QGridLayout(model_group)

        self.model_path_edit = QtWidgets.QLineEdit()
        self.model_path_edit.setPlaceholderText("Path to PyTorch density model (.pt / .pth)…")
        self.model_browse_btn = QtWidgets.QPushButton("Browse…")
        self.model_browse_btn.setFixedWidth(80)
        mg.addWidget(QtWidgets.QLabel("Model file"), 0, 0)
        mg.addWidget(self.model_path_edit, 0, 1)
        mg.addWidget(self.model_browse_btn, 0, 2)

        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItem("Auto (best available)", "auto")
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.addItem("CUDA (NVIDIA GPU)", "cuda")
        self.device_combo.addItem("MPS (Apple Silicon)", "mps")
        self.device_combo.setToolTip(
            "Compute device for density inference.\n"
            "'auto' selects CUDA if available, else CPU."
        )
        self._populate_devices()
        mg.addWidget(QtWidgets.QLabel("Device"), 1, 0)
        mg.addWidget(self.device_combo, 1, 1)

        self.load_btn = QtWidgets.QPushButton("Load model")
        self.load_btn.setToolTip("Validate and load the density model from disk.")
        mg.addWidget(self.load_btn, 1, 2)

        self.model_status = QtWidgets.QLabel("No model loaded.")
        self.model_status.setWordWrap(True)
        mg.addWidget(self.model_status, 2, 0, 1, 3)

        layout.addWidget(model_group)

        # ---- Input section -------------------------------------------
        input_group = QtWidgets.QGroupBox("Input")
        input_group.setToolTip("Select the image source and spatial scope for inference.")
        ig = QtWidgets.QGridLayout(input_group)

        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.addItem("Current frame", "frame")
        self.target_combo.addItem("Mean projection", "mean_proj")
        self.target_combo.addItem("Modality 2", "modality2")
        self.target_combo.setToolTip(
            "Image to pass to the density model.\n"
            "Mean projection averages across the temporal stack — useful for "
            "reducing shot noise before density prediction."
        )
        ig.addWidget(QtWidgets.QLabel("Target"), 0, 0)
        ig.addWidget(self.target_combo, 0, 1)

        self.roi_only_chk = QtWidgets.QCheckBox("Restrict to ROI bounding box")
        self.roi_only_chk.setChecked(True)
        self.roi_only_chk.setToolTip(
            "Confine inference to the bounding box of the active ROI, reducing "
            "computation on empty background regions."
        )
        ig.addWidget(self.roi_only_chk, 1, 0, 1, 2)

        layout.addWidget(input_group)

        # ---- Pre-processing section ----------------------------------
        preprocess_group = QtWidgets.QGroupBox("Pre-processing")
        preprocess_group.setToolTip(
            "Normalisation applied per-tile before the model receives the input."
        )
        pg = QtWidgets.QGridLayout(preprocess_group)

        self.normalize_combo = QtWidgets.QComboBox()
        self.normalize_combo.addItem("Percentile clip (recommended)", "percentile")
        self.normalize_combo.addItem("Z-score", "zscore")
        self.normalize_combo.addItem("Min–Max [0, 1]", "minmax")
        self.normalize_combo.setToolTip(
            "Percentile: clips to p_low–p_high then rescales to [0, 1].\n"
            "Z-score: (x − μ) / σ — unit variance, zero mean.\n"
            "Min–Max: global range rescaling; affected by hot pixels."
        )
        pg.addWidget(QtWidgets.QLabel("Normalise"), 0, 0)
        pg.addWidget(self.normalize_combo, 0, 1, 1, 3)

        self.p_low_spin = QtWidgets.QDoubleSpinBox()
        self.p_low_spin.setRange(0.0, 49.9)
        self.p_low_spin.setDecimals(1)
        self.p_low_spin.setSingleStep(0.5)
        self.p_low_spin.setValue(1.0)
        self.p_low_spin.setToolTip("Lower percentile for intensity clipping (percentile mode).")
        self.p_high_spin = QtWidgets.QDoubleSpinBox()
        self.p_high_spin.setRange(50.1, 100.0)
        self.p_high_spin.setDecimals(1)
        self.p_high_spin.setSingleStep(0.5)
        self.p_high_spin.setValue(99.0)
        self.p_high_spin.setToolTip("Upper percentile for intensity clipping (percentile mode).")
        pg.addWidget(QtWidgets.QLabel("p_low (%)"), 1, 0)
        pg.addWidget(self.p_low_spin, 1, 1)
        pg.addWidget(QtWidgets.QLabel("p_high (%)"), 1, 2)
        pg.addWidget(self.p_high_spin, 1, 3)

        self.invert_chk = QtWidgets.QCheckBox("Invert intensity (bright-field)")
        self.invert_chk.setToolTip(
            "Invert pixel values before inference. Enable for bright-field or "
            "phase-contrast images where particles appear darker than the background."
        )
        pg.addWidget(self.invert_chk, 2, 0, 1, 4)

        layout.addWidget(preprocess_group)

        # ---- Inference section ----------------------------------------
        infer_group = QtWidgets.QGroupBox("Inference")
        infer_group.setToolTip("Tiled inference configuration.")
        infer_layout = QtWidgets.QGridLayout(infer_group)

        self.tile_spin = QtWidgets.QSpinBox()
        self.tile_spin.setRange(64, 1024)
        self.tile_spin.setValue(256)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setToolTip(
            "Tile side length in pixels. Must match the spatial scale used during "
            "model training. Larger tiles require more GPU memory."
        )
        infer_layout.addWidget(QtWidgets.QLabel("Tile size (px)"), 0, 0)
        infer_layout.addWidget(self.tile_spin, 0, 1)

        self.overlap_spin = QtWidgets.QSpinBox()
        self.overlap_spin.setRange(0, 256)
        self.overlap_spin.setValue(32)
        self.overlap_spin.setSingleStep(8)
        self.overlap_spin.setToolTip(
            "Tile overlap in pixels. Tiles are blended with a raised-cosine window "
            "to suppress seam artefacts. Recommended: ≥ 10 % of tile size."
        )
        infer_layout.addWidget(QtWidgets.QLabel("Overlap (px)"), 1, 0)
        infer_layout.addWidget(self.overlap_spin, 1, 1)

        self.batch_spin = QtWidgets.QSpinBox()
        self.batch_spin.setRange(1, 64)
        self.batch_spin.setValue(8)
        self.batch_spin.setToolTip(
            "Tiles per inference batch. Larger values improve GPU utilisation "
            "at the cost of additional memory."
        )
        infer_layout.addWidget(QtWidgets.QLabel("Batch tiles"), 2, 0)
        infer_layout.addWidget(self.batch_spin, 2, 1)

        self.count_scale_spin = QtWidgets.QDoubleSpinBox()
        self.count_scale_spin.setRange(0.001, 1000.0)
        self.count_scale_spin.setDecimals(4)
        self.count_scale_spin.setSingleStep(0.01)
        self.count_scale_spin.setValue(1.0)
        self.count_scale_spin.setToolTip(
            "Multiplier applied to the integrated density map to convert to "
            "particle count. Calibrate against a specimen of known density.\n"
            "count = Σ(density_map) × count_scale."
        )
        infer_layout.addWidget(QtWidgets.QLabel("Count scale"), 3, 0)
        infer_layout.addWidget(self.count_scale_spin, 3, 1)

        self.run_btn = QtWidgets.QPushButton("Run")
        self.run_btn.setEnabled(False)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        infer_layout.addWidget(self.run_btn, 4, 0)
        infer_layout.addWidget(self.cancel_btn, 4, 1)

        layout.addWidget(infer_group)

        # ---- Progress -----------------------------------------------
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("Load a model to begin.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ---- Output section ------------------------------------------
        output_group = QtWidgets.QGroupBox("Results & Overlay")
        og = QtWidgets.QGridLayout(output_group)

        self.count_total_label = QtWidgets.QLabel("Total count: —")
        self.count_total_label.setToolTip("Integrated particle count over the full image area.")
        self.count_roi_label = QtWidgets.QLabel("ROI count: —")
        self.count_roi_label.setToolTip("Integrated count within the active ROI boundary.")
        og.addWidget(self.count_total_label, 0, 0)
        og.addWidget(self.count_roi_label, 0, 1)

        self.overlay_chk = QtWidgets.QCheckBox("Show density overlay")
        self.overlay_chk.setChecked(True)
        og.addWidget(self.overlay_chk, 1, 0, 1, 2)

        self.overlay_alpha = QtWidgets.QDoubleSpinBox()
        self.overlay_alpha.setRange(0.0, 1.0)
        self.overlay_alpha.setSingleStep(0.05)
        self.overlay_alpha.setValue(0.6)
        self.overlay_alpha.setToolTip("Overlay opacity (0 = transparent, 1 = opaque).")
        og.addWidget(QtWidgets.QLabel("Opacity"), 2, 0)
        og.addWidget(self.overlay_alpha, 2, 1)

        self.overlay_cmap = QtWidgets.QComboBox()
        for cmap in ["magma", "inferno", "viridis", "plasma", "hot"]:
            self.overlay_cmap.addItem(cmap)
        self.overlay_cmap.setToolTip(
            "Density map colourmap. Perceptually uniform colourmaps "
            "(magma, inferno, viridis) are recommended for publication figures."
        )
        og.addWidget(QtWidgets.QLabel("Colormap"), 3, 0)
        og.addWidget(self.overlay_cmap, 3, 1)

        self.contours_chk = QtWidgets.QCheckBox("Show iso-density contours")
        og.addWidget(self.contours_chk, 4, 0, 1, 2)

        self.export_map_btn = QtWidgets.QPushButton("Save density map (TIFF)…")
        self.export_map_btn.setEnabled(False)
        self.export_counts_btn = QtWidgets.QPushButton("Save counts CSV…")
        self.export_counts_btn.setEnabled(False)
        og.addWidget(self.export_map_btn, 5, 0)
        og.addWidget(self.export_counts_btn, 5, 1)

        layout.addWidget(output_group)
        layout.addStretch(1)

        # ---- Wire signals -------------------------------------------
        self.model_browse_btn.clicked.connect(self._browse_model)
        self.load_btn.clicked.connect(self._load_model)
        self.run_btn.clicked.connect(self._run_inference)
        self.cancel_btn.clicked.connect(self._cancel)
        self.export_map_btn.clicked.connect(self._export_density_map)
        self.export_counts_btn.clicked.connect(self._export_counts_csv)
        self.normalize_combo.currentIndexChanged.connect(self._update_percentile_visibility)
        self._update_percentile_visibility()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_devices(self) -> None:
        try:
            import torch
            if not torch.cuda.is_available():
                idx = self.device_combo.findData("cuda")
                if idx >= 0:
                    m = self.device_combo.model()
                    item = m.item(idx)
                    if item:
                        item.setEnabled(False)
            if not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
                idx = self.device_combo.findData("mps")
                if idx >= 0:
                    m = self.device_combo.model()
                    item = m.item(idx)
                    if item:
                        item.setEnabled(False)
        except ImportError:
            pass

    def _update_percentile_visibility(self) -> None:
        is_pct = (self.normalize_combo.currentData() == "percentile")
        self.p_low_spin.setEnabled(is_pct)
        self.p_high_spin.setEnabled(is_pct)

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

    def _browse_model(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select density model",
            str(Path.home()),
            "PyTorch models (*.pt *.pth);;All files (*)",
        )
        if path:
            self.model_path_edit.setText(path)

    def _load_model(self) -> None:
        path = self.model_path_edit.text().strip()
        if not path:
            self._set_status("Please specify a model path.", error=True)
            return
        device = self._resolve_device()
        self._set_status(f"Loading model on {device}…")
        self.load_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        try:
            from phage_annotator.algorithms.density_model import DensityPredictor
            self._predictor = DensityPredictor.from_path(path, device=device)
            self.model_status.setText(f"Model loaded  |  device: {device}  |  {Path(path).name}")
            self.run_btn.setEnabled(True)
            self._set_status("Model loaded successfully.")
        except Exception as exc:
            self._predictor = None
            self.run_btn.setEnabled(False)
            self.model_status.setText(f"Load failed: {exc}")
            self._set_status(f"Load failed: {exc}", error=True)
            logger.exception("Density model load error")
        finally:
            self.load_btn.setEnabled(True)

    def _run_inference(self) -> None:
        if self._predictor is None:
            self._set_status("No model loaded.", error=True)
            return
        parent_win = self._find_main_window()
        image = self._get_image(parent_win)
        if image is None:
            self._set_status("No image available for inference.", error=True)
            return

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._cancelled = False
        self.progress.setValue(0)
        self._set_status("Running density inference…")
        QtWidgets.QApplication.processEvents()

        try:
            from phage_annotator.algorithms.density_infer import (
                DensityInferOptions,
                run_density_inference,
            )
            from phage_annotator.config.density import DensityConfig

            normalize_mode = self.normalize_combo.currentData() or "percentile"
            config = DensityConfig(
                normalize=normalize_mode,
                p_low=float(self.p_low_spin.value()),
                p_high=float(self.p_high_spin.value()),
                invert=bool(self.invert_chk.isChecked()),
                count_scale=float(self.count_scale_spin.value()),
            )
            opts = DensityInferOptions(
                tile_size=int(self.tile_spin.value()),
                overlap=int(self.overlap_spin.value()),
                batch_tiles=int(self.batch_spin.value()),
                use_roi_only=bool(self.roi_only_chk.isChecked()),
            )
            roi_spec = self._get_roi_spec(parent_win)
            result = run_density_inference(
                image,
                self._predictor,
                config,
                roi_spec=roi_spec,
                options=opts,
            )
            self._last_density_map = result.density_map
            self._last_count_total = result.count_total
            self._last_count_roi = result.count_roi

            self.count_total_label.setText(f"Total count: {result.count_total:.2f}")
            if result.count_roi is not None:
                self.count_roi_label.setText(f"ROI count: {result.count_roi:.2f}")
            else:
                self.count_roi_label.setText("ROI count: —")
            self._set_status(
                f"Inference complete — {result.tiles_processed} tiles in {result.runtime_ms:.0f} ms"
            )
            self.progress.setValue(100)
            self.export_map_btn.setEnabled(True)
            self.export_counts_btn.setEnabled(True)
            self.inference_finished.emit(result.density_map, result.count_total, result.count_roi)
        except Exception as exc:
            self._set_status(f"Inference failed: {exc}", error=True)
            logger.exception("Density inference error")
        finally:
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def _cancel(self) -> None:
        self._cancelled = True
        self._set_status("Cancellation requested.")

    def _export_density_map(self) -> None:
        if self._last_density_map is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save density map", "density_map.tiff", "TIFF images (*.tiff *.tif)"
        )
        if not path:
            return
        try:
            import tifffile
            tifffile.imwrite(path, self._last_density_map.astype("float32"))
            self._set_status(f"Saved: {Path(path).name}")
        except ImportError:
            np.save(path.replace(".tiff", ".npy").replace(".tif", ".npy"), self._last_density_map)
            self._set_status("Saved as .npy (tifffile not installed).")
        except Exception as exc:
            self._set_status(f"Export failed: {exc}", error=True)

    def _export_counts_csv(self) -> None:
        if self._last_density_map is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save counts CSV", "density_counts.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            import csv as _csv
            with open(path, "w", newline="") as fh:
                w = _csv.writer(fh)
                w.writerow(["metric", "value", "unit"])
                w.writerow(["count_total", f"{self._last_count_total:.4f}", "particles"])
                if self._last_count_roi is not None:
                    w.writerow(["count_roi", f"{self._last_count_roi:.4f}", "particles"])
                w.writerow(["model_path", self.model_path_edit.text().strip(), ""])
                w.writerow(["device", self._resolve_device(), ""])
                w.writerow(["tile_size", self.tile_spin.value(), "px"])
                w.writerow(["overlap", self.overlap_spin.value(), "px"])
                w.writerow(["count_scale", self.count_scale_spin.value(), ""])
            self._set_status(f"Saved: {Path(path).name}")
        except Exception as exc:
            self._set_status(f"CSV export failed: {exc}", error=True)

    def _find_main_window(self):
        w = self.parent()
        while w is not None and not isinstance(w, QtWidgets.QMainWindow):
            w = w.parent() if hasattr(w, "parent") else None
        return w

    def _get_image(self, window) -> Optional[np.ndarray]:
        try:
            if window is None:
                return None
            for attr in ("current_frame", "_current_frame", "current_image", "_displayed_image"):
                img = getattr(window, attr, None)
                if img is not None:
                    return np.asarray(img, dtype=np.float32)
        except Exception:
            pass
        return None

    def _get_roi_spec(self, window):
        if window is None:
            return None
        try:
            roi_rect = getattr(window, "roi_rect", None)
            roi_shape = getattr(window, "roi_shape", "box")
            if roi_rect is None:
                return None
            return {"shape": roi_shape, "rect": tuple(roi_rect)}
        except Exception:
            return None

    def _set_status(self, msg: str, *, error: bool = False) -> None:
        self.status_label.setText(msg)
        colour = "#c0392b" if error else "#1a1a1a"
        self.status_label.setStyleSheet(f"color: {colour};")
