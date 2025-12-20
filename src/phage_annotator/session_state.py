"""Dataclasses describing session, view, and image state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class RoiSpec:
    """ROI specification in full-resolution coordinates.

    Parameters
    ----------
    rect : tuple[float, float, float, float]
        (x, y, width, height) in full-resolution pixel coordinates.
    shape : str
        ROI shape identifier ("box" or "circle").
    """

    rect: Tuple[float, float, float, float]
    shape: str = "circle"


class ViewState:
    """View-specific state for the active session.

    Notes
    -----
    Coordinates stored here are always in full-resolution image space.
    Crop only affects display; annotations remain in full-resolution coordinates.
    """

    t: int = 0
    z: int = 0
    crop_rect: Optional[Tuple[float, float, float, float]] = None
    roi_spec: RoiSpec = field(default_factory=lambda: RoiSpec((0.0, 0.0, 600.0, 600.0), "circle"))
    tool: str = "ANNOTATE_POINT"
    annotate_target: str = "mean"
    annotation_scope: str = "all"
    linked_zoom: bool = True
    overlay_enabled: bool = True
    show_ann_frame: bool = True
    show_ann_mean: bool = True
    show_ann_comp: bool = True
    profile_line: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
    profile_enabled: bool = True
    hist_enabled: bool = True
    hist_bins: int = 100
    hist_region: str = "roi"
    play_mode: Optional[str] = None
    loop_playback: bool = False


class ImageState:
    """Image metadata tracked by the session.

    Parameters
    ----------
    image_id : int
        Stable identifier for the image within the session.
    path : pathlib.Path
        Full filesystem path to the image.
    dims : tuple[int, int, int, int]
        (T, Z, Y, X) dimensions in standardized order.
    axis_mode : str
        Interpretation of the 3D axis when metadata is ambiguous.
    has_time, has_z : bool
        Flags describing whether time/z axes are present.
    pixel_size_um : float
        Pixel size in micrometers per pixel.
    memmap_flag : bool
        True when data is memory-mapped instead of fully loaded.
    metadata_summary : dict
        Cached metadata summary for the image.
    """

    image_id: int
    path: pathlib.Path
    dims: Tuple[int, int, int, int]
    axis_mode: str
    has_time: bool
    has_z: bool
    pixel_size_um: float
    memmap_flag: bool
    metadata_summary: dict = field(default_factory=dict)


class SessionState:
    """Project/session state that persists across views.

    Notes
    -----
    Image and annotation state is centralized here so the GUI avoids ad-hoc
    attributes. Annotation coordinates are stored in full-resolution space.
    """

    project_path: Optional[pathlib.Path]
    project_save_time: Optional[float]
    dirty: bool
    last_folder: Optional[pathlib.Path]
    recent_images: List[str]
    active_primary_id: int
    active_support_id: int
    smlm_runs: List[dict] = field(default_factory=list)
    threshold_settings: Dict[str, object] = field(default_factory=dict)
    threshold_masks: Dict[int, dict] = field(default_factory=dict)
    threshold_configs_by_image: Dict[int, Dict[str, object]] = field(default_factory=dict)
    particles_configs_by_image: Dict[int, Dict[str, object]] = field(default_factory=dict)
    annotation_imports: Dict[int, List[Dict[str, object]]] = field(default_factory=dict)
    annotation_index: Dict[int, List[AnnotationIndexEntry]] = field(default_factory=dict)
    annotations_loaded: Dict[int, bool] = field(default_factory=dict)
    images: List["LazyImage"]
    image_states: Dict[int, ImageState]
    annotations: Dict[int, List[Keypoint]]
    labels: List[str]
    current_label: str
    fps: int = 12
