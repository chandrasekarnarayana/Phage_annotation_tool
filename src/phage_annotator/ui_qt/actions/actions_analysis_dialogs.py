"""Analysis, detection, scoring, and interactive learning actions."""

from __future__ import annotations

import csv
import gc
import logging
import pathlib
import time
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.utils.debug import debug_log

logger = logging.getLogger(__name__)

class ActionsAnalysisDialogsMixin:
    """Mixin for analysis, detection, calibration, and interactive learning actions."""

    # ── Modal consensus ────────────────────────────────────────────────────:
    """Mixin extracted from ActionsMixinAnalysis."""
    pass

    def _show_bleach_dialog(self) -> None:
        """Open a dialog showing ROI mean over T with exponential fit."""
        if self.primary_image.array is None:
            return
        self.recorder.record("bleach_fit", {"image": self.primary_image.name})
        arr = self.primary_image.array
        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        crop_rect = self.crop_rect
        img_path = pathlib.Path(self.primary_image.path)
        job_gen = self._job_generation
        from typing import Tuple

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Computing…", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Bleaching analysis")
        layout = QtWidgets.QVBoxLayout(dlg)
        status_label = QtWidgets.QLabel("Computing ROI means…")
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        status_row = QtWidgets.QHBoxLayout()
        status_row.addWidget(status_label)
        status_row.addWidget(cancel_btn)
        layout.addLayout(status_row)
        layout.addWidget(progress_bar)

        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            def _apply_crop_local(frame: np.ndarray) -> np.ndarray:
                """Apply crop local for the current workflow."""
                x, y, w, h = crop_rect
                if w <= 0 or h <= 0:
                    return frame
                x0 = int(max(0, x))
                y0 = int(max(0, y))
                x1 = int(min(frame.shape[1], x + w))
                y1 = int(min(frame.shape[0], y + h))
                return frame[y0:y1, x0:x1]

            def _roi_mask_local(shape):
                """Handle the roi mask local helper flow."""
                if len(shape) < 2:
                    raise ValueError(f"Invalid frame shape for ROI mask: {shape}")
                h, w = int(shape[0]), int(shape[1])
                yy = np.arange(h)[:, None]
                xx = np.arange(w)[None, :]
                rx, ry, rw, rh = roi_rect
                if roi_shape == "circle":
                    cx, cy = rx + rw / 2, ry + rh / 2
                    r = min(rw, rh) / 2
                    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
                return (rx <= xx) & (xx <= rx + rw) & (ry <= yy) & (yy <= ry + rh)

            means = []
            total = max(1, arr.shape[0])
            for t in range(arr.shape[0]):
                if cancel_token.is_cancelled():
                    return None
                frame = arr[t, 0, :, :]
                frame_cropped = _apply_crop_local(frame)
                roi_mask = _roi_mask_local(frame_cropped.shape)
                vals = frame_cropped[roi_mask]
                means.append(float(vals.mean()) if vals.size else float("nan"))
                pct = int((t + 1) / total * 80)
                progress(pct, f"Computing means… {t+1}/{total}")
            if cancel_token.is_cancelled():
                return None
            progress(90, "Fitting…")
            try:
                xs, fit, eq = fit_bleach_curve(means)
            except Exception:
                xs = np.arange(len(means))
                fit = None
                eq = "fit failed"
            progress(100, "Done")
            return (means, xs, fit, eq, img_path, job_gen)

        def _on_progress(value: int, msg: str) -> None:
            """Handle the on progress helper flow."""
            if not dlg.isVisible():
                return
            progress_bar.setValue(value)
            if msg:
                status_label.setText(msg)

        def _on_result(result) -> None:
            """Handle the on result helper flow."""
            if not dlg.isVisible():
                return
            if result is None:
                return
            means, xs, fit, eq, path, gen = result
            if gen != self._job_generation:
                return
            if pathlib.Path(self.primary_image.path) != path:
                return
            ax.clear()
            ax.plot(xs, means, "o-", label="ROI mean")
            if fit is not None:
                ax.plot(xs, fit, "--", label=eq)
            ax.set_xlabel("Frame")
            ax.set_ylabel("Mean intensity")
            ax.set_title("ROI mean vs frame")
            ax.legend()
            canvas.draw_idle()
            status_label.setText("Done.")

        def _on_error(err: str) -> None:
            """Handle the on error helper flow."""
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Failed. See Logs.")
            self._append_log(f"[JOB] Bleaching analysis error\n{err}")

        token = self._submit_analysis_job(
            _job,
            name="Bleaching analysis",
            on_progress=_on_progress,
            on_result=_on_result,
            on_error=_on_error,
        )

        def _cancel() -> None:
            """Handle the cancel helper flow."""
            token.cancel()
            status_label.setText("Cancelled.")

        cancel_btn.clicked.connect(_cancel)
        dlg.finished.connect(lambda _result: token.cancel())
        dlg.resize(800, 520)
        dlg.show()
        dlg.exec()

    def _show_profile_dialog(self) -> None:
        """Open a dialog showing line profiles (vertical, horizontal, diagonals) raw vs corrected."""
        if self.primary_image.array is None:
            return
        data = self._apply_crop(self._slice_data(self.primary_image))
        if data.ndim > 2:
            data = np.mean(data, axis=-1)
        h, w = data.shape[:2]
        cy, cx = h // 2, w // 2
        vertical = data[:, cx]
        horizontal = data[cy, :]
        diag1 = np.diag(data)
        diag2 = np.diag(np.fliplr(data))

        def _correct(arr: np.ndarray) -> np.ndarray:
            """Handle the correct helper flow."""
            if self.illum_corr_chk.isChecked():
                arr = arr - arr.min()
            if arr.max() > 0:
                arr = arr / arr.max()
            return arr

        fig, axes = plt.subplots(2, 2, figsize=(10, 6))
        axes = axes.ravel()
        for ax, arr, title in [
            (axes[0], vertical, "Vertical"),
            (axes[1], horizontal, "Horizontal"),
            (axes[2], diag1, "Diag TL-BR"),
            (axes[3], diag2, "Diag TR-BL"),
        ]:
            ax.plot(arr, label="raw")
            ax.plot(_correct(arr), label="corrected")
            ax.set_title(title)
            ax.legend()
            ax.set_xlabel("Pixel")
            ax.set_ylabel("Intensity")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Line profiles")
        layout = QtWidgets.QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.resize(900, 600)
        dlg.show()
        dlg.exec()
