"""Extracted method group 5 for SmlmControlsMixin."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import pathlib
import platform
import subprocess
import sys
import textwrap
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.deepstorm.infer import DeepStormParams, is_torch_available, run_deepstorm_stream
from phage_annotator.smlm.backends import (
    ThunderstormBridgeConfig,
    discover_bundled_thunderstorm_jar,
    run_thunderstorm_backend,
)
from phage_annotator.smlm.reproducibility import (
    ReproducibilityRunbookState,
    append_provenance_event,
    export_reproducibility_bundle,
    lock_profile,
    resolve_profile,
)
from phage_annotator.smlm.preflight import report_to_text, run_preflight
from phage_annotator.smlm.external_plugins import parse_plugins_config_from_jar
from phage_annotator.smlm.thunderstorm import SmlmParams



class SmlmControlsFilteringMixin:
    """Method group 5 extracted from SmlmControlsMixin."""

    def _run_deepstorm(self) -> None:
        """Run deepstorm for the current workflow."""
        if self.smlm_panel is None:
            return
        deep = self.smlm_panel.deep
        if not is_torch_available():
            deep.status_label.setText("PyTorch not available.")
            return
        
        # Check GPU availability before running inference
        from phage_annotator.tools.utils.gpu_utils import check_cuda_available
        params_check = self._deepstorm_params_from_ui()
        if params_check and params_check.device in ("cuda", "auto"):
            cuda_ok, cuda_msg = check_cuda_available()
            if not cuda_ok and params_check.device == "cuda":
                from matplotlib.backends.qt_compat import QtWidgets
                QtWidgets.QMessageBox.warning(
                    self, 
                    "CUDA Not Available",
                    f"Cannot run Deep-STORM on GPU:\n\n{cuda_msg}\n\nPlease select 'CPU' device or install CUDA support."
                )
                return
            elif not cuda_ok and params_check.device == "auto":
                deep.status_label.setText("Running on CPU (CUDA unavailable)")
        
        self._ensure_loaded(self.current_image_idx)
        if self.primary_image.array is None:
            deep.status_label.setText("Load an image first.")
            return
        params = self._deepstorm_params_from_ui()
        if params is None or not params.model_path:
            deep.status_label.setText("Select a model first.")
            return
        roi_rect = self.roi_rect
        if roi_rect is None or roi_rect[2] <= 0 or roi_rect[3] <= 0:
            deep.status_label.setText("Set an ROI first.")
            if self.dock_roi is not None:
                self.set_panel_visible("roi", True, source="deepstorm_validation")
            return
        
        # Phase ζ: Get selected modality_idx from panel
        selected_modality_idx = self.smlm_panel.get_selected_modality_idx()
        self._deepstorm_modality_idx = selected_modality_idx
        
        err, warn = self._validate_deepstorm_params(params)
        if err:
            deep.status_label.setText(err)
            return
        if warn:
            deep.status_label.setText(warn)

        self.stop_playback_t()
        self._cancel_deepstorm()
        arr = self.primary_image.array
        t_count = int(arr.shape[0])
        _, z_idx = self._slice_indices(self.primary_image)
        full_h, full_w = arr.shape[2], arr.shape[3]
        if self.crop_rect is None or self.crop_rect[2] <= 0 or self.crop_rect[3] <= 0:
            x0, y0, x1, y1 = 0, 0, full_w, full_h
        else:
            cx, cy, cw, ch = self.crop_rect
            x0 = int(max(0, cx))
            y0 = int(max(0, cy))
            x1 = int(min(full_w, cx + cw))
            y1 = int(min(full_h, cy + ch))
        if x1 <= x0 or y1 <= y0:
            deep.status_label.setText("Crop has zero area.")
            return
        crop_offset = (x0, y0)
        roi_rect_crop = (roi_rect[0] - x0, roi_rect[1] - y0, roi_rect[2], roi_rect[3])
        crop_w = x1 - x0
        crop_h = y1 - y0
        rx0 = max(0.0, roi_rect_crop[0])
        ry0 = max(0.0, roi_rect_crop[1])
        rx1 = min(float(crop_w), roi_rect_crop[0] + roi_rect_crop[2])
        ry1 = min(float(crop_h), roi_rect_crop[1] + roi_rect_crop[3])
        if rx1 <= rx0 or ry1 <= ry0:
            deep.status_label.setText("ROI has no pixels in crop.")
            return
        eff_roi_full = (rx0 + x0, ry0 + y0, rx1 - rx0, ry1 - ry0)
        job_gen = self._job_generation
        image_id = self.primary_image.id
        self._deepstorm_run_id += 1
        run_id = self._deepstorm_run_id
        device = "cuda" if is_torch_available() and self._torch_has_cuda() else "cpu"
        model_hash = self._hash_file(params.model_path)
        self._record_smlm_run(
            "Deep-STORM",
            params.__dict__,
            eff_roi_full,
            self.crop_rect,
            {"path": params.model_path, "hash": model_hash},
        )

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            def _frames():
                """Handle the frames helper flow."""
                for t in range(t_count):
                    if cancel_token.is_cancelled():
                        break
                    frame = arr[t, z_idx, :, :]
                    if x0 != 0 or y0 != 0 or x1 != full_w or y1 != full_h:
                        frame = frame[y0:y1, x0:x1]
                    if rx0 > 0 or ry0 > 0 or rx1 < crop_w or ry1 < crop_h:
                        frame = frame[int(ry0):int(ry1), int(rx0):int(rx1)]
                    yield (t, frame)

            def _progress_cb(val: int, msg: str) -> None:
                """Handle the progress cb helper flow."""
                progress(val, msg)

            sr, locs = run_deepstorm_stream(
                _frames(),
                total_frames=t_count,
                roi_rect=eff_roi_full,
                params=params,
                device=device,
                progress_cb=_progress_cb,
                is_cancelled=cancel_token.is_cancelled,
            )
            return (sr, locs, eff_roi_full, crop_offset, image_id, job_gen, run_id, t_count)

        def _on_result(result) -> None:
            """Handle the on result helper flow."""
            if result is None:
                return
            sr, locs, roi_rect_full, crop_off, img_id, gen, res_run_id, frames = result
            if gen != self._job_generation or img_id != self.primary_image.id or res_run_id != self._deepstorm_run_id:
                return
            self._deepstorm_results = locs
            self._deepstorm_image_id = img_id  # Track which image these results are for
            self._deepstorm_overlay = sr
            off_x, off_y = crop_off
            self._deepstorm_overlay_extent = (
                roi_rect_full[0] - off_x,
                roi_rect_full[0] - off_x + roi_rect_full[2],
                roi_rect_full[1] - off_y + roi_rect_full[3],
                roi_rect_full[1] - off_y,
            )
            self._sr_overlay = self._deepstorm_overlay
            self._sr_overlay_extent = self._deepstorm_overlay_extent
            deep.status_label.setText(f"Done: {len(locs)} localizations")
            deep.progress.setValue(100)
            deep.run_btn.setEnabled(True)
            deep.cancel_btn.setEnabled(False)
            self._append_log(
                f"[SMLM] Deep-STORM job={self._deepstorm_job_id} frames={frames} detections={len(locs)}"
            )
            self._request_ui_refresh("smlm-controls")

        def _on_error(err: str) -> None:
            """Handle the on error helper flow."""
            deep.status_label.setText("Error (see Logs).")
            deep.run_btn.setEnabled(True)
            deep.cancel_btn.setEnabled(False)
            self._append_log(f"[Deep-STORM] Error\n{err}")

        def _on_progress(val: int, msg: str) -> None:
            """Handle the on progress helper flow."""
            deep.progress.setValue(val)
            if msg:
                deep.status_label.setText(msg)

        handle = self.jobs.submit(
            _job,
            name="Deep-STORM (ROI)",
            on_result=_on_result,
            on_error=_on_error,
            on_progress=_on_progress,
            timeout_sec=900.0,
            retries=2,  # P5.3: Increased from 1 to handle transient errors
            priority="interactive",
            replace_key="deepstorm-roi",
        )
        self._deepstorm_job_id = handle.job_id
        deep.progress.setValue(0)
        deep.status_label.setText(f"Running on {device}…")
        deep.run_btn.setEnabled(False)
        deep.cancel_btn.setEnabled(True)
        self._append_log(f"[SMLM] Deep-STORM started job={self._deepstorm_job_id} frames={t_count}")
    def _cancel_deepstorm(self) -> None:
        """Handle the cancel deepstorm helper flow."""
        if self._deepstorm_job_id is None:
            return
        self.jobs.cancel(self._deepstorm_job_id)
        self._deepstorm_job_id = None
        if self.smlm_panel is not None:
            deep = self.smlm_panel.deep
            deep.status_label.setText("Cancelling…")
            deep.cancel_btn.setEnabled(False)
            deep.run_btn.setEnabled(True)
    def _export_deepstorm_csv(self) -> None:
        """Export deepstorm csv for the current workflow."""
        if not self._deepstorm_results:
            if self.smlm_panel is not None:
                self.smlm_panel.deep.status_label.setText("No Deep-STORM results.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Deep-STORM CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x_px", "y_px", "score"])
            for loc in self._deepstorm_results:
                writer.writerow([f"{loc.x_px:.4f}", f"{loc.y_px:.4f}", f"{loc.score:.4f}"])
        if self.smlm_panel is not None:
            self.smlm_panel.deep.status_label.setText(f"Exported CSV: {path}")
    def _export_deepstorm_sr(self) -> None:
        """Export deepstorm sr for the current workflow."""
        if self._deepstorm_overlay is None:
            if self.smlm_panel is not None:
                self.smlm_panel.deep.status_label.setText("No SR image to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export SR Image", "", "TIFF Files (*.tif);;PNG Files (*.png)"
        )
        if not path:
            return
        if path.lower().endswith(".png"):
            from matplotlib import pyplot as plt

            plt.imsave(path, self._deepstorm_overlay, cmap="magma")
        else:
            import tifffile as tif

            tif.imwrite(path, self._deepstorm_overlay.astype(np.float32, copy=False))
        if self.smlm_panel is not None:
            self.smlm_panel.deep.status_label.setText(f"Exported SR image: {path}")
