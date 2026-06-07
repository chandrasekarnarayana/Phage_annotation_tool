"""Extracted method group 6 for DisplayControlsMixin."""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_auto_window
from phage_annotator.session.signal_hub import emit_display_changed, emit_view_changed
from phage_annotator.session.modality import ProjectionType
from phage_annotator.session.multi_playback import PlaybackMode
from phage_annotator.ui_qt.controls.display_contrast import DisplayContrastMixin
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger



class HistogramContrastAutosetMixin:
    """Method group 6 extracted from DisplayControlsMixin."""

    def _auto_contrast(self) -> None:
        """Run auto contrast with a quick preview and background job."""
        prim = self.primary_image
        if prim.array is None:
            return
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        use_roi = self.auto_roi_chk.isChecked()
        scope = self.auto_scope_combo.currentText()
        panel_ids = self._contrast_target_panels()

        if not panel_ids:
            return

        source_panel = str(getattr(self, "annotate_target", "")).strip().lower()
        if not source_panel:
            source_panel = panel_ids[0] if panel_ids else "modality_0"
        if source_panel not in panel_ids:
            source_panel = panel_ids[0]
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(source_panel)
        if modality is not None:
            auto_img = self._image_obj_from_id(int(modality.image_id))
        else:
            auto_img = self.primary_image
        if auto_img is None:
            return
        if auto_img.array is None:
            self._ensure_loaded(auto_img.id)
            if auto_img.array is None:
                return

        # Quick preview on current slice (downsampled).
        slice_data = self._slice_data(auto_img)
        roi_mask = self._roi_mask(slice_data.shape) if use_roi else None
        stride = max(1, self.downsample_factor)
        quick = slice_data[::stride, ::stride]
        quick_mask = roi_mask[::stride, ::stride] if roi_mask is not None else None
        vmin, vmax = compute_auto_window(quick, low_pct, high_pct, roi_mask=quick_mask)
        self._apply_auto_to_panels(panel_ids, vmin, vmax)
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")

        if self._auto_job_id is not None:
            self.jobs.cancel(self._auto_job_id)
            self._auto_job_id = None

        self._bump_job_generation()
        job_gen = self._job_generation

        def _sample_stack() -> np.ndarray:
            """Handle the sample stack helper flow."""
            arr = auto_img.array
            if arr is None:
                return np.array([], dtype=np.float32)
            t_count, z_count = arr.shape[0], arr.shape[1]
            samples = []
            roi_mask_local = None
            if scope == "All frames":
                t_step = max(1, t_count // 16)
                z_idx = self.z_slider.value()
                for t in range(0, t_count, t_step):
                    frame = arr[t, z_idx, :, :]
                    if use_roi:
                        if roi_mask_local is None:
                            roi_mask_local = self._roi_mask(frame.shape)
                        samples.append(frame[roi_mask_local])
                    else:
                        samples.append(frame.ravel())
            elif scope == "Whole image":
                t_step = max(1, t_count // 8)
                z_step = max(1, z_count // 8)
                for t in range(0, t_count, t_step):
                    for z in range(0, z_count, z_step):
                        frame = arr[t, z, :, :]
                        if use_roi:
                            if roi_mask_local is None:
                                roi_mask_local = self._roi_mask(frame.shape)
                            samples.append(frame[roi_mask_local])
                        else:
                            samples.append(frame.ravel())
            else:
                t = self.t_slider.value()
                z = self.z_slider.value()
                frame = arr[t, z, :, :]
                if use_roi:
                    roi_mask_local = self._roi_mask(frame.shape)
                    samples.append(frame[roi_mask_local])
                else:
                    samples.append(frame.ravel())
            if not samples:
                return np.array([], dtype=np.float32)
            sample = np.concatenate(samples)
            if sample.size > 200000:
                # Deterministic sampling for reproducibility (P3.2)
                rng = np.random.default_rng(42)
                idx = rng.choice(sample.size, size=200000, replace=False)
                sample = sample[idx]
            return sample

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            if cancel_token.is_cancelled():
                return None
            vmin_full, vmax_full = compute_auto_window(_sample_stack, low_pct, high_pct)
            if cancel_token.is_cancelled():
                return None
            return vmin_full, vmax_full, job_gen

        def _on_result(result) -> None:
            """Handle the on result helper flow."""
            if result is None:
                return
            vmin_full, vmax_full, gen = result
            if gen != self._job_generation:
                return
            self._apply_auto_to_panels(panel_ids, vmin_full, vmax_full)
            if hasattr(self, "_schedule_refresh"):
                self._schedule_refresh()
            else:
                self._request_ui_refresh("display-controls")

        def _on_error(err: str) -> None:
            """Handle the on error helper flow."""
            self._append_log(f"[JOB] Auto contrast error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Auto contrast",
            on_result=_on_result,
            on_error=_on_error,
            priority="interactive",
            replace_key="auto-contrast",
        )
        self._auto_job_id = handle.job_id
    def _auto_contrast_panel(self, panel_key: str) -> None:
        """Apply a quick auto-contrast window to one panel immediately."""
        key = str(panel_key or "").strip().lower()
        if not key:
            return
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(key)
        if modality is not None:
            auto_img = self._image_obj_from_id(int(modality.image_id))
        elif key == "support":
            auto_img = getattr(self, "support_image", None)
        else:
            auto_img = getattr(self, "primary_image", None)
        if auto_img is None:
            return
        if auto_img.array is None:
            self._ensure_loaded(auto_img.id)
            if auto_img.array is None:
                return
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        slice_data = self._slice_data(auto_img)
        stride = max(1, int(getattr(self, "downsample_factor", 1)))
        quick = slice_data[::stride, ::stride]
        vmin, vmax = compute_auto_window(quick, low_pct, high_pct)
        self._apply_auto_to_panels([key], vmin, vmax)
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")
    def _apply_auto_to_panels(
        self, panel_ids: List[str], vmin: float, vmax: float
    ) -> None:
        """Apply auto to panels for the current workflow."""
        panel_map = getattr(self, "_panel_modality_map", {})
        for panel in panel_ids:
            modality = panel_map.get(panel)
            if modality is not None:
                image_id = modality.image_id
                img = self._image_obj_from_id(image_id)
                if img is None:
                    continue
                data = img.array if img.array is not None else img
            else:
                image_id = (
                    self.support_image.id if panel == "support" else self.primary_image.id
                )
                data = (
                    self.support_image.array
                    if panel == "support"
                    else self.primary_image.array
                )
            mapping = self._get_display_mapping(image_id, panel, data)
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings(panel, mapping)
    def _mark_dirty(self, dirty: bool = True) -> None:
        """Mark dirty for the current workflow."""
        self._annotations_dirty = dirty
        if dirty and hasattr(self, "_note_annotation_edit"):
            try:
                self._note_annotation_edit(self.primary_image.id)
            except Exception:
                pass
    def _autosave_tick(self) -> None:
        """Handle the autosave tick helper flow."""
        path = self.controller.autosave_if_needed(self, self._current_keypoints)
        if path is None:
            return
        self._last_autosave_path = str(path)
        self._last_autosave_timestamp = time.time()
        self._append_log(f"[RECOVERY] Autosaved annotations to {path}")
        self._status_success(
            "Autosaved recovery file.",
            timeout_ms=2500,
            source="display.autosave",
        )
    def _check_recovery(self) -> None:
        """Check recovery for the current workflow."""
        recovery = self.controller.find_recovery_file(self._current_keypoints)
        if recovery is None:
            return
        resp = QtWidgets.QMessageBox.question(
            self,
            "Recovery found",
            "A newer recovery file was found. Restore annotations?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if resp == QtWidgets.QMessageBox.StandardButton.Yes:
            self.controller.restore_recovery(recovery)
            self._request_ui_refresh("display-controls")
