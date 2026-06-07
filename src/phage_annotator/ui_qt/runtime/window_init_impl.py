"""Runtime window init impl helpers for the phage annotation tool.

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
    ensure_ui_settings_defaults,
)
from phage_annotator.ui_qt.utils.constants import INTERACTIVE_DOWNSAMPLE, PLAYBACK_BUFFER_SIZE


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
        """Handle projection cache warning for the current workflow."""
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
