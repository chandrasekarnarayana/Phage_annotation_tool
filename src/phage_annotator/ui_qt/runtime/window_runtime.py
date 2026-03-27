"""Runtime bootstrap helpers for the main Qt window."""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.annotation.core import Keypoint
from phage_annotator.cache.projection_cache import ProjectionCache
from phage_annotator.config.settings import DEFAULT_CONFIG
from phage_annotator.data.models import LazyImage
from phage_annotator.data.ring_buffer import BlockPrefetcher, FrameRingBuffer
from phage_annotator.roi.manager import RoiManager
from phage_annotator.session.controller import SessionController
from phage_annotator.session.modality_facade import ModalityFacade
from phage_annotator.session.multi_playback import ModalityPlaybackManager
from phage_annotator.session.view_sync import ViewSyncManager
from phage_annotator.ui_qt.models.lazy_loader import LazyLoaderManifest
from phage_annotator.ui_qt.panels.recorder import ActionRecorder
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.services.jobs import JobManager
from phage_annotator.ui_qt.services.status import StatusService
from phage_annotator.ui_qt.services.settings_proxy import UnifiedSettingsProxy
from phage_annotator.ui_qt.services.settings_schema import (
    apply_settings_migrations,
    ensure_ui_settings_defaults,
)
from phage_annotator.ui_qt.utils.constants import INTERACTIVE_DOWNSAMPLE, PLAYBACK_BUFFER_SIZE


def configure_window_behavior(owner) -> None:
    """Apply non-modal window flags so the GUI stays cooperative with other apps."""
    owner.setWindowFlags(owner.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)


def init_settings_runtime(owner) -> None:
    """Initialize unified settings access and migrate persisted UI defaults."""
    qsettings = QtCore.QSettings("PhageAnnotator", "PhageAnnotator")
    try:
        from phage_annotator.framework import get_settings_service

        owner._settings_service = get_settings_service()
    except (ImportError, RuntimeError, AttributeError):
        owner._settings_service = None
    owner._settings = UnifiedSettingsProxy(qsettings, owner._settings_service)
    apply_settings_migrations(owner._settings)
    ensure_ui_settings_defaults(owner._settings)


def init_display_runtime_preferences(owner) -> None:
    """Initialize persisted display/layout preferences consumed across mixins."""
    owner.marker_size = owner._get_setting("markerSize", 40, int)
    owner.marker_shape = str(owner._get_setting("markerShape", "o", str) or "o")
    owner.click_radius_px = owner._get_setting("clickRadiusPx", 6.0, float)
    owner._canvas_layout_rows = int(owner._settings.value("canvasLayoutRows", 0, type=int))
    owner._canvas_layout_cols = int(owner._settings.value("canvasLayoutCols", 0, type=int))
    owner._skip_capture_once = False
    owner.pixel_size_um_per_px = float(owner._get_setting("defaultPixelSizeUmPerPx", 0.069, float))
    owner._prefetch_disabled = False
    owner._adaptive_tile_size = 256
    owner._lod_mode_active: Dict[int, bool] = {}


def init_view_runtime_state(owner) -> None:
    """Initialize lightweight runtime state used by view/layout coordination."""
    owner._last_zoom_linked: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
    owner._axis_zoom: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = {}
    owner._left_sizes: Optional[List[int]] = None
    owner._block_table = False
    owner._table_rows: List[Keypoint] = []
    owner._selected_annotation_ids: set[str] = set()
    owner._suppress_limits = False
    owner._panel_visibility = {"modality_0": False, "modality_1": False}
    sync_groups = {
        0: "1",
        1: "1",
        "builtin:support": "1",
        "builtin:mean": "1",
        "builtin:std": "1",
    }
    sync_modes = {
        0: {"contrast": True, "zoom": True, "playback": True},
        1: {"contrast": True, "zoom": True, "playback": True},
        "builtin:support": {"contrast": True, "zoom": True, "playback": True},
        "builtin:mean": {"contrast": True, "zoom": True, "playback": True},
        "builtin:std": {"contrast": True, "zoom": True, "playback": True},
    }
    owner.controller.session_state.lazy_sync_groups = dict(sync_groups)
    owner.controller.session_state.lazy_sync_modes = {
        key: dict(value) for key, value in sync_modes.items()
    }
    owner.controller.session_state.roi_by_sync_group = {}
    owner._lazy_builtin_views = {}
    owner._lazy_builtin_seeded = False
    owner._lazy_builtin_migrated = False
    owner._lazy_hidden_base_panel_keys = {"modality_0", "modality_1"}
    owner._lazy_panel_order = {}
    owner._panel_modality_map = {}
    owner._annotation_panel_visibility = {}
    owner._annotation_write_context_pending = False
    owner._annotation_context_change_reason = ""
    owner._annotation_write_context_pending_value = None
    owner._annotation_write_context_confirmed = None
    owner._annotation_edit_ts_by_image = {}
    owner._disable_bulk_accept_when_stale = bool(
        owner._settings.value("disableBulkAcceptWhenStale", True, type=bool)
    )
    owner._evidence_layer_config = {}
    owner._evidence_layer_presets = {}
    owner._active_evidence_preset_name = "custom"
    owner._modality_compare_toggle_state = 0
    owner._last_generation_context_signature = {}
    owner._last_generation_context_text = ""
    owner._last_assist_context_delta_text = ""
    owner._review_telemetry_started_ts = None
    owner._review_telemetry_last_ts = None
    owner._review_telemetry_baseline_accepted = 0
    owner._review_telemetry_baseline_rejected = 0
    owner._last_assist_state_name = None
    owner._default_geometry = None
    owner._default_state = None
    owner._preset_active = False
    owner._interactive = False
    owner._cursor_xy = None


def init_playback_runtime_state(owner) -> None:
    """Initialize playback buffers and pacing state."""
    owner.play_timer = QtCore.QTimer()
    owner._playback_mode = False
    owner._playback_ring = FrameRingBuffer(PLAYBACK_BUFFER_SIZE)
    owner._playback_stop_event = threading.Event()
    owner._playback_thread = None
    owner._playback_buffer_size = PLAYBACK_BUFFER_SIZE
    owner._playback_direction = 1
    owner._playback_overlay_stride = 3
    owner._playback_frame_counter = 0
    owner._fps_times: Deque[float] = deque(maxlen=120)
    owner._fps_text = None
    owner._playback_cursor = 0
    owner._last_frame_time = None
    owner._playback_underruns = 0


def init_refresh_runtime_state(owner) -> None:
    """Initialize queued refresh and debounce timers."""
    owner._lazy_loader_manifest = LazyLoaderManifest()
    owner._lazy_loader_path_to_ids = {}
    owner._lazy_apply_timer = QtCore.QTimer(owner)
    owner._lazy_apply_timer.setSingleShot(True)
    owner._lazy_apply_timer.setInterval(0)
    owner._lazy_apply_timer.timeout.connect(owner._flush_lazy_canvas_refresh)
    owner._lazy_apply_table_refresh = True
    owner._lazy_refresh_reason = ""
    owner._ui_refresh_timer = QtCore.QTimer(owner)
    owner._ui_refresh_timer.setSingleShot(True)
    owner._ui_refresh_timer.setInterval(0)
    owner._ui_refresh_timer.timeout.connect(owner._flush_ui_refresh)
    owner._ui_refresh_flags = {"image": False, "table": False, "status": False, "metadata": False}
    owner._ui_refresh_reason = ""
    owner.status_service = StatusService(owner)
    owner._debounce_timer = QtCore.QTimer()
    owner._debounce_timer.setSingleShot(True)
    owner._debounce_timer.setInterval(80)
    owner._debounce_timer.timeout.connect(owner._refresh_image)


def init_render_job_runtime_state(owner) -> None:
    """Initialize caches, job manager, and render-related runtime state."""
    owner.downsample_factor = int(owner._settings.value("downsampleFactor", INTERACTIVE_DOWNSAMPLE, type=int))
    owner.downsample_images = bool(owner._settings.value("downsampleImages", True, type=bool))
    owner.downsample_hist = bool(owner._settings.value("downsampleHist", True, type=bool))
    owner.downsample_profile = bool(owner._settings.value("downsampleProfile", True, type=bool))
    owner._job_generation = 0
    owner._projection_jobs = {}
    owner._pyramid_jobs = {}
    cache_max_mb = owner._settings.value("cacheMaxMB", 1024, type=int)
    owner.proj_cache = ProjectionCache(max_mb=cache_max_mb)

    def _handle_projection_cache_warning(message: str) -> None:
        text = f"Memory warning: {message}"
        try:
            owner._status_warning(text, sticky=True, source="projection_cache")
        except Exception:
            pass
        try:
            owner._append_log(f"[CACHE] {text}")
        except Exception:
            pass

    owner._handle_projection_cache_warning = _handle_projection_cache_warning
    owner.proj_cache.set_warning_callback(
        lambda msg: QtCore.QTimer.singleShot(0, lambda m=str(msg): owner._handle_projection_cache_warning(m))
    )
    owner._diag_hist_source = None
    owner.jobs = JobManager(owner)
    owner.jobs.set_ui_busy_provider(
        lambda: bool(getattr(owner, "_interactive", False) or getattr(owner, "_playback_mode", False))
    )
    owner._active_job_id = None
    owner._active_job_name = None
    owner._annotation_job_ids = {}
    owner._annotation_job_tokens = {}
    owner._pending_annotation_meta = None
    owner._pending_annotation_meta_image_id = None


def init_widget_placeholder_state(owner) -> None:
    """Initialize widget references populated later during UI setup."""
    for attr in (
        "progress_label",
        "progress_bar",
        "progress_cancel_btn",
        "log_view",
        "cache_stats_label",
        "buffer_stats_label",
        "_dev_demo_job_act",
        "modality_facade",
        "modality_playback",
        "view_sync",
        "im_frame",
        "im_mean",
        "im_comp",
        "im_support",
        "im_std",
        "hist_fig",
        "hist_canvas",
        "contrast_hist_fig",
        "contrast_hist_canvas",
        "profile_fig",
        "profile_canvas",
        "dock_hist",
        "dock_profile",
        "dock_orthoview",
        "dock_smlm",
        "dock_threshold",
        "dock_particles",
        "dock_channels",
        "dock_annotations",
        "dock_review_queue",
        "dock_roi",
        "dock_logs",
        "dock_metadata",
        "dock_density",
        "dock_sidebar",
        "sidebar_stack",
        "annotation_toolbar",
        "annotation_toolbar_action",
        "command_palette_act",
        "reset_view_act",
        "tool_router",
        "tool_label",
        "overlay_text",
        "render_level_label",
        "status",
        "status_context_lbl",
        "status_state_lbl",
        "status_metric_lbl",
        "status_logs_lbl",
        "hist_chk",
        "profile_chk",
        "show_hist_chk",
        "show_profile_chk",
        "ax_hist",
        "ax_contrast_hist",
        "ax_line",
        "profile_mode_chk",
        "orthoview_widget",
        "smlm_panel",
        "threshold_panel",
        "particles_panel",
        "channel_panel",
        "channel_integration",
        "metadata_widget",
        "density_panel",
        "review_queue_panel",
        "suggestion_explain_panel",
        "_roi_controls_layout",
        "roi_manager_widget",
        "results_widget",
        "recorder_widget",
    ):
        setattr(owner, attr, None)
    owner.sidebar_actions = []
    owner.tool_actions = {}
    owner._render_scales = {}


def init_feature_runtime_state(owner) -> None:
    """Initialize feature-specific runtime state and persisted toggles."""
    owner._channel_panel_autoshown = False
    owner.scale_bar_enabled = bool(owner._settings.value("scaleBarEnabled", False, type=bool))
    owner.scale_bar_length_um = float(owner._settings.value("scaleBarLengthUm", 5.0, type=float))
    owner.scale_bar_thickness_px = int(owner._settings.value("scaleBarThicknessPx", 4, type=int))
    owner.scale_bar_location = owner._settings.value("scaleBarLocation", "bottom_right", type=str)
    owner.scale_bar_padding_px = int(owner._settings.value("scaleBarPaddingPx", 12, type=int))
    owner.scale_bar_show_text = bool(owner._settings.value("scaleBarShowText", True, type=bool))
    owner.scale_bar_text_offset_px = int(owner._settings.value("scaleBarTextOffsetPx", 6, type=int))
    owner.scale_bar_background_box = bool(owner._settings.value("scaleBarBackgroundBox", True, type=bool))
    owner.scale_bar_include_in_export = bool(owner._settings.value("scaleBarIncludeInExport", True, type=bool))
    owner.show_roi_handles = bool(owner._settings.value("showRoiHandles", True, type=bool))
    owner._density_job_id = None
    owner._density_overlay = None
    owner._density_overlay_extent = None
    owner._density_overlay_alpha = 0.6
    owner._density_overlay_cmap = "magma"
    owner._density_contours = False
    owner._density_last_result = None
    owner._density_last_panel = "frame"
    owner._show_suggestion_overlay = True
    owner._suggestion_overlay_limit = int(
        owner._settings.value("suggestionOverlayLimit", 24, type=int)
    )
    from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel

    owner._suggestion_model = LocalPeakSuggestionModel()
    if bool(owner.controller.feature_enabled("interactive_learning_experimental", False)):
        from phage_annotator.analysis.interactive_learning import InteractiveLearningModel

        owner._interactive_learning_model = InteractiveLearningModel()
    owner._suggestion_strategy = "current_view"
    owner._canvas_header_verbose_context = True
    owner._suggestion_score_threshold = 0.0
    owner._suggestion_cursor = 0
    owner._suggestion_focus_zoom_px = 160.0
    owner._suggestion_rule_config = None
    owner._timed_session_active = False
    owner._timed_session_assisted = True
    owner._timed_session_started_at = 0.0
    owner._timed_session_accepts = 0
    owner._timed_session_rejects = 0
    owner._timed_session_points = 0
    owner._timed_session_correction_time = 0.0
    owner._review_queue_filter = "all"
    owner._qc_issue_cursor = -1
    owner.panel_specs: List[PanelSpec] = []
    owner.panel_docks = {}
    owner.dock_actions = {}
    owner._analysis_last_submit = 0.0
    owner._analysis_submit_pending = False
    owner._contrast_drag_active = False
    owner._auto_job_id = None
    owner._norm_cache = {}
    owner._hist_job_id = None
    owner._smlm_results = []
    owner._smlm_overlay = None
    owner._smlm_overlay_extent = None
    owner._smlm_job_id = None
    owner._smlm_run_id = 0
    owner._smlm_modality_idx = None
    owner._deepstorm_results = []
    owner._deepstorm_overlay = None
    owner._deepstorm_overlay_extent = None
    owner._deepstorm_job_id = None
    owner._deepstorm_run_id = 0
    owner._deepstorm_modality_idx = None
    owner._sr_overlay = None
    owner._sr_overlay_extent = None
    owner._smlm_run_history = []
    owner._last_smlm_run = None
    owner._smlm_runbook_state = None
    owner.show_smlm_points = True
    owner.show_sr_overlay = True
    owner._threshold_preview_mask = None
    owner._threshold_preview_extent = None
    owner._threshold_mask_full = None
    owner._threshold_job_id = None
    owner._threshold_auto_value = None
    owner._threshold_settings = {}
    owner._threshold_timer = QtCore.QTimer()
    owner._threshold_timer.setSingleShot(True)
    owner._threshold_timer.setInterval(80)
    owner._threshold_timer.timeout.connect(owner._threshold_refresh_preview)
    owner._binary_view_mask = None
    owner._binary_view_enabled = False
    owner._particles_results = []
    owner._particles_modality_idx = None
    owner._particles_overlays = []
    owner._particles_selected = None
    owner._particles_job_id = None
    owner._auto_roi_job_id = None
    owner._hist_cache = None
    owner._hist_cache_key = None
    owner._hist_last_time = 0.0
    owner._hist_scope_mode = "Current slice"
    owner.roi_manager = RoiManager()
    owner.recorder = ActionRecorder()
    owner._action_map = {}
    owner.pyramid_enabled = bool(owner._settings.value("pyramidEnabled", False, type=bool))
    owner.pyramid_max_levels = int(owner._settings.value("pyramidMaxLevels", 3, type=int))
    owner._last_render_level = 0


def init_runtime_state(owner) -> None:
    """Initialize window runtime state in explicit phases."""
    init_playback_runtime_state(owner)
    init_refresh_runtime_state(owner)
    init_render_job_runtime_state(owner)
    init_widget_placeholder_state(owner)
    # These phases require owner.controller and must run after controller init.
    if getattr(owner, "controller", None) is not None:
        init_view_runtime_state(owner)
        init_feature_runtime_state(owner)


def init_controller_runtime(owner, images: List[LazyImage], labels: Sequence[str] | None) -> None:
    """Create controller-owned runtime collaborators and dependent services."""
    owner.controller = SessionController(
        owner,
        images,
        labels or DEFAULT_CONFIG.default_labels,
        owner._settings,
        proj_cache=owner.proj_cache,
        ring_buffer=owner._playback_ring,
        colormaps=lut_names(),
    )
    owner.modality_facade = ModalityFacade(owner.controller.session_state)
    owner.modality_playback = ModalityPlaybackManager(None)
    owner.view_sync = ViewSyncManager(None)
    owner.colormaps = lut_names()
    owner._autosave_timer = QtCore.QTimer()
    owner._autosave_timer.setInterval(120000)
    owner._autosave_timer.timeout.connect(owner._autosave_tick)
    owner._prefetcher = BlockPrefetcher(
        owner._read_playback_block,
        owner._playback_ring,
        block_size=int(owner._settings.value("prefetchBlockSizeFrames", 64, type=int)),
        max_inflight_blocks=int(owner._settings.value("prefetchMaxInflightBlocks", 2, type=int)),
        stop_event=owner._playback_stop_event,
    )


def bootstrap_runtime(owner, images: List[LazyImage], labels: Sequence[str] | None) -> None:
    """Initialize window-local runtime state before widgets are built."""
    init_settings_runtime(owner)
    init_display_runtime_preferences(owner)
    init_runtime_state(owner)
    init_controller_runtime(owner, images, labels)
    init_view_runtime_state(owner)
    init_feature_runtime_state(owner)
