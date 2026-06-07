"""Extracted method group 2 for ContrastDialog."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils.contrast_lut import computeHistogram, autoScaleHistogram



class HistogramContrastAutosetMixin:
    """Method group 2 extracted from ContrastDialog."""

    def _compute_preset_range(self, preset: str, low: float, high: float) -> Tuple[float, float]:
        """Compute preset range for the current workflow."""
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
        """Handle the on auto done helper flow."""
        self._min_spin.setValue(float(vmin))
        self._max_spin.setValue(float(vmax))
        self._update_vlines()
    def _on_auto_error(self, message: str) -> None:
        """Handle the on auto error helper flow."""
        QtWidgets.QMessageBox.warning(self, "Auto contrast", message)
    def _on_auto_finished(self) -> None:
        """Handle the on auto finished helper flow."""
        self._status_label.setText("")
        self._auto_btn.setEnabled(True)
        self._worker = None
        self._worker_thread = None
    def closeEvent(self, event) -> None:
        """Run the closeEvent workflow."""
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait(200)
        self._fig.clear()
        super().closeEvent(event)
    def _reset(self) -> None:
        """Reset reset for the current workflow."""
        self._min_spin.setValue(self._data_min)
        self._max_spin.setValue(self._data_max)
        self._update_vlines()
    def _apply(self) -> None:
        """Apply apply for the current workflow."""
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
