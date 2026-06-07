"""Runtime window runtime core helpers for the phage annotation tool.

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


from phage_annotator.ui_qt.runtime.window_init_impl import (
    init_settings_runtime,
    init_display_runtime_preferences,
    init_view_runtime_state,
    init_playback_runtime_state,
    init_refresh_runtime_state,
    init_render_job_runtime_state,
)
from phage_annotator.ui_qt.runtime.window_state import (
    init_widget_placeholder_state,
    init_feature_runtime_state,
    init_runtime_state,
    init_controller_runtime,
)
from phage_annotator.ui_qt.runtime.window_state_impl import bootstrap_runtime

__all__ = [
    'init_settings_runtime', 'init_display_runtime_preferences',
    'init_view_runtime_state', 'init_playback_runtime_state',
    'init_refresh_runtime_state', 'init_render_job_runtime_state',
    'init_widget_placeholder_state', 'init_feature_runtime_state',
    'init_runtime_state', 'init_controller_runtime', 'bootstrap_runtime',
]
