"""Runtime window state helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

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
    ensure_ui_settings_defaults)
from phage_annotator.ui_qt.utils.constants import INTERACTIVE_DOWNSAMPLE, PLAYBACK_BUFFER_SIZE



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
        "recorder_widget"):
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
        (owner)
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
        colormaps=lut_names())
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
        stop_event=owner._playback_stop_event)
