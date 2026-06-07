"""Canvas context dataclass: render inputs for image panels and overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
import numpy as np

from phage_annotator.core.session_state import ViewState


@dataclass(frozen=True)
class RenderContext:
    """Render inputs for image panels and overlays.

    Parameters
    ----------
    image_frame : np.ndarray
        Primary image frame (2D array) in display resolution.
    support_frame : np.ndarray or None
        Support image frame (2D array) in display resolution.
    projections : dict[str, np.ndarray]
        Precomputed projections keyed by name ("mean", "std").
    view : ViewState
        View state (T/Z, crop/ROI, overlay toggle).
    annotations : Sequence[object]
        Filtered annotations for the current view scope.
    panel_visibility : dict[str, bool]
        Panel visibility map keyed by panel id.
    titles : dict[str, str]
        Panel titles keyed by panel id.
    extents : dict[str, tuple[float, float, float, float]]
        Axis extents per panel in display coordinates.
    std_range : tuple[float, float]
        vmin/vmax for the std panel.
    norms : dict[str, matplotlib.colors.Normalize]
        Per-panel normalization objects derived from display mappings.
    panel_cmaps : dict[str, matplotlib.colors.Colormap]
        Per-panel colormaps.
    panel_ranges : dict[str, tuple[float, float]]
        Per-panel vmin/vmax ranges used as a fallback.
    panel_annotations : dict[str, list[tuple[float, float, str, bool, bool]]]
        Per-panel display coordinates for annotations:
        (x, y, color, selected).
    suggestion_staleness_labels : dict[str, list[tuple[float, float, str]]]
        Per-panel suggestion age labels as (x, y, text).
    roi_overlays : dict[str, list[tuple[str, object, str]]]
        Per-panel ROI overlays: (shape, data, color).
    overlay_text : str or None
        Overlay text to display in the active panel.
    canvas_header_text : str or None
        Always-visible non-interactive header text rendered above the frame panel.
    marker_size : float
        Marker size for scatter annotations.
    marker_shape : str
        Matplotlib marker code for annotation points.
    localization_points : list[tuple[float, float, float]]
        Optional localization overlays as (x, y, value).
    localization_visible : bool
        Whether to render localization overlays.
    threshold_mask : np.ndarray or None
        Optional threshold mask overlay in display coordinates.
    threshold_extent : tuple[float, float, float, float] or None
        Extent for the threshold overlay.
    threshold_visible : bool
        Whether to render the threshold overlay.
    particle_overlays : list[tuple[str, object, str, bool]]
        Particle overlays as (shape, data, color, selected).
    particle_labels : list[tuple[float, float, str]]
        Label overlays as (x, y, text).
    overlay_frame : np.ndarray or None
        Optional overlay image for the main frame panel.
    overlay_extent : tuple[float, float, float, float] or None
        Extent for the overlay image in display coordinates.
    overlay_alpha : float
        Alpha to apply to the overlay image.
    overlay_norm : matplotlib.colors.Normalize or None
        Optional normalization for the overlay.
    overlay_cmap : matplotlib.colors.Colormap or None
        Optional colormap for the overlay.
    scale_bar : dict or None
        Scale bar geometry and text settings for the frame panel.
    scale_bar_warning : str or None
        Warning text when calibration is missing.
    density_contours : bool
        Whether to draw density contours for the overlay layer.
    roi_scale : float
        Display-to-full coordinate scale for ROI interaction.
    roi_offset : tuple[float, float]
        Display-to-full coordinate offset for ROI interaction.
    roi_show_handles : bool
        Whether to show ROI handles on the frame axis.
    roi_type : str
        ROI type ("box", "circle", "none").
    roi_rect : tuple[float, float, float, float] or None
        ROI rectangle in full-image coordinates.
    """

    image_frame: np.ndarray
    support_frame: Optional[np.ndarray]
    projections: Dict[str, np.ndarray]
    panel_images: Dict[str, np.ndarray]
    primary_panel: str
    view: ViewState
    annotations: Sequence[object]
    panel_visibility: Dict[str, bool]
    titles: Dict[str, str]
    extents: Dict[str, Tuple[float, float, float, float]]
    std_range: Tuple[float, float]
    panel_annotations: Dict[str, List[Tuple[float, float, str, bool, bool]]]
    suggestion_staleness_labels: Dict[str, List[Tuple[float, float, str]]]
    roi_overlays: Dict[str, List[Tuple[str, object, str]]]
    overlay_text: Optional[str]
    canvas_header_text: Optional[str]
    marker_size: float
    marker_shape: str
    norms: Dict[str, matplotlib.colors.Normalize]
    panel_cmaps: Dict[str, matplotlib.colors.Colormap]
    panel_ranges: Dict[str, Tuple[float, float]]
    localization_points: List[Tuple[float, float, float]]
    localization_visible: bool
    threshold_mask: Optional[np.ndarray]
    threshold_extent: Optional[Tuple[float, float, float, float]]
    threshold_visible: bool
    particle_overlays: List[Tuple[str, object, str, bool]]
    particle_labels: List[Tuple[float, float, str]]
    overlay_frame: Optional[np.ndarray]
    overlay_extent: Optional[Tuple[float, float, float, float]]
    overlay_alpha: float
    overlay_norm: Optional[matplotlib.colors.Normalize]
    overlay_cmap: Optional[matplotlib.colors.Colormap]
    density_contours: bool
    scale_bar: Optional[Dict[str, object]]
    scale_bar_warning: Optional[str]
    roi_scale: float
    roi_offset: Tuple[float, float]
    roi_show_handles: bool
    roi_type: str
    roi_rect: Optional[Tuple[float, float, float, float]]
