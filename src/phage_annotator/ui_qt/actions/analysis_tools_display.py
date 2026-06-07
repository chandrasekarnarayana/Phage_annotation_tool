"""Extracted method group 16 for ActionsMixin."""

from __future__ import annotations

import gc
import json
import logging
import os
import pathlib
import time
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.assist_context import AssistContextMixin
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.actions.assist_strategy import AssistStrategyMixin
from phage_annotator.ui_qt.actions.standard_workspace import WorkspaceActionsMixin
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.actions.dock_actions import DockActionsMixin
from phage_annotator.ui_qt.actions.export_actions import ExportActionsMixin
from phage_annotator.ui_qt.actions.navigation_actions import NavigationActionsMixin
from phage_annotator.ui_qt.actions.qc_actions import QCActionsMixin
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.io.metadata.reader import MetadataBundle


logger = logging.getLogger(__name__)



class AnalysisToolsDisplayMixin:
    """Method group 16 extracted from ActionsMixin."""

    def _show_table_dialog(self) -> None:
        """Open a dialog with a table of file names and ROI mean; allow CSV export."""
        # Prefer last opened folder; otherwise use currently loaded images.
        candidates: List[pathlib.Path] = []
        if self._last_folder and self._last_folder.exists():
            candidates = sorted(
                [
                    p
                    for p in self._last_folder.iterdir()
                    if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")
                ]
            )
        if not candidates:
            candidates = [img.path for img in self.images]
        if not candidates:
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("ROI mean table")
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

        table = QtWidgets.QTableWidget(len(candidates), 2)
        table.setHorizontalHeaderLabels(["File", "ROI mean"])
        for i, p in enumerate(candidates):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(p.name))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem("…"))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        export_btn = QtWidgets.QPushButton("Export CSV")
        layout.addWidget(export_btn)

        rows: List[dict] = [{"file": p.name, "roi_mean": float("nan")} for p in candidates]

        def _export() -> None:
            """Export export for the current workflow."""
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export ROI means",
                str(pathlib.Path.cwd() / "roi_means.csv"),
                "CSV Files (*.csv)",
            )
            if path:
                pd.DataFrame(rows).to_csv(path, index=False)

        export_btn.clicked.connect(_export)
        export_btn.setEnabled(False)

        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        crop_rect = self.crop_rect
        job_gen = self._job_generation

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            total = max(1, len(candidates))
            for idx, path in enumerate(candidates):
                if cancel_token.is_cancelled():
                    return None
                roi_mean = compute_roi_mean_for_path(str(path), roi_rect, roi_shape, crop_rect)
                pct = int((idx + 1) / total * 100)
                progress(pct, f"row:{idx}:{roi_mean}")
            return "done"

        def _on_progress(value: int, msg: str) -> None:
            """Handle the on progress helper flow."""
            if not dlg.isVisible():
                return
            progress_bar.setValue(value)
            if msg.startswith("row:"):
                try:
                    _, idx_s, mean_s = msg.split(":", 2)
                    idx = int(idx_s)
                    mean_val = float(mean_s)
                except ValueError:
                    return
                if 0 <= idx < len(rows):
                    rows[idx]["roi_mean"] = mean_val
                    table.setItem(idx, 1, QtWidgets.QTableWidgetItem(f"{mean_val:.3f}"))
            status_label.setText("Computing ROI means…")

        def _on_result(_result) -> None:
            """Handle the on result helper flow."""
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Done.")
            export_btn.setEnabled(True)

        def _on_error(err: str) -> None:
            """Handle the on error helper flow."""
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Failed. See Logs.")
            self._append_log(f"[JOB] ROI mean table error\n{err}")

        token = self._submit_analysis_job(
            _job,
            name="ROI mean table",
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
        dlg.resize(500, 300)
        dlg.show()
        dlg.exec()
    def _compute_roi_mean_for_path(self, path: pathlib.Path) -> float:
        """Compute ROI mean for the given TIFF path with minimal memory use."""
        try:
            return compute_roi_mean_for_path(
                str(path), self.roi_rect, self.roi_shape, self.crop_rect
            )
        except Exception:
            return float("nan")
    def _clear_cache(self) -> None:
        """Clear all lazy image data (arrays + projections) and refresh the view."""
        self.stop_playback_t()
        cleared = 0
        self.proj_cache.clear()
        for img in self.images:
            if img.array is not None or img.mean_proj is not None or img.std_proj is not None:
                cleared += 1
            self._evict_image_cache(img)
        gc.collect()
        debug_log(f"Cleared cached data for {cleared} images")
        self._status_success(
            f"Cleared cached image data for {cleared} images.",
            timeout_ms=3000,
            source="standard.clear_cache",
        )
        # Will lazily reload the active images after purge.
        self._request_ui_refresh("standard-actions")
    def _show_smlm_panel(self) -> None:
        """Show the SMLM parameter panel."""
        if self.dock_smlm is not None:
            self.set_panel_visible("smlm", True, source="advanced_panel")
            self.dock_smlm.raise_()
            if getattr(self, "smlm_panel", None) is not None:
                self.smlm_panel.tabs.setCurrentIndex(0)
    def _show_deepstorm_panel(self) -> None:
        """Show the Deep-STORM parameter panel."""
        if getattr(self, "dock_smlm", None) is not None:
            self.set_panel_visible("smlm", True, source="advanced_panel")
            self.dock_smlm.raise_()
        if getattr(self, "smlm_panel", None) is not None:
            self.smlm_panel.tabs.setCurrentIndex(1)
    def _show_threshold_panel(self) -> None:
        """Show the Threshold panel."""
        if getattr(self, "dock_threshold", None) is not None:
            self.set_panel_visible("threshold", True, source="advanced_panel")
            self.dock_threshold.raise_()
    def _show_analyze_particles_panel(self) -> None:
        """Show the Analyze Particles panel."""
        if getattr(self, "dock_particles", None) is not None:
            self.set_panel_visible("particles", True, source="advanced_panel")
            self.dock_particles.raise_()
