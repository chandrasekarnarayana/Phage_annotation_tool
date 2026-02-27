"""Brightness and contrast adjustment dialog with histogram preview."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils.contrast_lut import computeHistogram, autoScaleHistogram


class ContrastDialog(QtWidgets.QDialog):
    """Dialog for interactive brightness/contrast adjustment.

    Parameters
    ----------
    parent : QtWidgets.QWidget
        Parent widget.
    data : np.ndarray
        2D image data used to compute the histogram.
    vmin : float
        Initial minimum value.
    vmax : float
        Initial maximum value.
    on_apply : Callable[[float, float], None]
        Callback invoked when Apply is pressed.
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget],
        data: np.ndarray,
        vmin: float,
        vmax: float,
        on_apply: Callable[[float, float], None],
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._on_apply = on_apply
        self._hist = None
        self._edges = None
        self._vmin_line = None
        self._vmax_line = None
        self._data_min = float(np.min(data)) if data.size else 0.0
        self._data_max = float(np.max(data)) if data.size else 1.0
        self._worker_thread = None
        self._worker = None

        self.setWindowTitle("Brightness/Contrast")
        self._build_ui(vmin, vmax)
        self._compute_histogram()
        self._render_histogram()

    def _build_ui(self, vmin: float, vmax: float) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Histogram figure
        self._fig = Figure(figsize=(5, 3))
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        layout.addWidget(self._canvas)

        # Controls
        controls = QtWidgets.QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(6)

        self._min_spin = QtWidgets.QDoubleSpinBox()
        self._max_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self._min_spin, self._max_spin):
            spin.setDecimals(3)
            spin.setRange(self._data_min, self._data_max)
            spin.setSingleStep(max((self._data_max - self._data_min) / 1000.0, 0.001))
            spin.setKeyboardTracking(False)

        self._min_spin.setValue(float(vmin))
        self._max_spin.setValue(float(vmax))

        controls.addWidget(QtWidgets.QLabel("Minimum"), 0, 0)
        controls.addWidget(self._min_spin, 0, 1)
        controls.addWidget(QtWidgets.QLabel("Maximum"), 1, 0)
        controls.addWidget(self._max_spin, 1, 1)

        self._method_combo = QtWidgets.QComboBox()
        self._method_combo.addItems(["Percentile", "Min/Max", "Std"])
        controls.addWidget(QtWidgets.QLabel("Auto method"), 2, 0)
        controls.addWidget(self._method_combo, 2, 1)

        self._low_spin = QtWidgets.QDoubleSpinBox()
        self._high_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self._low_spin, self._high_spin):
            spin.setRange(0.0, 100.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
        self._low_spin.setValue(0.35)
        self._high_spin.setValue(99.65)

        controls.addWidget(QtWidgets.QLabel("Low %"), 3, 0)
        controls.addWidget(self._low_spin, 3, 1)
        controls.addWidget(QtWidgets.QLabel("High %"), 4, 0)
        controls.addWidget(self._high_spin, 4, 1)

        layout.addLayout(controls)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel("Presets"))
        self._preset_auto_btn = QtWidgets.QPushButton("Auto")
        self._preset_linear_btn = QtWidgets.QPushButton("Linear")
        self._preset_log_btn = QtWidgets.QPushButton("Log")
        self._preset_sqrt_btn = QtWidgets.QPushButton("Sqrt")
        preset_row.addWidget(self._preset_auto_btn)
        preset_row.addWidget(self._preset_linear_btn)
        preset_row.addWidget(self._preset_log_btn)
        preset_row.addWidget(self._preset_sqrt_btn)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setStyleSheet("color: #666666;")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self._auto_btn = QtWidgets.QPushButton("Auto")
        self._reset_btn = QtWidgets.QPushButton("Reset")
        self._apply_btn = QtWidgets.QPushButton("Apply")
        self._close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(self._auto_btn)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._min_spin.valueChanged.connect(self._update_vlines)
        self._max_spin.valueChanged.connect(self._update_vlines)
        self._auto_btn.clicked.connect(self._auto_adjust)
        self._reset_btn.clicked.connect(self._reset)
        self._apply_btn.clicked.connect(self._apply)
        self._close_btn.clicked.connect(self.close)
        self._preset_auto_btn.clicked.connect(lambda: self._apply_preset("Auto"))
        self._preset_linear_btn.clicked.connect(lambda: self._apply_preset("Linear"))
        self._preset_log_btn.clicked.connect(lambda: self._apply_preset("Log"))
        self._preset_sqrt_btn.clicked.connect(lambda: self._apply_preset("Sqrt"))

    def _compute_histogram(self) -> None:
        if self._data.size == 0:
            self._hist = np.array([])
            self._edges = np.array([0.0, 1.0])
            return
        self._hist, self._edges = computeHistogram(self._data, bins=256)

    def _render_histogram(self) -> None:
        self._ax.clear()
        if self._hist is not None and self._edges is not None:
            centers = (self._edges[:-1] + self._edges[1:]) / 2.0
            self._ax.plot(centers, self._hist, color="#4C78A8", linewidth=1.0)
        self._ax.set_xlabel("Intensity")
        self._ax.set_ylabel("Count")
        self._ax.set_title("Histogram")
        self._vmin_line = self._ax.axvline(self._min_spin.value(), color="#D62728")
        self._vmax_line = self._ax.axvline(self._max_spin.value(), color="#2CA02C")
        self._ax.set_xlim(self._data_min, self._data_max)
        self._fig.tight_layout()
        self._canvas.draw_idle()

    def _update_vlines(self) -> None:
        if self._vmin_line is not None:
            self._vmin_line.set_xdata([self._min_spin.value()])
        if self._vmax_line is not None:
            self._vmax_line.set_xdata([self._max_spin.value()])
        self._canvas.draw_idle()

    def _auto_adjust(self) -> None:
        if self._data.size == 0:
            return
        if self._worker_thread is not None:
            return
        method = self._method_combo.currentText().lower()
        low = float(self._low_spin.value())
        high = float(self._high_spin.value())
        if self._data.size < 2_000_000:
            vmin, vmax = self._compute_auto_range(method, low, high)
            self._min_spin.setValue(float(vmin))
            self._max_spin.setValue(float(vmax))
            self._update_vlines()
            return
        self._status_label.setText("Computing auto range…")
        self._auto_btn.setEnabled(False)

        class _AutoWorker(QtCore.QObject):
            finished = QtCore.pyqtSignal(float, float)
            failed = QtCore.pyqtSignal(str)

            def __init__(self, data: np.ndarray, method: str, low: float, high: float) -> None:
                super().__init__()
                self._data = data
                self._method = method
                self._low = low
                self._high = high

            def run(self) -> None:
                try:
                    vmin, vmax = self._compute()
                    self.finished.emit(float(vmin), float(vmax))
                except Exception as exc:
                    self.failed.emit(str(exc))

            def _compute(self) -> Tuple[float, float]:
                if self._method == "percentile":
                    vmin = float(np.percentile(self._data, self._low))
                    vmax = float(np.percentile(self._data, self._high))
                    return vmin, vmax
                if self._method == "min/max":
                    return autoScaleHistogram(self._data, method="minmax")
                return autoScaleHistogram(self._data, method="std")

        self._worker = _AutoWorker(self._data, method, low, high)
        self._worker_thread = QtCore.QThread(self)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_auto_done)
        self._worker.failed.connect(self._on_auto_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.failed.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._on_auto_finished)
        self._worker_thread.start()

    def _compute_auto_range(self, method: str, low: float, high: float) -> Tuple[float, float]:
        if method == "percentile":
            vmin = float(np.percentile(self._data, low))
            vmax = float(np.percentile(self._data, high))
            return vmin, vmax
        if method == "min/max":
            return autoScaleHistogram(self._data, method="minmax")
        return autoScaleHistogram(self._data, method="std")

    def _apply_preset(self, preset: str) -> None:
        if self._data.size == 0:
            return
        low = float(self._low_spin.value())
        high = float(self._high_spin.value())
        vmin, vmax = self._compute_preset_range(preset, low, high)
        self._min_spin.setValue(float(vmin))
        self._max_spin.setValue(float(vmax))
        self._update_vlines()

    def _compute_preset_range(self, preset: str, low: float, high: float) -> Tuple[float, float]:
        preset = preset.lower()
        if preset == "auto":
            method = self._method_combo.currentText().lower()
            return self._compute_auto_range(method, low, high)
        if preset == "linear":
            return autoScaleHistogram(self._data, method="minmax")
        data_min = float(self._data_min)
        data_max = float(self._data_max)
        if data_max <= data_min:
            return data_min, data_max
        shifted = self._data - data_min
        shifted = np.clip(shifted, 0.0, None)
        if preset == "log":
            transformed = np.log1p(shifted)
            lo, hi = np.percentile(transformed, [low, high])
            return float(np.expm1(lo) + data_min), float(np.expm1(hi) + data_min)
        if preset == "sqrt":
            transformed = np.sqrt(shifted)
            lo, hi = np.percentile(transformed, [low, high])
            return float(lo * lo + data_min), float(hi * hi + data_min)
        return autoScaleHistogram(self._data, method="minmax")

    def _on_auto_done(self, vmin: float, vmax: float) -> None:
        self._min_spin.setValue(float(vmin))
        self._max_spin.setValue(float(vmax))
        self._update_vlines()

    def _on_auto_error(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "Auto contrast", message)

    def _on_auto_finished(self) -> None:
        self._status_label.setText("")
        self._auto_btn.setEnabled(True)
        self._worker = None
        self._worker_thread = None

    def closeEvent(self, event) -> None:
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait(200)
        self._fig.clear()
        super().closeEvent(event)

    def _reset(self) -> None:
        self._min_spin.setValue(self._data_min)
        self._max_spin.setValue(self._data_max)
        self._update_vlines()

    def _apply(self) -> None:
        vmin = float(self._min_spin.value())
        vmax = float(self._max_spin.value())
        if vmax <= vmin:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid range",
                "Maximum must be greater than minimum.",
            )
            return
        self._on_apply(vmin, vmax)

    def values(self) -> Tuple[float, float]:
        """Return current min/max values."""
        return float(self._min_spin.value()), float(self._max_spin.value())
