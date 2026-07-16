"""ONNX density prediction panel.

Provides a Qt dock widget for loading a TensorFlow-exported ONNX model and
running tiled density inference over the current image frame or ROI. The panel
surfaces all scientifically relevant parameters from
:class:`~phage_annotator.algorithms.onnx_infer.OnnxDensityOptions` and
displays estimated particle counts along with export controls.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.algorithms.onnx_infer import (
    OnnxDensityOptions,
    OnnxDensityResult,
    get_model_metadata,
    is_onnxruntime_available,
    list_available_providers,
    load_onnx_session,
    run_onnx_density,
)

logger = logging.getLogger(__name__)

_PROVIDER_LABELS = {
    "CPUExecutionProvider": "CPU",
    "CUDAExecutionProvider": "CUDA (GPU)",
    "CoreMLExecutionProvider": "CoreML (Apple Silicon)",
    "DirectMLExecutionProvider": "DirectML (Windows GPU)",
    "TensorrtExecutionProvider": "TensorRT",
}


class OnnxDensityPanel(QtWidgets.QWidget):
    """Dock panel for ONNX-based particle density prediction.

    Loads an ONNX model exported from TensorFlow (or any ONNX-compatible
    framework) and runs tiled inference over the active image frame to produce
    a calibrated particle-density map with integrated count estimates.

    Parameters
    ----------
    parent:
        Optional parent Qt widget.
    """

    #: Emitted when inference completes successfully.
    inference_finished = QtCore.Signal(object)  # OnnxDensityResult

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._session = None
        self._last_result: Optional[OnnxDensityResult] = None
        self._worker: Optional[QtCore.QThread] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget(scroll)
        scroll.setWidget(container)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ---- Model section -------------------------------------------
        model_group = QtWidgets.QGroupBox("Model")
        model_group.setToolTip(
            "Select an ONNX model file exported from TensorFlow via tf2onnx "
            "or the Keras ONNX export path."
        )
        mg = QtWidgets.QGridLayout(model_group)

        self.model_path_edit = QtWidgets.QLineEdit()
        self.model_path_edit.setPlaceholderText("Path to .onnx model file…")
        self.model_browse_btn = QtWidgets.QPushButton("Browse…")
        self.model_browse_btn.setFixedWidth(80)
        mg.addWidget(QtWidgets.QLabel("Model file"), 0, 0)
        mg.addWidget(self.model_path_edit, 0, 1)
        mg.addWidget(self.model_browse_btn, 0, 2)

        # Execution provider dropdown — populated from onnxruntime
        self.provider_combo = QtWidgets.QComboBox()
        self.provider_combo.setToolTip(
            "Execution provider controls where inference runs.\n"
            "CUDAExecutionProvider uses an NVIDIA GPU (fastest).\n"
            "CPUExecutionProvider runs on the host CPU (always available)."
        )
        self._populate_providers()
        mg.addWidget(QtWidgets.QLabel("Device"), 1, 0)
        mg.addWidget(self.provider_combo, 1, 1, 1, 2)

        # Channel format
        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.addItem("NHWC  (TensorFlow / Keras default)", "NHWC")
        self.channel_combo.addItem("NCHW  (PyTorch default)", "NCHW")
        self.channel_combo.setToolTip(
            "Memory layout expected by the model.\n"
            "TensorFlow models typically use NHWC (height, width, channels last).\n"
            "PyTorch models typically use NCHW (channels first)."
        )
        mg.addWidget(QtWidgets.QLabel("Channel format"), 2, 0)
        mg.addWidget(self.channel_combo, 2, 1, 1, 2)

        self.load_btn = QtWidgets.QPushButton("Load model")
        self.load_btn.setToolTip("Validate and load the ONNX model file.")
        self.model_status = QtWidgets.QLabel("No model loaded.")
        self.model_status.setWordWrap(True)
        self.model_info_btn = QtWidgets.QPushButton("Model info…")
        self.model_info_btn.setEnabled(False)
        self.model_info_btn.setToolTip("Show model input/output shape metadata.")
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.model_info_btn)
        btn_row.addStretch(1)
        mg.addLayout(btn_row, 3, 0, 1, 3)
        mg.addWidget(self.model_status, 4, 0, 1, 3)

        layout.addWidget(model_group)

        # ---- Pre-processing section ----------------------------------
        preproc_group = QtWidgets.QGroupBox("Pre-processing")
        preproc_group.setToolTip(
            "Normalisation applied to each image tile before inference. "
            "Use 'percentile' for fluorescence images with outlier hot-pixels."
        )
        pg = QtWidgets.QGridLayout(preproc_group)

        self.normalize_combo = QtWidgets.QComboBox()
        for label, val in [
            ("Percentile clip (recommended)", "percentile"),
            ("Z-score (zero mean / unit std)", "zscore"),
            ("Min–Max  [0, 1]", "minmax"),
            ("None (pass-through)", "none"),
        ]:
            self.normalize_combo.addItem(label, val)
        self.normalize_combo.setToolTip(
            "Percentile: clips to p_low–p_high then rescales to [0, 1].\n"
            "Z-score: (x − μ) / σ, sensitive to outliers.\n"
            "Min–Max: global rescale; affected by hot pixels."
        )
        pg.addWidget(QtWidgets.QLabel("Normalise"), 0, 0)
        pg.addWidget(self.normalize_combo, 0, 1, 1, 3)

        self.p_low_spin = QtWidgets.QDoubleSpinBox()
        self.p_low_spin.setRange(0.0, 49.9)
        self.p_low_spin.setDecimals(1)
        self.p_low_spin.setSingleStep(0.5)
        self.p_low_spin.setValue(1.0)
        self.p_low_spin.setToolTip(
            "Lower percentile for intensity clipping (percentile mode only).\n"
            "Increase to suppress dim background; typical range: 0.5–5."
        )
        self.p_high_spin = QtWidgets.QDoubleSpinBox()
        self.p_high_spin.setRange(50.1, 100.0)
        self.p_high_spin.setDecimals(1)
        self.p_high_spin.setSingleStep(0.5)
        self.p_high_spin.setValue(99.0)
        self.p_high_spin.setToolTip(
            "Upper percentile for intensity clipping (percentile mode only).\n"
            "Decrease to suppress saturated pixels; typical range: 95–99.9."
        )
        pg.addWidget(QtWidgets.QLabel("p_low (%)"), 1, 0)
        pg.addWidget(self.p_low_spin, 1, 1)
        pg.addWidget(QtWidgets.QLabel("p_high (%)"), 1, 2)
        pg.addWidget(self.p_high_spin, 1, 3)

        self.invert_chk = QtWidgets.QCheckBox("Invert intensity")
        self.invert_chk.setToolTip(
            "Invert pixel intensities before inference. "
            "Enable for bright-field / phase-contrast images where particles "
            "appear dark on a bright background."
        )
        pg.addWidget(self.invert_chk, 2, 0, 1, 4)

        layout.addWidget(preproc_group)

        # ---- Inference section ----------------------------------------
        infer_group = QtWidgets.QGroupBox("Inference")
        ig = QtWidgets.QGridLayout(infer_group)

        self.tile_spin = QtWidgets.QSpinBox()
        self.tile_spin.setRange(64, 1024)
        self.tile_spin.setValue(256)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setToolTip(
            "Tile side length in pixels. The model input must match this size.\n"
            "Larger tiles reduce seam artefacts but require more GPU memory.\n"
            "Must match the resolution the model was trained at."
        )
        ig.addWidget(QtWidgets.QLabel("Tile size (px)"), 0, 0)
        ig.addWidget(self.tile_spin, 0, 1)

        self.overlap_spin = QtWidgets.QSpinBox()
        self.overlap_spin.setRange(0, 256)
        self.overlap_spin.setValue(32)
        self.overlap_spin.setSingleStep(8)
        self.overlap_spin.setToolTip(
            "Overlap between adjacent tiles (pixels). Adjacent tiles are blended "
            "with a raised-cosine weight window to suppress seam artefacts.\n"
            "Recommended: ≥ 10 % of tile_size."
        )
        ig.addWidget(QtWidgets.QLabel("Overlap (px)"), 1, 0)
        ig.addWidget(self.overlap_spin, 1, 1)

        self.batch_spin = QtWidgets.QSpinBox()
        self.batch_spin.setRange(1, 64)
        self.batch_spin.setValue(8)
        self.batch_spin.setToolTip(
            "Tiles per inference batch. Larger batches increase GPU utilisation "
            "at the cost of additional memory. Reduce if CUDA out-of-memory errors occur."
        )
        ig.addWidget(QtWidgets.QLabel("Batch tiles"), 2, 0)
        ig.addWidget(self.batch_spin, 2, 1)

        self.stitch_combo = QtWidgets.QComboBox()
        self.stitch_combo.addItem("Weighted (raised-cosine blending)", "weighted")
        self.stitch_combo.addItem("Flat (uniform weight)", "flat")
        self.stitch_combo.setToolTip(
            "Tile blending strategy.\n"
            "Weighted: uses a 2-D raised-cosine window — recommended.\n"
            "Flat: equal weight per tile, may produce visible seams."
        )
        ig.addWidget(QtWidgets.QLabel("Stitch mode"), 3, 0)
        ig.addWidget(self.stitch_combo, 3, 1)

        self.roi_only_chk = QtWidgets.QCheckBox("Restrict to ROI bounding box")
        self.roi_only_chk.setChecked(True)
        self.roi_only_chk.setToolTip(
            "Confine tiled inference to the axis-aligned bounding box of the "
            "active ROI. This reduces computation and suppresses off-ROI "
            "background contributions to the count estimate."
        )
        ig.addWidget(self.roi_only_chk, 4, 0, 1, 2)

        layout.addWidget(infer_group)

        # ---- Calibration section -------------------------------------
        calib_group = QtWidgets.QGroupBox("Calibration")
        cg = QtWidgets.QGridLayout(calib_group)

        self.count_scale_spin = QtWidgets.QDoubleSpinBox()
        self.count_scale_spin.setRange(0.001, 1000.0)
        self.count_scale_spin.setDecimals(4)
        self.count_scale_spin.setSingleStep(0.01)
        self.count_scale_spin.setValue(1.0)
        self.count_scale_spin.setToolTip(
            "Multiplier applied to the summed density map to convert raw model "
            "output to an estimated particle count.\n"
            "Calibrate against a specimen with a known particle count. "
            "A value of 1.0 returns the raw integral."
        )
        cg.addWidget(QtWidgets.QLabel("Count scale factor"), 0, 0)
        cg.addWidget(self.count_scale_spin, 0, 1)

        self.threshold_clip_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_clip_spin.setRange(0.0, 1.0)
        self.threshold_clip_spin.setDecimals(4)
        self.threshold_clip_spin.setSingleStep(0.0001)
        self.threshold_clip_spin.setValue(0.0)
        self.threshold_clip_spin.setToolTip(
            "Minimum density map value. Pixels below this threshold are zeroed "
            "after inference, suppressing low-level background noise.\n"
            "The threshold is subtracted from remaining pixels to maintain "
            "conservation. Set to 0 to disable."
        )
        cg.addWidget(QtWidgets.QLabel("Background threshold"), 1, 0)
        cg.addWidget(self.threshold_clip_spin, 1, 1)

        layout.addWidget(calib_group)

        # ---- Run controls --------------------------------------------
        run_group = QtWidgets.QGroupBox("Run")
        rg = QtWidgets.QGridLayout(run_group)

        self.run_btn = QtWidgets.QPushButton("Run inference")
        self.run_btn.setEnabled(False)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        rg.addWidget(self.run_btn, 0, 0)
        rg.addWidget(self.cancel_btn, 0, 1)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        rg.addWidget(self.progress, 1, 0, 1, 2)

        self.status_label = QtWidgets.QLabel("Load a model to begin.")
        self.status_label.setWordWrap(True)
        rg.addWidget(self.status_label, 2, 0, 1, 2)

        layout.addWidget(run_group)

        # ---- Results section -----------------------------------------
        results_group = QtWidgets.QGroupBox("Results")
        resg = QtWidgets.QGridLayout(results_group)

        self.count_total_label = QtWidgets.QLabel("Total count: —")
        self.count_total_label.setToolTip(
            "Integrated particle count over the full image (or crop region). "
            "Equals: Σ(density_map) × count_scale."
        )
        self.count_roi_label = QtWidgets.QLabel("ROI count: —")
        self.count_roi_label.setToolTip(
            "Integrated count restricted to the active ROI polygon/rectangle. "
            "Only available when 'Restrict to ROI' is enabled."
        )
        self.runtime_label = QtWidgets.QLabel("Runtime: —")
        resg.addWidget(self.count_total_label, 0, 0)
        resg.addWidget(self.count_roi_label, 0, 1)
        resg.addWidget(self.runtime_label, 1, 0, 1, 2)

        layout.addWidget(results_group)

        # ---- Overlay & export section --------------------------------
        output_group = QtWidgets.QGroupBox("Overlay & Export")
        og = QtWidgets.QGridLayout(output_group)

        self.overlay_chk = QtWidgets.QCheckBox("Show density overlay on canvas")
        self.overlay_chk.setChecked(True)
        og.addWidget(self.overlay_chk, 0, 0, 1, 2)

        self.overlay_alpha = QtWidgets.QDoubleSpinBox()
        self.overlay_alpha.setRange(0.0, 1.0)
        self.overlay_alpha.setSingleStep(0.05)
        self.overlay_alpha.setValue(0.6)
        self.overlay_alpha.setToolTip("Opacity of the density map overlay (0 = transparent, 1 = opaque).")
        og.addWidget(QtWidgets.QLabel("Opacity"), 1, 0)
        og.addWidget(self.overlay_alpha, 1, 1)

        self.overlay_cmap = QtWidgets.QComboBox()
        for cmap in ["magma", "inferno", "viridis", "plasma", "hot", "jet"]:
            self.overlay_cmap.addItem(cmap)
        self.overlay_cmap.setToolTip(
            "Perceptually uniform colourmaps (magma, inferno, viridis, plasma) "
            "are recommended for scientific figures."
        )
        og.addWidget(QtWidgets.QLabel("Colormap"), 2, 0)
        og.addWidget(self.overlay_cmap, 2, 1)

        self.contours_chk = QtWidgets.QCheckBox("Show iso-density contours")
        og.addWidget(self.contours_chk, 3, 0, 1, 2)

        self.export_map_btn = QtWidgets.QPushButton("Save density map (TIFF)…")
        self.export_map_btn.setEnabled(False)
        self.export_counts_btn = QtWidgets.QPushButton("Save counts CSV…")
        self.export_counts_btn.setEnabled(False)
        og.addWidget(self.export_map_btn, 4, 0)
        og.addWidget(self.export_counts_btn, 4, 1)

        layout.addWidget(output_group)
        layout.addStretch(1)
        root.addWidget(scroll)

        # ---- Wire signals -------------------------------------------
        self.model_browse_btn.clicked.connect(self._browse_model)
        self.load_btn.clicked.connect(self._load_model)
        self.model_info_btn.clicked.connect(self._show_model_info)
        self.run_btn.clicked.connect(self._run_inference)
        self.cancel_btn.clicked.connect(self._cancel_inference)
        self.export_map_btn.clicked.connect(self._export_density_map)
        self.export_counts_btn.clicked.connect(self._export_counts_csv)
        self.normalize_combo.currentIndexChanged.connect(self._update_percentile_visibility)
        self._update_percentile_visibility()

    # ------------------------------------------------------------------
    # Provider population
    # ------------------------------------------------------------------

    def _populate_providers(self) -> None:
        self.provider_combo.clear()
        self.provider_combo.addItem("Auto (use best available)", "auto")
        if is_onnxruntime_available():
            for prov in list_available_providers():
                label = _PROVIDER_LABELS.get(prov, prov)
                self.provider_combo.addItem(label, prov)
        else:
            self.provider_combo.addItem("CPUExecutionProvider (onnxruntime not installed)", "CPUExecutionProvider")

    # ------------------------------------------------------------------
    # Slot implementations
    # ------------------------------------------------------------------

    def _update_percentile_visibility(self) -> None:
        is_pct = (self.normalize_combo.currentData() == "percentile")
        self.p_low_spin.setEnabled(is_pct)
        self.p_high_spin.setEnabled(is_pct)

    def _browse_model(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select ONNX model file",
            str(Path.home()),
            "ONNX models (*.onnx);;All files (*)",
        )
        if path:
            self.model_path_edit.setText(path)

    def _load_model(self) -> None:
        path = self.model_path_edit.text().strip()
        if not path:
            self._set_status("Please specify a model file path.", error=True)
            return
        if not is_onnxruntime_available():
            self._set_status(
                "onnxruntime is not installed. Run: pip install onnxruntime", error=True
            )
            return
        provider = self.provider_combo.currentData() or "auto"
        channel = self.channel_combo.currentData() or "NHWC"
        self._set_status("Loading model…")
        self.load_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        try:
            self._session = load_onnx_session(path, execution_provider=provider)
            meta = get_model_metadata(self._session)
            inp = meta["inputs"][0]
            out = meta["outputs"][0]
            actual_provider = self._session.get_providers()[0]
            self.model_status.setText(
                f"Model loaded  |  Provider: {actual_provider}\n"
                f"Input: {inp['name']}  {inp['shape']}  {inp['dtype']}\n"
                f"Output: {out['name']}  {out['shape']}  {out['dtype']}"
            )
            self.run_btn.setEnabled(True)
            self.model_info_btn.setEnabled(True)
            self._set_status("Model loaded successfully.")
        except Exception as exc:
            self._session = None
            self.run_btn.setEnabled(False)
            self.model_info_btn.setEnabled(False)
            self._set_status(f"Load failed: {exc}", error=True)
            logger.exception("ONNX model load error")
        finally:
            self.load_btn.setEnabled(True)

    def _show_model_info(self) -> None:
        if self._session is None:
            return
        meta = get_model_metadata(self._session)
        lines = ["ONNX Model Metadata\n" + "=" * 40]
        for inp in meta["inputs"]:
            lines.append(f"Input:  {inp['name']}  shape={inp['shape']}  dtype={inp['dtype']}")
        for out in meta["outputs"]:
            lines.append(f"Output: {out['name']}  shape={out['shape']}  dtype={out['dtype']}")
        providers = self._session.get_providers()
        lines.append(f"\nActive provider: {providers[0] if providers else 'unknown'}")
        QtWidgets.QMessageBox.information(self, "ONNX Model Info", "\n".join(lines))

    def _build_options(self) -> OnnxDensityOptions:
        return OnnxDensityOptions(
            model_path=self.model_path_edit.text().strip(),
            execution_provider=self.provider_combo.currentData() or "auto",
            channel_format=self.channel_combo.currentData() or "NHWC",
            normalize_mode=self.normalize_combo.currentData() or "percentile",
            p_low=float(self.p_low_spin.value()),
            p_high=float(self.p_high_spin.value()),
            invert=bool(self.invert_chk.isChecked()),
            tile_size=int(self.tile_spin.value()),
            overlap=int(self.overlap_spin.value()),
            batch_tiles=int(self.batch_spin.value()),
            count_scale=float(self.count_scale_spin.value()),
            threshold_clip_min=float(self.threshold_clip_spin.value()),
            use_roi_only=bool(self.roi_only_chk.isChecked()),
            stitch_mode=self.stitch_combo.currentData() or "weighted",
        )

    def _run_inference(self) -> None:
        if self._session is None:
            self._set_status("No model loaded.", error=True)
            return
        parent_win = self._find_main_window()
        image = self._get_current_image(parent_win)
        if image is None:
            self._set_status("No image available for inference.", error=True)
            return

        opts = self._build_options()
        roi_mask = self._get_roi_mask(parent_win, image.shape)

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._cancelled = False
        self.progress.setValue(0)
        self._set_status("Running ONNX inference…")

        def _progress_cb(pct: int, msg: str) -> None:
            self.progress.setValue(pct)
            self.status_label.setText(msg)
            QtWidgets.QApplication.processEvents()

        try:
            result = run_onnx_density(
                image,
                opts,
                session=self._session,
                roi_mask=roi_mask,
                progress_cb=_progress_cb,
            )
            self._last_result = result
            self._display_result(result)
            self.inference_finished.emit(result)
        except Exception as exc:
            self._set_status(f"Inference failed: {exc}", error=True)
            logger.exception("ONNX inference error")
        finally:
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def _cancel_inference(self) -> None:
        self._cancelled = True
        self._set_status("Cancellation requested.")

    def _display_result(self, result: OnnxDensityResult) -> None:
        self.count_total_label.setText(f"Total count: {result.count_total:.2f}")
        if result.count_roi is not None:
            self.count_roi_label.setText(f"ROI count: {result.count_roi:.2f}")
        else:
            self.count_roi_label.setText("ROI count: —")
        self.runtime_label.setText(
            f"Runtime: {result.runtime_ms:.0f} ms  |  {result.tiles_processed} tiles  |  {result.execution_provider}"
        )
        self._set_status(
            f"Inference complete — estimated count: {result.count_total:.1f} particles"
        )
        self.export_map_btn.setEnabled(True)
        self.export_counts_btn.setEnabled(True)
        self.progress.setValue(100)

    # ------------------------------------------------------------------
    # Image / ROI helpers (deferred to parent window)
    # ------------------------------------------------------------------

    def _find_main_window(self):
        w = self.parent()
        while w is not None and not isinstance(w, QtWidgets.QMainWindow):
            w = w.parent() if hasattr(w, "parent") else None
        return w

    def _get_current_image(self, window) -> Optional["np.ndarray"]:  # type: ignore[name-defined]
        try:
            import numpy as np
            if window is None:
                return None
            # Try common attribute names used in main window
            for attr in ("current_frame", "_current_frame", "current_image", "_displayed_image"):
                img = getattr(window, attr, None)
                if img is not None:
                    return np.asarray(img, dtype=np.float32)
            # Try the canvas/viewer
            for attr in ("_canvas", "canvas", "_viewer"):
                canvas = getattr(window, attr, None)
                if canvas is not None:
                    for sub in ("current_frame", "image_data"):
                        img = getattr(canvas, sub, None)
                        if img is not None:
                            return np.asarray(img, dtype=np.float32)
        except Exception:
            pass
        return None

    def _get_roi_mask(self, window, shape) -> Optional["np.ndarray"]:  # type: ignore[name-defined]
        if not self.roi_only_chk.isChecked() or window is None:
            return None
        try:
            import numpy as np
            from phage_annotator.algorithms.analysis import roi_mask_for_shape
            roi_rect = getattr(window, "roi_rect", None)
            roi_shape = getattr(window, "roi_shape", "box")
            if roi_rect is None:
                return None
            return roi_mask_for_shape(shape, roi_rect, roi_shape)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_density_map(self) -> None:
        if self._last_result is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save density map", "density_map.tiff", "TIFF images (*.tiff *.tif)"
        )
        if not path:
            return
        try:
            import tifffile
            tifffile.imwrite(path, self._last_result.density_map.astype("float32"))
            self._set_status(f"Density map saved: {Path(path).name}")
        except ImportError:
            import numpy as np
            np.save(path.replace(".tiff", ".npy").replace(".tif", ".npy"),
                    self._last_result.density_map)
            self._set_status("Saved as .npy (tifffile not installed).")
        except Exception as exc:
            self._set_status(f"Export failed: {exc}", error=True)

    def _export_counts_csv(self) -> None:
        if self._last_result is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save counts CSV", "density_counts.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            import csv as _csv
            result = self._last_result
            with open(path, "w", newline="") as fh:
                writer = _csv.writer(fh)
                writer.writerow(["metric", "value", "unit"])
                writer.writerow(["count_total", f"{result.count_total:.4f}", "particles"])
                if result.count_roi is not None:
                    writer.writerow(["count_roi", f"{result.count_roi:.4f}", "particles"])
                writer.writerow(["tiles_processed", result.tiles_processed, "tiles"])
                writer.writerow(["runtime_ms", f"{result.runtime_ms:.1f}", "ms"])
                writer.writerow(["model_path", result.model_path, ""])
                writer.writerow(["execution_provider", result.execution_provider, ""])
                for k, v in result.metadata.items():
                    writer.writerow([k, v, ""])
            self._set_status(f"Counts saved: {Path(path).name}")
        except Exception as exc:
            self._set_status(f"CSV export failed: {exc}", error=True)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, *, error: bool = False) -> None:
        self.status_label.setText(msg)
        colour = "#c0392b" if error else "#1a1a1a"
        self.status_label.setStyleSheet(f"color: {colour};")

    def current_options(self) -> OnnxDensityOptions:
        """Return a typed snapshot of the current UI parameter values."""
        return self._build_options()
