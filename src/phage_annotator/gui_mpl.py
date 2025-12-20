"""Matplotlib + Qt keypoint annotation GUI for microscopy TIFF stacks.

This module hosts the main window, dock registry, and interactive tool routing.
It embeds Matplotlib canvases for image panels plus diagnostic plots, while
persisting UI state via QSettings and supporting background jobs for heavy work.

Architecture highlights:
- Lazy image loading with memmap for large TIFFs.
- Tool-based mouse routing (annotate/erase/ROI/profile/pan-zoom).
- Projection caching with LRU eviction and crop-aware keys.
- Autosave recovery (project-based) with recovery prompts.

All Qt interactions must run on the GUI thread; background work is routed via
JobManager signals to keep the UI responsive.
"""

from __future__ import annotations

import pathlib
import threading
from collections import deque
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.annotations import Keypoint
from phage_annotator.config import DEFAULT_CONFIG
from phage_annotator.gui_actions import ActionsMixin
from phage_annotator.gui_annotations import AnnotationsMixin
from phage_annotator.gui_constants import INTERACTIVE_DOWNSAMPLE, PLAYBACK_BUFFER_SIZE
from phage_annotator.gui_controls import ControlsMixin
from phage_annotator.gui_events import EventsMixin
from phage_annotator.gui_export import ExportMixin
from phage_annotator.gui_image_io import read_metadata
from phage_annotator.gui_jobs import JobsMixin
from phage_annotator.gui_playback import PlaybackMixin
from phage_annotator.gui_rendering import RenderingMixin
from phage_annotator.gui_roi_crop import RoiCropMixin
from phage_annotator.gui_state import StateMixin
from phage_annotator.gui_table_status import TableStatusMixin
from phage_annotator.gui_ui_extra import UiExtrasMixin
from phage_annotator.gui_ui_setup import UiSetupMixin
from phage_annotator.image_models import LazyImage
from phage_annotator.jobs import JobManager
from phage_annotator.lut_manager import lut_names
from phage_annotator.panels import PanelSpec
from phage_annotator.projection_cache import ProjectionCache
from phage_annotator.recorder import ActionRecorder
from phage_annotator.ring_buffer import BlockPrefetcher, FrameRingBuffer
from phage_annotator.roi_manager import RoiManager
from phage_annotator.session_controller import SessionController
from phage_annotator.tools import Tool


class KeypointAnnotator(
    QtWidgets.QMainWindow,
    UiSetupMixin,
    UiExtrasMixin,
    JobsMixin,
    EventsMixin,
    StateMixin,
    PlaybackMixin,
    RenderingMixin,
    RoiCropMixin,
    AnnotationsMixin,
    ActionsMixin,
    ControlsMixin,
    TableStatusMixin,
    ExportMixin,
):
    """Main GUI window for keypoint annotation on T/Z image stacks.

    The window owns all UI state and must be interacted with on the GUI thread.
    Arrays may be full in-memory numpy arrays or memory-mapped TIFFs for large
    stacks. Annotation coordinates are stored in full-resolution image space
    (crop and downsample only affect display).
    """

    def __init__(self, images: List[LazyImage], labels: Sequence[str] | None = None) -> None:
        super().__init__()
        if not images:
            raise ValueError("No images provided.")
        # QSettings keys: layout (customGeometry/customState), cacheMaxMB,
        # downsampleFactor, downsampleImages/Hist/Profile, autosaveRecoveryEnabled,
        # autoLoadAnnotations, applyAnnotationMetaOnLoad, encodeAnnotationMetaFilename,
        # keepRecentImages, recentImages, defaultLayoutPreset, defaultColormap, defaultFPS,
        # defaultPixelSizeUmPerPx, scaleBarEnabled, scaleBarLengthUm, scaleBarThicknessPx,
        # scaleBarLocation, scaleBarPaddingPx, scaleBarShowText, scaleBarTextOffsetPx,
        # scaleBarBackgroundBox, scaleBarIncludeInExport, densityModelPath, densityDevice,
        # densityConfig, densityInferOptions, densityTargetPanel,
        # prefetchBlockSizeFrames, prefetchMaxInflightBlocks, throttleAnalysisHzDuringPlayback,
        # pyramidEnabled, pyramidMaxLevels, showRoiHandles.
        self._settings = QtCore.QSettings("PhageAnnotator", "PhageAnnotator")
        # Marker size controls visual size only; click_radius_px controls selection tolerance.
        self.marker_size = 40
        self.click_radius_px = 6.0
        self.play_timer = QtCore.QTimer()
        self._last_zoom_linked: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self._axis_zoom: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = {}
        self._left_sizes: Optional[List[int]] = None
        self._block_table = False
        self._table_rows: List[Keypoint] = []

        self._suppress_limits = False

        # Playback helpers (high-FPS path)
        self._playback_mode = False
        self._playback_ring = FrameRingBuffer(PLAYBACK_BUFFER_SIZE)
        self._playback_stop_event = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_buffer_size = PLAYBACK_BUFFER_SIZE
        self._playback_direction = 1
        self._playback_overlay_stride = 3
        self._playback_frame_counter = 0
        self._fps_times: Deque[float] = deque(maxlen=120)
        self._fps_text = None
        self._playback_cursor = 0
        self._last_frame_time: Optional[float] = None
        self._playback_underruns = 0
        # Panel visibility controls which axes exist; at least one must remain visible.
        self._panel_visibility = {
            "frame": True,
            "mean": True,
            "composite": True,
            "support": True,
            "std": True,
        }
        # Skip the next zoom capture when layout is rebuilt to preserve previous zoom.
        self._skip_capture_once = False
        # Pixel size (um per pixel) for density calculations.
        self.pixel_size_um_per_px = float(
            self._settings.value("defaultPixelSizeUmPerPx", 0.069, type=float)
        )
        self._status_base = ""
        self._status_extra = ""
        self._default_geometry: Optional[QtCore.QByteArray] = None
        self._default_state: Optional[QtCore.QByteArray] = None
        self._preset_active = False
        self._interactive = False
        self._debounce_timer = QtCore.QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(80)
        self._debounce_timer.timeout.connect(self._refresh_image)
        self.downsample_factor = int(
            self._settings.value("downsampleFactor", INTERACTIVE_DOWNSAMPLE, type=int)
        )
        self.downsample_images = bool(self._settings.value("downsampleImages", True, type=bool))
        self.downsample_hist = bool(self._settings.value("downsampleHist", True, type=bool))
        self.downsample_profile = bool(self._settings.value("downsampleProfile", True, type=bool))
        self._job_generation = 0
        self._projection_jobs: Dict[
            Tuple[int, str, Tuple[float, float, float, float], int, int], str
        ] = {}
        cache_max_mb = self._settings.value("cacheMaxMB", 1024, type=int)
        self.proj_cache = ProjectionCache(max_mb=cache_max_mb)
        self._diag_hist_source = None
        self.jobs = JobManager(self)
        self._active_job_id: Optional[str] = None
        self._active_job_name: Optional[str] = None
        self.progress_label = None
        self.progress_bar = None
        self.progress_cancel_btn = None
        self.log_view = None
        self.cache_stats_label = None
        self.buffer_stats_label = None
        self._dev_demo_job_act = None

        # Matplotlib image artists reused across refreshes to avoid recreation.
        self.im_frame = None
        self.im_mean = None
        self.im_comp = None
        self.im_support = None
        self.im_std = None
        self.hist_fig = None
        self.hist_canvas = None
        self.profile_fig = None
        self.profile_canvas = None
        self.dock_hist = None
        self.dock_profile = None
        self.dock_orthoview = None
        self.dock_smlm = None
        self.dock_threshold = None
        self.dock_particles = None
        self.dock_annotations = None
        self.dock_roi = None
        self.dock_logs = None
        self.dock_metadata = None
        self.dock_density = None
        self.dock_sidebar = None
        self.sidebar_stack = None
        self.sidebar_actions = []
        self.command_palette_act = None
        self.reset_view_act = None
        self.tool_router = None
        self.tool_actions: Dict[Tool, QtWidgets.QAction] = {}
        self.tool_label = None
        self.overlay_text = None
        self.render_level_label = None
        self._render_scales: Dict[object, float] = {}
        self._pyramid_jobs: Dict[
            Tuple[int, str, int, int, Tuple[float, float, float, float], int], str
        ] = {}
        self._annotation_job_ids: Dict[int, str] = {}
        self._annotation_job_tokens: Dict[int, object] = {}
        self._pending_annotation_meta: Optional[dict] = None
        self._pending_annotation_meta_image_id: Optional[int] = None
        self.scale_bar_enabled = bool(self._settings.value("scaleBarEnabled", False, type=bool))
        self.scale_bar_length_um = float(self._settings.value("scaleBarLengthUm", 5.0, type=float))
        self.scale_bar_thickness_px = int(self._settings.value("scaleBarThicknessPx", 4, type=int))
        self.scale_bar_location = self._settings.value("scaleBarLocation", "bottom_right", type=str)
        self.scale_bar_padding_px = int(self._settings.value("scaleBarPaddingPx", 12, type=int))
        self.scale_bar_show_text = bool(self._settings.value("scaleBarShowText", True, type=bool))
        self.scale_bar_text_offset_px = int(
            self._settings.value("scaleBarTextOffsetPx", 6, type=int)
        )
        self.scale_bar_background_box = bool(
            self._settings.value("scaleBarBackgroundBox", True, type=bool)
        )
        self.scale_bar_include_in_export = bool(
            self._settings.value("scaleBarIncludeInExport", True, type=bool)
        )
        self.show_roi_handles = bool(self._settings.value("showRoiHandles", True, type=bool))
        self._density_job_id: Optional[str] = None
        self._density_overlay = None
        self._density_overlay_extent = None
        self._density_overlay_alpha = 0.6
        self._density_overlay_cmap = "magma"
        self._density_contours = False
        self._density_last_result = None
        self._density_last_panel = "frame"
        self.panel_specs: List[PanelSpec] = []
        self.panel_docks: Dict[str, QtWidgets.QDockWidget] = {}
        self.dock_actions: Dict[str, QtWidgets.QAction] = {}
        self.orthoview_widget = None
        self.smlm_panel = None
        self.threshold_panel = None
        self.particles_panel = None
        self.metadata_widget = None
        self.density_panel = None
        self._roi_controls_layout = None
        
        # ==================== ARCHITECTURAL DEBT: Widget Initialization Ordering ====================
        # ISSUE: GUI fails during initialization due to widget initialization ordering dependencies.
        # - Some widgets are created in _setup_status_bar() (status bar widgets, progress, labels)
        # - Other widgets are created in _init_panels() -> make_*_widget() factories (hist_chk, profile_chk)
        # - These factories reference self.status which may not exist yet if _init_panels() runs before _setup_status_bar()
        # 
        # ROOT CAUSE: The mixin-based architecture lacks explicit state dependency ordering.
        # Each mixin method assumes certain attributes exist, but there's no enforced initialization sequence.
        # 
        # MITIGATION (Current): Pre-initialize all widget stubs to None here. This prevents AttributeError
        # but masks the real architectural problem: scattered, implicit self.* attributes with no clear ownership.
        # 
        # SOLUTION (Phase 2D): Refactor into explicit state dataclasses:
        #   1. Create RenderContext(status, progress_label, progress_bar, progress_cancel_btn)
        #   2. Create ViewState(vmin, vmax, contrast_params, zoom_state, downsample_factor)
        #   3. Create OverlayState(tool, annotations, roi, density_overlay)
        # Then pass these explicitly to methods instead of relying on self.* lookups.
        # This will eliminate 400+ implicit self.* references and make initialization order irrelevant.
        # 
        # TEST IMPACT: GUI tests currently skip until Phase 2D completes (see test_gui_basic.py).
        # Once state dataclasses are in place, tests will pass because factories will receive
        # explicit RenderContext/ViewState objects rather than searching for self.status/self.hist_chk.
        # 
        # Pre-initialize GUI widget stubs (will be properly set during _setup_ui)
        self.status = None  # Created in _setup_status_bar() but used in make_logs_widget()
        self.hist_chk = None  # Created in make_hist_widget() but checked in init_panels()
        self.profile_chk = None  # Created in make_profile_widget() but checked in init_panels()
        self.show_hist_chk = None  # Alias for hist_chk
        self.show_profile_chk = None  # Alias for profile_chk
        self.hist_canvas = None  # Created in make_hist_widget()
        self.profile_canvas = None  # Created in make_profile_widget()
        self.hist_fig = None  # Matplotlib figure for histogram
        self.profile_fig = None  # Matplotlib figure for profile (line plot)
        self.ax_hist = None  # Matplotlib axes for histogram
        self.ax_line = None  # Matplotlib axes for profile line plot
        self.log_view = None  # QPlainTextEdit for debug logs
        self.cache_stats_label = None  # Status label for cache statistics
        self.profile_mode_chk = None  # Checkbox for profile mode (created in annotation controls)
        # ==============================================================================================
        self.controller = SessionController(
            self,
            images,
            labels or DEFAULT_CONFIG.default_labels,
            self._settings,
            proj_cache=self.proj_cache,
            ring_buffer=self._playback_ring,
            colormaps=lut_names(),
        )
        self.colormaps = lut_names()
        self._autosave_timer = QtCore.QTimer()
        self._autosave_timer.setInterval(120000)
        self._autosave_timer.timeout.connect(self._autosave_tick)
        self._analysis_last_submit = 0.0
        self._analysis_submit_pending = False
        self._contrast_drag_active = False
        self._auto_job_id: Optional[str] = None
        self._norm_cache: Dict[Tuple[str, float, float, float, str], object] = {}
        self._hist_job_id: Optional[str] = None
        self._cursor_xy: Optional[Tuple[float, float]] = None
        self._smlm_results = []
        self._smlm_overlay = None
        self._smlm_overlay_extent = None
        self._smlm_job_id: Optional[str] = None
        self._smlm_run_id = 0
        self._deepstorm_results = []
        self._deepstorm_overlay = None
        self._deepstorm_overlay_extent = None
        self._deepstorm_job_id: Optional[str] = None
        self._deepstorm_run_id = 0
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._smlm_run_history: List[dict] = []
        self._last_smlm_run: Optional[dict] = None
        self.show_smlm_points = True
        self.show_sr_overlay = True
        self._threshold_preview_mask = None
        self._threshold_preview_extent = None
        self._threshold_mask_full = None
        self._threshold_job_id: Optional[str] = None
        self._threshold_auto_value: Optional[float] = None
        self._threshold_settings: Dict[str, object] = {}
        self._threshold_timer = QtCore.QTimer()
        self._threshold_timer.setSingleShot(True)
        self._threshold_timer.setInterval(80)
        self._threshold_timer.timeout.connect(self._threshold_refresh_preview)
        self._binary_view_mask = None
        self._binary_view_enabled = False
        self._particles_results: List[object] = []
        self._particles_overlays: List[tuple] = []
        self._particles_selected: Optional[int] = None
        self._particles_job_id: Optional[str] = None
        self._auto_roi_job_id: Optional[str] = None
        self._hist_cache = None
        self._hist_cache_key = None
        self._hist_last_time = 0.0
        self._hist_scope_mode = "Current slice"
        self.roi_manager = RoiManager()
        self.roi_manager_widget = None
        self.results_widget = None
        self.recorder = ActionRecorder()
        self.recorder_widget = None
        self._action_map: Dict[str, QtWidgets.QAction] = {}
        self.pyramid_enabled = bool(self._settings.value("pyramidEnabled", False, type=bool))
        self.pyramid_max_levels = int(self._settings.value("pyramidMaxLevels", 3, type=int))
        self._last_render_level = 0
        self._prefetcher = BlockPrefetcher(
            self._read_playback_block,
            self._playback_ring,
            block_size=int(self._settings.value("prefetchBlockSizeFrames", 64, type=int)),
            max_inflight_blocks=int(self._settings.value("prefetchMaxInflightBlocks", 2, type=int)),
            stop_event=self._playback_stop_event,
        )

        self._setup_ui()
        if hasattr(self, "show_smlm_points_act"):
            self.show_smlm_points = self.show_smlm_points_act.isChecked()
        if hasattr(self, "show_smlm_sr_act"):
            self.show_sr_overlay = self.show_smlm_sr_act.isChecked()
        if self.orthoview_widget is not None:
            self.orthoview_widget.set_callbacks(
                self._on_orthoview_xz_click, self._on_orthoview_yz_click
            )
        self._attach_recorder()
        self._install_exception_hook()
        self._setup_tool_router()
        self._bind_events()
        self._bind_job_signals()
        self._ensure_loaded(self.current_image_idx)
        self._ensure_loaded(self.support_image_idx)
        self._reset_crop(initial=True)
        self._reset_roi()
        self._refresh_image()
        self._autosave_timer.start()


def create_app(image_paths: List[pathlib.Path]) -> "KeypointAnnotator":
    """Create the Qt application and main window without starting the event loop."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        QtWidgets.QApplication([])
    images = [
        img for img in (read_metadata(pathlib.Path(p)) for p in image_paths) if img is not None
    ]
    return KeypointAnnotator(images)


def run_gui(image_paths: List[pathlib.Path]) -> None:
    images = [img for img in (read_metadata(p) for p in image_paths) if img is not None]
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = KeypointAnnotator(images)
    window.show()
    app.exec()
