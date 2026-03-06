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

from phage_annotator.annotation.core import Keypoint
from phage_annotator.config.settings import DEFAULT_CONFIG
from phage_annotator.ui_qt.actions.standard import ActionsMixin
from phage_annotator.ui_qt.utils.annotations import AnnotationsMixin
from phage_annotator.ui_qt.utils.constants import INTERACTIVE_DOWNSAMPLE, PLAYBACK_BUFFER_SIZE
from phage_annotator.ui_qt.controls.base import ControlsMixin
from phage_annotator.ui_qt.actions.events import EventsMixin
from phage_annotator.ui_qt.utils.export import ExportMixin
from phage_annotator.ui_qt.actions.file import FileActionsMixin
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.utils.jobs import JobsMixin
from phage_annotator.ui_qt.utils.playback import PlaybackMixin
from phage_annotator.ui_qt.rendering.renderer import RenderingMixin
from phage_annotator.ui_qt.rendering.roi_crop import RoiCropMixin
from phage_annotator.ui_qt.utils.state import StateMixin
from phage_annotator.ui_qt.utils.table_status import TableStatusMixin
from phage_annotator.ui_qt.utils.ui_extra import UiExtrasMixin
from phage_annotator.ui_qt.utils.ui_setup import UiSetupMixin
from phage_annotator.ui_qt.utils.modality_helpers import ModalityHelpersMixin
from phage_annotator.ui_qt.handlers.keyboard_handlers import KeyboardHandlersMixin
from phage_annotator.ui_qt.utils.context_menu import ContextMenuMixin
from phage_annotator.data.models import LazyImage
from phage_annotator.ui_qt.services.jobs import JobManager
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.cache.projection_cache import ProjectionCache
from phage_annotator.data.ring_buffer import BlockPrefetcher, FrameRingBuffer
from phage_annotator.ui_qt.panels.recorder_legacy import ActionRecorder
from phage_annotator.ui_qt.panels.registry_legacy import PanelSpec
from phage_annotator.roi.manager import RoiManager
from phage_annotator.session.controller import SessionController
from phage_annotator.session.modality_facade import ModalityFacade
from phage_annotator.session.multi_playback import ModalityPlaybackManager, PlaybackMode
from phage_annotator.session.view_sync import ViewSyncManager
from phage_annotator.tools import Tool
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.ui_qt.services.settings_proxy import UnifiedSettingsProxy
from phage_annotator.ui_qt.services.settings_schema import (
    apply_settings_migrations,
    ensure_ui_settings_defaults,
)


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
    ContextMenuMixin,
    ActionsMixin,
    FileActionsMixin,
    ControlsMixin,
    TableStatusMixin,
    ExportMixin,
    ModalityHelpersMixin,
    KeyboardHandlersMixin,
):
    """Main GUI window for keypoint annotation on T/Z image stacks.

    The window owns all UI state and must be interacted with on the GUI thread.
    Arrays may be full in-memory numpy arrays or memory-mapped TIFFs for large
    stacks. Annotation coordinates are stored in full-resolution image space
    (crop and downsample only affect display).
    """
    def _get_setting(self, key: str, default, type_):
        """Get a setting via unified settings proxy."""
        return self._settings.value(key, default, type=type_)

    def __init__(self, images: List[LazyImage], labels: Sequence[str] | None = None) -> None:
        super().__init__()
        
        # Ensure window doesn't block other applications
        # Remove any modal or always-on-top flags that might interfere with other windows
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
        
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
        # pyramidEnabled, pyramidMaxLevels, showRoiHandles, markerSize, clickRadiusPx, activeTool.
        qsettings = QtCore.QSettings("PhageAnnotator", "PhageAnnotator")
        
        # Optional settings service integration.
        try:
            from phage_annotator.framework import get_settings_service
            from phage_annotator.constants.settings import (
                MARKER_SIZE, MARKER_SIZE_DEFAULT,
                CLICK_RADIUS_PX, CLICK_RADIUS_PX_DEFAULT,
            )
            self._settings_service = get_settings_service()
        except (ImportError, RuntimeError, AttributeError):
            self._settings_service = None
        
        self._settings = UnifiedSettingsProxy(qsettings, self._settings_service)
        apply_settings_migrations(self._settings)
        ensure_ui_settings_defaults(self._settings)

        # Marker size controls visual size only; click_radius_px controls selection tolerance.
        self.marker_size = self._get_setting("markerSize", 40, int)
        self.click_radius_px = self._get_setting("clickRadiusPx", 6.0, float)
        self.play_timer = QtCore.QTimer()
        self._last_zoom_linked: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self._axis_zoom: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = {}
        self._left_sizes: Optional[List[int]] = None
        self._block_table = False
        self._table_rows: List[Keypoint] = []
        self._selected_annotation_ids: set[str] = set()

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
            "modality_0": False,
            "modality_1": False,
        }
        # Lazy loading modality sync groups: maps modality indices/panel keys to group numbers (default to 1)
        self._lazy_modality_groups = {
            0: "1",           # frame -> group 1
            1: "1",           # support -> group 1
            "builtin:support": "1",
            "builtin:mean": "1",
            "builtin:std": "1",
        }
        # Lazy loading sync modes: maps modality indices/panel keys to sync mode flags
        self._lazy_sync_modes = {
            0: {"contrast": True, "zoom": True, "playback": True},
            1: {"contrast": True, "zoom": True, "playback": True},
            "builtin:support": {"contrast": True, "zoom": True, "playback": True},
            "builtin:mean": {"contrast": True, "zoom": True, "playback": True},
            "builtin:std": {"contrast": True, "zoom": True, "playback": True},
        }
        # Per-sync-group ROI memory. Group key -> {"shape": str, "rect": (x,y,w,h)} or None.
        self._roi_by_sync_group = {}
        # Lazy builtin views configuration (mean and std projections)
        self._lazy_builtin_views = {}
        self._lazy_builtin_seeded = False
        self._lazy_builtin_migrated = False
        self._lazy_hidden_base_panel_keys = {"modality_0", "modality_1"}
        self._lazy_panel_order: Dict[str, int] = {}
        self._canvas_layout_rows = int(self._settings.value("canvasLayoutRows", 0, type=int))
        self._canvas_layout_cols = int(self._settings.value("canvasLayoutCols", 0, type=int))
        # Skip the next zoom capture when layout is rebuilt to preserve previous zoom.
        self._skip_capture_once = False
        # Pixel size (um per pixel) for density calculations.
        self.pixel_size_um_per_px = float(
            self._get_setting("defaultPixelSizeUmPerPx", 0.069, float)
        )
        # Memory pressure state for prefetch/tile adaptation.
        self._prefetch_disabled = False
        self._adaptive_tile_size = 256
        self._lod_mode_active: Dict[int, bool] = {}
        self._panel_modality_map: Dict[str, object] = {}
        self._annotation_panel_visibility: Dict[str, bool] = {}
        self._status_base = ""
        self._status_extra = ""
        self._annotation_write_context_pending = False
        self._annotation_context_change_reason = ""
        self._annotation_write_context_pending_value = None
        self._annotation_write_context_confirmed = None
        self._annotation_edit_ts_by_image: Dict[int, float] = {}
        self._disable_bulk_accept_when_stale = True
        self._evidence_layer_config: Dict[str, dict] = {}
        self._evidence_layer_presets: Dict[str, dict] = {}
        self._active_evidence_preset_name: str = "custom"
        self._modality_compare_toggle_state: int = 0
        self._last_generation_context_signature: Dict[str, str] = {}
        self._last_generation_context_text: str = ""
        self._last_assist_context_delta_text: str = ""
        self._review_telemetry_started_ts: Optional[float] = None
        self._review_telemetry_last_ts: Optional[float] = None
        self._review_telemetry_baseline_accepted: int = 0
        self._review_telemetry_baseline_rejected: int = 0
        self._last_assist_state_name = None
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
        def _handle_projection_cache_warning(message: str) -> None:
            text = f"Memory warning: {message}"
            try:
                self._set_status(text)
            except Exception:
                pass
            try:
                self._append_log(f"[CACHE] {text}")
            except Exception:
                pass

        self._handle_projection_cache_warning = _handle_projection_cache_warning
        self.proj_cache.set_warning_callback(
            lambda msg: QtCore.QTimer.singleShot(
                0, lambda m=str(msg): self._handle_projection_cache_warning(m)
            )
        )
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
        self.modality_facade = None
        self.modality_playback = None
        self.view_sync = None

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
        self.dock_channels = None
        self.dock_annotations = None
        self.dock_review_queue = None
        self.dock_suggestion_explain = None
        self.dock_roi = None
        self.dock_logs = None
        self.dock_metadata = None
        self.dock_density = None
        self.dock_modality_layers = None
        self.dock_sidebar = None
        self.sidebar_stack = None
        self.sidebar_actions = []
        self.annotation_toolbar = None
        self.annotation_toolbar_action = None
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
        self._show_suggestion_overlay = True
        self._suggestion_model = LocalPeakSuggestionModel()
        self._interactive_learning_model = InteractiveLearningModel()
        self._suggestion_strategy = "current_view"
        self._canvas_header_verbose_context = True
        self._suggestion_score_threshold = 0.0
        self._suggestion_cursor = 0
        self._suggestion_focus_zoom_px = 160.0
        self._suggestion_rule_config = None
        self._timed_session_active = False
        self._timed_session_assisted = True
        self._timed_session_started_at = 0.0
        self._timed_session_accepts = 0
        self._timed_session_rejects = 0
        self._timed_session_points = 0
        self._timed_session_correction_time = 0.0
        self._review_queue_filter = "all"
        self._qc_issue_cursor = -1
        self.panel_specs: List[PanelSpec] = []
        self.panel_docks: Dict[str, QtWidgets.QDockWidget] = {}
        self.dock_actions: Dict[str, QtWidgets.QAction] = {}
        self.orthoview_widget = None
        self.smlm_panel = None
        self.threshold_panel = None
        self.particles_panel = None
        self.channel_panel = None
        self.channel_integration = None
        self._channel_panel_autoshown = False
        self.metadata_widget = None
        self.density_panel = None
        self.review_queue_panel = None
        self.suggestion_explain_panel = None
        self._roi_controls_layout = None
        
        # Pre-initialize widget references that are filled during UI setup.
        self.status = None
        self.hist_chk = None
        self.profile_chk = None
        self.show_hist_chk = None  # Alias for hist_chk
        self.show_profile_chk = None  # Alias for profile_chk
        self.hist_canvas = None
        self.profile_canvas = None
        self.hist_fig = None
        self.profile_fig = None
        self.ax_hist = None
        self.ax_line = None
        self.log_view = None
        self.cache_stats_label = None
        self.profile_mode_chk = None
        self.controller = SessionController(
            self,
            images,
            labels or DEFAULT_CONFIG.default_labels,
            self._settings,
            proj_cache=self.proj_cache,
            ring_buffer=self._playback_ring,
            colormaps=lut_names(),
        )
        self.modality_facade = ModalityFacade(self.controller.session_state)
        self.modality_playback = ModalityPlaybackManager(None)
        self.view_sync = ViewSyncManager(None)
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
        self._smlm_modality_idx: Optional[int] = None  # Phase ζ: Track modality for SMLM results
        self._deepstorm_results = []
        self._deepstorm_overlay = None
        self._deepstorm_overlay_extent = None
        self._deepstorm_job_id: Optional[str] = None
        self._deepstorm_run_id = 0
        self._deepstorm_modality_idx: Optional[int] = None  # Phase ζ: Track modality for Deep-STORM results
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._smlm_run_history: List[dict] = []
        self._last_smlm_run: Optional[dict] = None
        self._smlm_runbook_state = None
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
        self._particles_modality_idx: Optional[int] = None  # Phase ζ: Track modality for particle results
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
        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        if self.view_sync is not None:
            self.view_sync.view_changed.connect(self._on_view_sync_changed)
            self.view_sync.enable_zoom_sync(self.link_zoom)
            self.view_sync.enable_pan_sync(self.link_zoom)
        self._init_modality_playback()
        self._cleanup_recent_images()  # Remove missing paths from recent files list
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
        self._schedule_qc_validation()
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
