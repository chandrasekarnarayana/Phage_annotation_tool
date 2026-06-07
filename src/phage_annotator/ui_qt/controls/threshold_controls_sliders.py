"""Extracted method group 1 for ThresholdControlsMixin."""

from __future__ import annotations

import csv
from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import roi_mask_for_shape
from phage_annotator.analysis.particles import ParticleOptions, analyze_particles
from phage_annotator.analysis.threshold import (
    PostprocessOptions,
    compute_threshold,
    make_mask,
    postprocess_mask,
    smooth_image,
)



class ThresholdControlsSlidersMixin:
    """Method group 1 extracted from ThresholdControlsMixin."""

    def _threshold_method_changed(self) -> None:
        """Handle the threshold method changed helper flow."""
        if self.threshold_panel is None:
            return
        method = self.threshold_panel.method_combo.currentText()
        if method == "Manual":
            self._threshold_refresh_preview()
        else:
            self._threshold_auto()
    def _threshold_manual_changed(self) -> None:
        """Handle the threshold manual changed helper flow."""
        if self.threshold_panel is None:
            return
        if self.threshold_panel.method_combo.currentText() != "Manual":
            return
        self._threshold_timer.start()
    def _threshold_refresh_preview(self) -> None:
        """Handle the threshold refresh preview helper flow."""
        if self.threshold_panel is None:
            return
        values = self.threshold_panel.values()
        if not values.preview:
            self._threshold_preview_mask = None
            self._threshold_preview_extent = None
            self._request_ui_refresh("threshold-controls")
            return

        image = self._threshold_source_image(values.target)
        if image is None:
            self.threshold_panel.status_label.setText("No image data.")
            return
        crop_offset = self._threshold_crop_offset(image.shape)
        data, roi_mask = self._threshold_apply_roi(image, values, crop_offset)
        if data is None:
            self.threshold_panel.status_label.setText("ROI empty.")
            return

        smooth = smooth_image(data, values.smooth_sigma)
        if values.method == "Manual":
            low, high = self._threshold_percentile_bounds(smooth, values, roi_mask)
            thr_low = low
            thr_high = high
        else:
            thr = self._threshold_auto_value
            if thr is None or np.isnan(thr):
                return
            thr_low = float(thr)
            thr_high = None

        mask = make_mask(smooth, thr_low, thr_high, invert=values.invert_mask)
        opts = PostprocessOptions(
            min_area_px=values.min_area_px,
            fill_holes=values.fill_holes,
            open_radius_px=values.open_radius_px,
            close_radius_px=values.close_radius_px,
            despeckle=values.despeckle,
            watershed_split=values.watershed_split,
        )
        mask = postprocess_mask(mask, opts)
        self._threshold_preview_mask = mask
        self._threshold_preview_extent = (0, mask.shape[1], mask.shape[0], 0)
        self._threshold_mask_full = self._threshold_to_full_mask(mask, crop_offset, image.shape)
        self._threshold_settings = values.__dict__
        self.controller.set_threshold_preview_settings(
            self.primary_image.id,
            dict(self._threshold_settings),
        )
        self._append_log(self._threshold_log_message(values, self._threshold_auto_value))
        self.recorder.record("threshold_preview", self._threshold_settings)
        self._request_ui_refresh("threshold-controls")
    def _threshold_auto(self) -> None:
        """Handle the threshold auto helper flow."""
        if self.threshold_panel is None:
            return
        values = self.threshold_panel.values()
        if values.method == "Manual":
            return
        if self._threshold_job_id is not None:
            self.jobs.cancel(self._threshold_job_id)
            self._threshold_job_id = None

        image = self._threshold_source_image(values.target)
        if image is None:
            self.threshold_panel.status_label.setText("No image data.")
            return
        crop_offset = self._threshold_crop_offset(image.shape)
        data, roi_mask = self._threshold_apply_roi(image, values, crop_offset)
        if data is None:
            self.threshold_panel.status_label.setText("ROI empty.")
            return

        def _job(progress, cancel_token):
            """Handle the job helper flow."""
            pixels = self._threshold_sample_pixels(values, roi_mask, data)
            if cancel_token.is_cancelled():
                return float("nan")
            thr = compute_threshold(pixels, values.method, background=values.background)
            return float(thr)

        def _on_result(result: float) -> None:
            """Handle the on result helper flow."""
            self._threshold_auto_value = result
            if result is None or np.isnan(result):
                self.threshold_panel.status_label.setText("Auto method unavailable.")
                self.threshold_panel.auto_value.setText("Auto: —")
                return
            self.threshold_panel.auto_value.setText(f"Auto: {result:.4f}")
            self.recorder.record(
                "threshold_auto",
                {
                    "method": values.method,
                    "value": float(result),
                    "region_roi": values.region_roi,
                    "scope": values.scope,
                },
            )
            self._threshold_refresh_preview()

        def _on_error(err: str) -> None:
            """Handle the on error helper flow."""
            self.threshold_panel.status_label.setText("Auto threshold failed.")
            self._append_log(f"[Threshold] Error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Threshold Auto",
            on_result=_on_result,
            on_error=_on_error,
            priority="interactive",
            replace_key="threshold-auto",
        )
        self._threshold_job_id = handle.job_id
        self.threshold_panel.status_label.setText(f"Computing {values.method}…")
    def _threshold_source_image(self, target: str) -> Optional[np.ndarray]:
        """Handle the threshold source image helper flow."""
        prim = self.primary_image
        if prim.array is None:
            return None
        if target == "Frame":
            return self._slice_data(prim)
        if target in {"Mean", "Mean Projection"}:
            data, _ = self._get_projection(prim, "mean")
            return data
        if target in {"Support", "Modality 2"}:
            if self.support_image.array is None:
                return None
            return self._slice_data(self.support_image)
        return self._slice_data(prim)
    def _threshold_crop_offset(self, shape: Tuple[int, int]) -> Tuple[int, int]:
        """Handle the threshold crop offset helper flow."""
        if not self.crop_rect:
            return (0, 0)
        x, y, _, _ = self.crop_rect
        return (int(max(0, x)), int(max(0, y)))
    def _threshold_apply_roi(
        self, image: np.ndarray, values, crop_offset: Tuple[int, int]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Handle the threshold apply roi helper flow."""
        data = image
        if self.crop_rect:
            data = self._apply_crop_rect(data, self.crop_rect, image.shape)
        roi_mask = None
        if values.region_roi:
            x0, y0 = crop_offset
            if self.roi_rect is None:
                return None, None
            roi_rect = (self.roi_rect[0] - x0, self.roi_rect[1] - y0, self.roi_rect[2], self.roi_rect[3])
            roi_mask = roi_mask_for_shape(data.shape, roi_rect, self.roi_shape)
            if not roi_mask.any():
                return None, None
        return data, roi_mask
    def _threshold_percentile_bounds(
        self, data: np.ndarray, values, roi_mask: Optional[np.ndarray]
    ) -> Tuple[float, float]:
        """Handle the threshold percentile bounds helper flow."""
        sample = data[roi_mask] if roi_mask is not None else data.ravel()
        low = float(np.percentile(sample, values.manual_low_pct))
        high = float(np.percentile(sample, values.manual_high_pct))
        return low, high
    def _threshold_sample_pixels(self, values, roi_mask: Optional[np.ndarray], data: np.ndarray) -> np.ndarray:
        """Handle the threshold sample pixels helper flow."""
        if values.scope == "Current slice":
            sample = data[roi_mask] if roi_mask is not None else data
            return sample.ravel()

        prim = self.primary_image
        if prim.array is None:
            return data.ravel()
        t_count = int(prim.array.shape[0])
        n = min(values.sample_count, t_count)
        # Deterministic frame selection for reproducibility (P3.2)
        idxs = np.linspace(0, t_count - 1, n).astype(int)
        pixels = []
        for t in idxs:
            frame = prim.array[t, self.z_slider.value(), :, :]
            if self.crop_rect:
                frame = self._apply_crop_rect(frame, self.crop_rect, frame.shape)
            if roi_mask is not None:
                pixels.append(frame[roi_mask])
            else:
                pixels.append(frame.ravel())
        if not pixels:
            return np.array([])
        return np.concatenate(pixels)
    def _threshold_to_full_mask(
        self, mask: np.ndarray, crop_offset: Tuple[int, int], full_shape: Tuple[int, int]
    ) -> np.ndarray:
        """Handle the threshold to full mask helper flow."""
        full = np.zeros(full_shape, dtype=bool)
        x0, y0 = crop_offset
        y1 = min(full_shape[0], y0 + mask.shape[0])
        x1 = min(full_shape[1], x0 + mask.shape[1])
        full[y0:y1, x0:x1] = mask[: y1 - y0, : x1 - x0]
        return full
