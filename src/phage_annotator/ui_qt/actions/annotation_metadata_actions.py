"""Extracted method group 3 for WorkspaceActionsMixin."""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.utils.image_io import read_metadata



class AnnotationMetadataActionsMixin:
    """Method group 3 extracted from WorkspaceActionsMixin."""

    def _apply_annotation_metadata(self, keep_banner: bool = False) -> None:
        """Apply annotation metadata for the current workflow."""
        meta = self._pending_annotation_meta
        image_id = self._pending_annotation_meta_image_id
        if not meta or image_id is None:
            return
        active_primary = self.primary_image.id
        roi = meta.get("roi")
        if isinstance(roi, dict) and image_id == active_primary:
            shape = roi.get("shape", "box")
            rect = roi.get("rect")
            if rect and len(rect) == 4:
                rect = tuple(float(v) for v in rect)
                self.controller.set_roi(rect, shape=str(shape))
                self.roi_rect = rect
                self.roi_shape = str(shape)
            elif shape == "circle":
                center = roi.get("center")
                radius = roi.get("radius")
                if center and radius is not None:
                    cx, cy = center
                    rect = (
                        float(cx - radius),
                        float(cy - radius),
                        float(radius * 2),
                        float(radius * 2),
                    )
                    self.controller.set_roi(rect, shape="circle")
                    self.roi_rect = rect
                    self.roi_shape = "circle"
        crop = meta.get("crop")
        if crop and len(crop) == 4 and image_id == active_primary:
            self.crop_rect = tuple(float(v) for v in crop)
            self.controller.set_crop(self.crop_rect)
            self._sync_crop_controls()
        if image_id == active_primary and roi is not None:
            self._sync_roi_controls()
        display = meta.get("display")
        if isinstance(display, dict):
            non_active_mapping = None
            win = display.get("win")
            if isinstance(win, dict) and "min" in win and "max" in win:
                if image_id == active_primary:
                    self.controller.set_display_mapping(
                        float(win["min"]), float(win["max"]), display.get("gamma")
                    )
                else:
                    non_active_mapping = self.controller.display_mapping.mapping_for(
                        image_id, "frame"
                    )
                    non_active_mapping.set_window(float(win["min"]), float(win["max"]))
            else:
                pct = display.get("pct")
                if (
                    isinstance(pct, dict)
                    and self.primary_image.array is not None
                    and image_id == active_primary
                ):
                    try:
                        low = float(pct.get("low", 2.0))
                        high = float(pct.get("high", 98.0))
                        data = self._slice_data(self.primary_image)
                        vmin = float(np.percentile(data, low))
                        vmax = float(np.percentile(data, high))
                        self.controller.set_display_mapping(vmin, vmax, display.get("gamma"))
                    except (TypeError, ValueError):
                        pass
            gamma = display.get("gamma")
            if gamma is not None:
                try:
                    if image_id == active_primary:
                        self.controller.set_gamma(float(gamma))
                    else:
                        if non_active_mapping is None:
                            non_active_mapping = self.controller.display_mapping.mapping_for(
                                image_id, "frame"
                            )
                        non_active_mapping.gamma = float(gamma)
                except (TypeError, ValueError):
                    pass
            mode = display.get("mode")
            if isinstance(mode, str):
                if image_id == active_primary:
                    mapping = self.controller.display_mapping.mapping_for(image_id, "frame")
                    mapping.mode = mode
                    self.controller.set_display_for_image(image_id, "frame", mapping)
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.mode = mode
            lut = display.get("lut")
            if isinstance(lut, str) and lut in lut_names():
                if image_id == active_primary:
                    self.controller.set_lut(lut_names().index(lut))
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.lut = lut_names().index(lut)
            elif isinstance(lut, int):
                if image_id == active_primary:
                    self.controller.set_lut(lut)
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.lut = lut
            invert = display.get("invert")
            if invert is not None:
                if image_id == active_primary:
                    self.controller.set_invert(bool(invert))
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.invert = bool(invert)
            if non_active_mapping is not None and image_id != active_primary:
                self.controller.set_display_for_image(image_id, "frame", non_active_mapping)
        axis = meta.get("axis")
        if isinstance(axis, str):
            self.controller.set_axis_interpretation(image_id, axis)
            if image_id == active_primary and hasattr(self, "axis_mode_combo"):
                self.axis_mode_combo.setCurrentText(axis)
        if keep_banner:
            if hasattr(self, "annotation_meta_label"):
                self.annotation_meta_label.setText("Metadata applied.")
        else:
            self._dismiss_annotation_meta_banner()
        self._request_ui_refresh("standard-actions")
