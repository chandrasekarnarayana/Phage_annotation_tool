"""State proxy and image helpers for the GUI.

This module provides a mixin that centralizes access to session state via properties,
simplifying GUI logic by abstracting controller calls. It also contains image loading
and coordinate transformation utilities that bridge full-resolution and displayed data.

Coordinate Conventions
----------------------
- Full-resolution: (y, x) in the original numpy array, 0-indexed
- Display/crop: (y, x) after cropping but before downsampling
- Downsampled: After pyramid downsampling; scale factor depends on level
- Canvas (matplotlib): (x, y) with potential axis inversions

All transforms are designed to be bijective; roundtrip errors <0.1 pixel expected.

Key State Proxies
-----------------
- images: List of LazyImage objects (metadata + lazy-loaded arrays)
- annotations: Dict[image_id] -> List[Keypoint] (observed keypoints)
- axis_mode: Dict[image_id] -> "time" | "depth" (3D axis interpretation)
- display_mapping: Per-image, per-panel brightness/contrast/LUT settings

Thread Safety
-------------
- All state proxies delegate to SessionController (main thread)
- Image array loading may occur in background (read_contiguous_block)
- Projection caching is thread-aware via CancelTokenShim
"""

from __future__ import annotations

import pathlib
from types import MappingProxyType
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from matplotlib.backends.qt_compat import QtCore

from phage_annotator.analysis.core import compute_projection, compute_projections
from phage_annotator.annotation.core import Keypoint, PointSuggestion
from phage_annotator.io.data.calibration import CalibrationState
from phage_annotator.ui_qt.utils.constants import PROJECTION_ASYNC_BYTES, CancelTokenShim
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import load_array
from phage_annotator.io import read_contiguous_block
from phage_annotator.data.pyramid import downsample_mean_pool, pyramid_level_factor

if TYPE_CHECKING:
    from phage_annotator.data.models import LazyImage

class StatePropertiesMixin:
    """Observable state properties and simple typed accessors."""

    def images(self, value: List["LazyImage"]) -> None:
        """Document the images flow."""
        self.controller.set_images(value)

    def labels(self) -> List[str]:
        """Document the labels flow."""
        return list(self.controller.session_state.labels)

    def current_label(self, label: str) -> None:
        """Document the current_label flow."""
        self.controller.set_current_label(label)

    def annotations(self) -> Dict[int, List[Keypoint]]:
        """Document the annotations flow."""
        return MappingProxyType(
            {int(k): tuple(v) for k, v in self.controller.session_state.annotations.items()}
        )

    def suggestions(self) -> Dict[int, List[PointSuggestion]]:
        """Document the suggestions flow."""
        return MappingProxyType(
            {int(k): tuple(v) for k, v in self.controller.session_state.suggestions.items()}
        )

    def axis_mode(self) -> Dict[int, str]:
        """Document the axis_mode flow."""
        return {k: v.axis_mode for k, v in self.controller.session_state.image_states.items()}

    def current_image_idx(self, value: int) -> None:
        """Document the current_image_idx flow."""
        self.controller.set_primary(value)

    def support_image_idx(self, value: int) -> None:
        """Document the support_image_idx flow."""
        self.controller.set_support(value)

    def current_cmap_idx(self, value: int) -> None:
        """Document the current_cmap_idx flow."""
        self.controller.set_lut(value)

    def _last_vmin(self, value: float) -> None:
        """Document the last_vmin flow."""
        self.controller.set_display_mapping(value, self._last_vmax)

    def _last_vmax(self, value: float) -> None:
        """Document the last_vmax flow."""
        self.controller.set_display_mapping(self._last_vmin, value)

    def play_mode(self, value: Optional[str]) -> None:
        """Document the play_mode flow."""
        if value is None:
            self.controller.stop_playback()
        else:
            self.controller.start_playback(value)

    def loop_playback(self, value: bool) -> None:
        """Document the loop_playback flow."""
        self.controller.set_loop(value)

    def profile_line(
        self, value: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> None:
        """Document the profile_line flow."""
        self.controller.set_profile_line(value)

    def profile_enabled(self, value: bool) -> None:
        """Document the profile_enabled flow."""
        self.controller.set_profile_enabled(value)

    def hist_enabled(self, value: bool) -> None:
        """Document the hist_enabled flow."""
        self.controller.set_hist_enabled(value)

    def hist_bins(self, value: int) -> None:
        """Document the hist_bins flow."""
        self.controller.set_hist_bins(value)

    def hist_region(self, value: str) -> None:
        """Document the hist_region flow."""
        self.controller.set_hist_region(value)

    def link_zoom(self, value: bool) -> None:
        """Document the link_zoom flow."""
        self.controller.set_link_zoom(value)

    def roi_shape(self, value: str) -> None:
        """Document the roi_shape flow."""
        self.controller.set_roi(self.roi_rect, shape=value)

    def roi_rect(self, value: Tuple[float, float, float, float]) -> None:
        """Document the roi_rect flow."""
        self.controller.set_roi(value, shape=self.roi_shape)

    def crop_rect(self, value: Optional[Tuple[float, float, float, float]]) -> None:
        """Document the crop_rect flow."""
        self.controller.set_crop(value)

    def annotate_target(self, value: str) -> None:
        """Document the annotate_target flow."""
        self.controller.set_annotate_target(value)

    def annotation_scope(self, value: str) -> None:
        """Document the annotation_scope flow."""
        self.controller.set_annotation_scope(value)

    def show_ann_frame(self, value: bool) -> None:
        """Document the show_ann_frame flow."""
        self.controller.set_show_annotations(value, self.show_ann_mean)

    def show_ann_mean(self, value: bool) -> None:
        """Document the show_ann_mean flow."""
        self.controller.set_show_annotations(self.show_ann_frame, value)

    def _annotations_dirty(self, value: bool) -> None:
        """Document the annotations_dirty flow."""
        self.controller.set_dirty(value)

    def _project_path(self, value: Optional[pathlib.Path]) -> None:
        """Document the project_path flow."""
        self.controller.set_project_path(value)

    def overlay_enabled(self, value: bool) -> None:
        """Document the overlay_enabled flow."""
        self.controller.set_overlay_enabled(value)

    def _last_folder(self, value: Optional[pathlib.Path]) -> None:
        """Document the last_folder flow."""
        self.controller.set_last_folder(value)

    def _project_save_time(self, value: Optional[float]) -> None:
        """Document the project_save_time flow."""
        self.controller.set_project_save_time(value)

    def primary_image(self) -> "LazyImage":
        """Document the primary_image flow."""
        return self.images[self.current_image_idx]

    def support_image(self) -> "LazyImage":
        """Document the support_image flow."""
        return self.images[self.support_image_idx]
