"""Extracted method group 1 for StateMixin."""

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



class PlaybackControlsMixin:
    """Method group 1 extracted from StateMixin."""

    @property
    def images(self) -> List["LazyImage"]:
        """Run the images workflow."""
        return list(self.controller.session_state.images)
    @images.setter
    def images(self, value: List["LazyImage"]) -> None:
        """Run the images workflow."""
        self.controller.set_images(value)
    @property
    def labels(self) -> List[str]:
        """Run the labels workflow."""
        return list(self.controller.session_state.labels)
    @property
    def current_label(self) -> str:
        """Run the current label workflow."""
        return self.controller.session_state.current_label
    @current_label.setter
    def current_label(self, label: str) -> None:
        """Run the current label workflow."""
        self.controller.set_current_label(label)
    @property
    def annotations(self) -> Dict[int, List[Keypoint]]:
        """Run the annotations workflow."""
        return MappingProxyType(
            {int(k): tuple(v) for k, v in self.controller.session_state.annotations.items()}
        )
    @property
    def suggestions(self) -> Dict[int, List[PointSuggestion]]:
        """Run the suggestions workflow."""
        return MappingProxyType(
            {int(k): tuple(v) for k, v in self.controller.session_state.suggestions.items()}
        )
    @property
    def axis_mode(self) -> Dict[int, str]:
        """Run the axis mode workflow."""
        return {k: v.axis_mode for k, v in self.controller.session_state.image_states.items()}
    @property
    def current_image_idx(self) -> int:
        """Run the current image idx workflow."""
        return self.controller.session_state.active_primary_id
    @current_image_idx.setter
    def current_image_idx(self, value: int) -> None:
        """Run the current image idx workflow."""
        self.controller.set_primary(value)
    @property
    def support_image_idx(self) -> int:
        """Run the support image idx workflow."""
        return self.controller.session_state.active_support_id
    @support_image_idx.setter
    def support_image_idx(self, value: int) -> None:
        """Run the support image idx workflow."""
        self.controller.set_support(value)
    @property
    def primary_image(self) -> "LazyImage":
        """Run the primary image workflow."""
        return self.images[self.current_image_idx]
    @property
    def support_image(self) -> "LazyImage":
        """Run the support image workflow."""
        return self.images[self.support_image_idx]
    @property
    def current_cmap_idx(self) -> int:
        """Run the current cmap idx workflow."""
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        return mapping.lut
    @current_cmap_idx.setter
    def current_cmap_idx(self, value: int) -> None:
        """Run the current cmap idx workflow."""
        self.controller.set_lut(value)
    @property
    def _last_vmin(self) -> float:
        """Handle the last vmin helper flow."""
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        return mapping.min_val
    @_last_vmin.setter
    def _last_vmin(self, value: float) -> None:
        """Handle the last vmin helper flow."""
        self.controller.set_display_mapping(value, self._last_vmax)
    @property
    def _last_vmax(self) -> float:
        """Handle the last vmax helper flow."""
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        return mapping.max_val
    @_last_vmax.setter
    def _last_vmax(self, value: float) -> None:
        """Handle the last vmax helper flow."""
        self.controller.set_display_mapping(self._last_vmin, value)
    @property
    def play_mode(self) -> Optional[str]:
        """Run the play mode workflow."""
        return self.controller.view_state.play_mode
    @play_mode.setter
    def play_mode(self, value: Optional[str]) -> None:
        """Run the play mode workflow."""
        if value is None:
            self.controller.stop_playback()
        else:
            self.controller.start_playback(value)
    @property
    def loop_playback(self) -> bool:
        """Run the loop playback workflow."""
        return self.controller.view_state.loop_playback
    @loop_playback.setter
    def loop_playback(self, value: bool) -> None:
        """Run the loop playback workflow."""
        self.controller.set_loop(value)
    @property
    def profile_line(self) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Run the profile line workflow."""
        return self.controller.view_state.profile_line
    @profile_line.setter
    def profile_line(
        self, value: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> None:
        """Run the profile line workflow."""
        self.controller.set_profile_line(value)
    @property
    def profile_enabled(self) -> bool:
        """Run the profile enabled workflow."""
        return self.controller.view_state.profile_enabled
    @profile_enabled.setter
    def profile_enabled(self, value: bool) -> None:
        """Run the profile enabled workflow."""
        self.controller.set_profile_enabled(value)
    @property
    def hist_enabled(self) -> bool:
        """Run the hist enabled workflow."""
        return self.controller.view_state.hist_enabled
    @hist_enabled.setter
    def hist_enabled(self, value: bool) -> None:
        """Run the hist enabled workflow."""
        self.controller.set_hist_enabled(value)
    @property
    def hist_bins(self) -> int:
        """Run the hist bins workflow."""
        return self.controller.view_state.hist_bins
    @hist_bins.setter
    def hist_bins(self, value: int) -> None:
        """Run the hist bins workflow."""
        self.controller.set_hist_bins(value)
    @property
    def hist_region(self) -> str:
        """Run the hist region workflow."""
        return self.controller.view_state.hist_region
    @hist_region.setter
    def hist_region(self, value: str) -> None:
        """Run the hist region workflow."""
        self.controller.set_hist_region(value)
    @property
    def link_zoom(self) -> bool:
        """Run the link zoom workflow."""
        return self.controller.view_state.linked_zoom
    @link_zoom.setter
    def link_zoom(self, value: bool) -> None:
        """Run the link zoom workflow."""
        self.controller.set_link_zoom(value)
    @property
    def roi_shape(self) -> str:
        """Return the roi shape value."""
        return self.controller.view_state.roi_spec.shape
    @roi_shape.setter
    def roi_shape(self, value: str) -> None:
        """Return the roi shape value."""
        self.controller.set_roi(self.roi_rect, shape=value)
    @property
    def roi_rect(self) -> Tuple[float, float, float, float]:
        """Return the roi rect value."""
        return self.controller.view_state.roi_spec.rect
    @roi_rect.setter
    def roi_rect(self, value: Tuple[float, float, float, float]) -> None:
        """Return the roi rect value."""
        self.controller.set_roi(value, shape=self.roi_shape)
    @property
    def crop_rect(self) -> Optional[Tuple[float, float, float, float]]:
        """Run the crop rect workflow."""
        return self.controller.view_state.crop_rect
    @crop_rect.setter
    def crop_rect(self, value: Optional[Tuple[float, float, float, float]]) -> None:
        """Run the crop rect workflow."""
        self.controller.set_crop(value)
    @property
    def annotate_target(self) -> str:
        """Run the annotate target workflow."""
        return self.controller.view_state.annotate_target
    @annotate_target.setter
    def annotate_target(self, value: str) -> None:
        """Run the annotate target workflow."""
        self.controller.set_annotate_target(value)
    @property
    def annotation_scope(self) -> str:
        """Run the annotation scope workflow."""
        return self.controller.view_state.annotation_scope
    @annotation_scope.setter
    def annotation_scope(self, value: str) -> None:
        """Run the annotation scope workflow."""
        self.controller.set_annotation_scope(value)
    @property
    def show_ann_frame(self) -> bool:
        """Show ann frame for the current workflow."""
        return self.controller.view_state.show_ann_frame
    @show_ann_frame.setter
    def show_ann_frame(self, value: bool) -> None:
        """Show ann frame for the current workflow."""
        self.controller.set_show_annotations(value, self.show_ann_mean)
    @property
    def show_ann_mean(self) -> bool:
        """Show ann mean for the current workflow."""
        return self.controller.view_state.show_ann_mean
    @show_ann_mean.setter
    def show_ann_mean(self, value: bool) -> None:
        """Show ann mean for the current workflow."""
        self.controller.set_show_annotations(self.show_ann_frame, value)
    @property
    def _annotations_dirty(self) -> bool:
        """Handle the annotations dirty helper flow."""
        return self.controller.session_state.dirty
    @_annotations_dirty.setter
    def _annotations_dirty(self, value: bool) -> None:
        """Handle the annotations dirty helper flow."""
        self.controller.set_dirty(value)
    @property
    def _project_path(self) -> Optional[pathlib.Path]:
        """Handle the project path helper flow."""
        return self.controller.session_state.project_path
    @_project_path.setter
    def _project_path(self, value: Optional[pathlib.Path]) -> None:
        """Handle the project path helper flow."""
        self.controller.set_project_path(value)
    @property
    def _last_folder(self) -> Optional[pathlib.Path]:
        """Handle the last folder helper flow."""
        return self.controller.session_state.last_folder
    @_last_folder.setter
    def _last_folder(self, value: Optional[pathlib.Path]) -> None:
        """Handle the last folder helper flow."""
        self.controller.set_last_folder(value)
    @property
    def _project_save_time(self) -> Optional[float]:
        """Handle the project save time helper flow."""
        return self.controller.session_state.project_save_time
    @property
    def overlay_enabled(self) -> bool:
        """Run the overlay enabled workflow."""
        return self.controller.view_state.overlay_enabled
    @overlay_enabled.setter
    def overlay_enabled(self, value: bool) -> None:
        """Run the overlay enabled workflow."""
        self.controller.set_overlay_enabled(value)
