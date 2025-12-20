"""View and display state mutations for the session controller."""

from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING
from phage_annotator.session_state import RoiSpec

if TYPE_CHECKING:
    from phage_annotator.display_mapping import DisplayMapping


class SessionViewMixin:
    """Mixin for view and display state mutations."""
    def set_current_label(self, label: str) -> None:
        """Set the active label for new annotations."""
        if self.session_state.current_label == label:
            return
        self.session_state.current_label = label
        self.state_changed.emit()

    def set_t(self, t_index: int) -> None:
        """Update the active T index."""
        if self.view_state.t == t_index:
            return
        self.view_state.t = t_index
        self.view_changed.emit()

    def set_z(self, z_index: int) -> None:
        """Update the active Z index."""
        if self.view_state.z == z_index:
            return
        self.view_state.z = z_index
        self.view_changed.emit()

    def set_roi(self, rect: Tuple[float, float, float, float], shape: Optional[str] = None) -> None:
        """Update the ROI rectangle/shape."""
        shape_val = shape if shape is not None else self.view_state.roi_spec.shape
        self.view_state.roi_spec = RoiSpec(rect=rect, shape=shape_val)
        self.view_changed.emit()
        self.roi_changed.emit()

    def set_roi_box(self, x: float, y: float, w: float, h: float) -> None:
        """Set a rectangular ROI in full-resolution coordinates."""
        self.set_roi((x, y, w, h), shape="box")

    def set_roi_circle(self, cx: float, cy: float, r: float) -> None:
        """Set a circular ROI in full-resolution coordinates."""
        rect = (cx - r, cy - r, r * 2, r * 2)
        self.set_roi(rect, shape="circle")

    def clear_roi(self) -> None:
        """Clear the active ROI."""
        self.view_state.roi_spec = RoiSpec(rect=(0.0, 0.0, 0.0, 0.0), shape="none")
        self.view_changed.emit()
        self.roi_changed.emit()

    def set_crop(self, rect: Optional[Tuple[float, float, float, float]]) -> None:
        """Update the crop rectangle."""
        self.view_state.crop_rect = rect
        self.view_changed.emit()

    def set_display_mapping(self, vmin: float, vmax: float, gamma: Optional[float] = None) -> None:
        """Update display mapping parameters."""
        mapping = self.display_mapping.mapping_for(self.session_state.active_primary_id, "frame")
        mapping.set_window(float(vmin), float(vmax))
        if gamma is not None:
            mapping.gamma = float(gamma)
            self.display_changed.emit()

    def set_lut(self, index: int) -> None:
        """Set the active LUT index."""
        mapping = self.display_mapping.mapping_for(self.session_state.active_primary_id, "frame")
        if mapping.lut == index:
            return
        mapping.lut = index
        self.display_changed.emit()

    def set_invert(self, invert: bool) -> None:
        """Toggle LUT inversion."""
        mapping = self.display_mapping.mapping_for(self.session_state.active_primary_id, "frame")
        if mapping.invert == invert:
            return
        mapping.invert = bool(invert)
        self.display_changed.emit()

    def set_gamma(self, gamma: float) -> None:
        """Set display gamma."""
        mapping = self.display_mapping.mapping_for(self.session_state.active_primary_id, "frame")
        if mapping.gamma == gamma:
            return
        mapping.gamma = float(gamma)
        self.display_changed.emit()

    def set_display_for_image(self, image_id: int, panel: str, mapping: DisplayMapping) -> None:
        """Store a display mapping override for an image/panel."""
        per_image = self.display_mapping.per_image.setdefault(image_id, {})
        per_image[panel] = mapping
        self.display_changed.emit()

    def set_profile_line(self, line: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]) -> None:
        """Update the active profile line."""
        self.view_state.profile_line = line
        self.view_changed.emit()

    def set_profile_enabled(self, enabled: bool) -> None:
        """Enable/disable line profile rendering."""
        if self.view_state.profile_enabled == enabled:
            return
        self.view_state.profile_enabled = enabled
        self.view_changed.emit()

    def set_hist_enabled(self, enabled: bool) -> None:
        """Enable/disable histogram rendering."""
        if self.view_state.hist_enabled == enabled:
            return
        self.view_state.hist_enabled = enabled
        self.view_changed.emit()

    def set_hist_bins(self, bins: int) -> None:
        """Set histogram bins."""
        if self.view_state.hist_bins == bins:
            return
        self.view_state.hist_bins = int(bins)
        self.view_changed.emit()

    def set_hist_region(self, region: str) -> None:
        """Set histogram region selection."""
        if self.view_state.hist_region == region:
            return
        self.view_state.hist_region = region
        self.view_changed.emit()

    def set_link_zoom(self, enabled: bool) -> None:
        """Enable/disable linked zoom."""
        if self.view_state.linked_zoom == enabled:
            return
        self.view_state.linked_zoom = enabled
        self.view_changed.emit()

    def set_annotation_scope(self, scope: str) -> None:
        """Set annotation scope (current/all)."""
        if self.view_state.annotation_scope == scope:
            return
        self.view_state.annotation_scope = scope
        self.view_changed.emit()

    def set_annotate_target(self, target: str) -> None:
        """Set annotation target panel."""
        if self.view_state.annotate_target == target:
            return
        self.view_state.annotate_target = target
        self.view_changed.emit()

    def set_tool(self, tool: str) -> None:
        """Set the active tool identifier."""
        if self.view_state.tool == tool:
            return
        self.view_state.tool = tool
        self.view_changed.emit()

    def set_overlay_enabled(self, enabled: bool) -> None:
        """Enable/disable the overlay text."""
        if self.view_state.overlay_enabled == enabled:
            return
        self.view_state.overlay_enabled = enabled
        self.view_changed.emit()

    def set_show_annotations(self, frame: bool, mean: bool, comp: bool) -> None:
        """Update which panels show annotations."""
        self.view_state.show_ann_frame = frame
        self.view_state.show_ann_mean = mean
        self.view_state.show_ann_comp = comp
        self.view_changed.emit()
