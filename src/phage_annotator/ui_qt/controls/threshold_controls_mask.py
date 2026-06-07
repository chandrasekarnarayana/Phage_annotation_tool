"""Extracted method group 2 for ThresholdControlsMixin."""

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



class ThresholdControlsMaskMixin:
    """Method group 2 extracted from ThresholdControlsMixin."""

    def _threshold_create_mask(self) -> None:
        """Handle the threshold create mask helper flow."""
        if self._threshold_mask_full is None:
            self._status_warning("No threshold mask to save.", source="threshold.create_mask")
            return
        image_id = self.primary_image.id
        # Phase 7: Store read-only view to avoid 8MB copy per mask
        # Operations like `mask & roi_mask` will create new arrays as needed
        from phage_annotator.utils import readonly_view
        self.controller.store_threshold_mask(
            image_id,
            {
                "t": int(self.t_slider.value()),
                "z": int(self.z_slider.value()),
                "mask": readonly_view(self._threshold_mask_full),
            },
        )
        self._status_success(
            "Threshold mask stored for current slice.",
            source="threshold.create_mask",
        )
        if self.threshold_panel is not None:
            self._append_log(self._threshold_log_message(self.threshold_panel.values(), self._threshold_auto_value))
            self.recorder.record("threshold_create_mask", self._threshold_settings)
    def _threshold_create_roi(self) -> None:
        """Handle the threshold create roi helper flow."""
        if self._threshold_mask_full is None:
            self._status_warning("No threshold mask to convert.", source="threshold.create_roi")
            return
        mask = self._threshold_mask_full
        try:
            from scipy import ndimage as ndi
        except Exception:
            ndi = None
        if ndi is None:
            ys, xs = np.nonzero(mask)
            if ys.size == 0:
                self._status_warning("Mask empty.", source="threshold.create_roi")
                return
            x0, x1 = xs.min(), xs.max()
            y0, y1 = ys.min(), ys.max()
        else:
            labeled, n = ndi.label(mask)
            if n == 0:
                self._status_warning("Mask empty.", source="threshold.create_roi")
                return
            sizes = ndi.sum(mask, labeled, range(1, n + 1))
            idx = int(np.argmax(sizes)) + 1
            ys, xs = np.nonzero(labeled == idx)
            x0, x1 = xs.min(), xs.max()
            y0, y1 = ys.min(), ys.max()
        rect = (float(x0), float(y0), float(x1 - x0), float(y1 - y0))
        self.controller.set_roi(rect, shape="box")
        self.roi_shape = "box"
        self.roi_rect = rect
        self._sync_roi_controls()
        self._request_ui_refresh("threshold-controls")
    def _threshold_analyze_particles(self) -> None:
        """Handle the threshold analyze particles helper flow."""
        self._show_analyze_particles_panel()
    def _threshold_apply_destructive(self) -> None:
        """Handle the threshold apply destructive helper flow."""
        if self.threshold_panel is None:
            return
        if self._threshold_preview_mask is None:
            self._status_warning("No threshold preview to apply.", source="threshold.apply")
            return
        # P1.4: Confirmation with "Don't show again" toggle stored in settings
        if self._settings.value("confirmApplyThreshold", True, type=bool):
            mbox = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Question,
                "Apply Threshold",
                "Replace the current view with a binary mask layer?",
                parent=self,
            )
            mbox.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
            )
            dont = QtWidgets.QCheckBox("Don't show again")
            mbox.setCheckBox(dont)
            resp = mbox.exec()
            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            if dont.isChecked():
                self._settings.setValue("confirmApplyThreshold", False)
        if self._threshold_mask_full is None:
            image = self._threshold_source_image(self.threshold_panel.values().target)
            if image is None:
                return
            crop_offset = self._threshold_crop_offset(image.shape)
            self._threshold_mask_full = self._threshold_to_full_mask(
                self._threshold_preview_mask, crop_offset, image.shape
            )
        self._binary_view_mask = self._threshold_mask_full
        self._binary_view_enabled = True
        self._threshold_preview_mask = None
        self._threshold_preview_extent = None
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._status_success("Binary mask applied to view.", source="threshold.apply")
        self.recorder.record("threshold_apply", self._threshold_settings)
        self._append_log(self._threshold_log_message(self.threshold_panel.values(), self._threshold_auto_value))
        self._request_ui_refresh("threshold-controls")
