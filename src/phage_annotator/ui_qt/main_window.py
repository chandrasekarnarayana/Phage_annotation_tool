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
from typing import Dict, List, Optional, Sequence, Tuple

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
from phage_annotator.ui_qt.runtime import window_runtime, window_services
from phage_annotator.ui_qt.utils.modality_helpers import ModalityHelpersMixin
from phage_annotator.ui_qt.handlers.keyboard_handlers import KeyboardHandlersMixin
from phage_annotator.ui_qt.utils.context_menu import ContextMenuMixin
from phage_annotator.data.models import LazyImage
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.session.multi_playback import PlaybackMode
from phage_annotator.tools import Tool
from phage_annotator.ui_qt.services.action_logger import ActionLogger


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

    def _configure_window_behavior(self) -> None:
        """Apply non-modal window flags so the GUI stays cooperative with other apps."""
        window_runtime.configure_window_behavior(self)

    def _init_settings_runtime(self) -> None:
        """Initialize unified settings access and migrate persisted UI defaults."""
        window_runtime.init_settings_runtime(self)

    def _init_display_runtime_preferences(self) -> None:
        """Initialize persisted display/layout preferences consumed across mixins."""
        window_runtime.init_display_runtime_preferences(self)

    def _init_view_runtime_state(self) -> None:
        """Initialize lightweight runtime state used by view/layout coordination."""
        window_runtime.init_view_runtime_state(self)

    def _init_playback_runtime_state(self) -> None:
        """Initialize playback buffers and pacing state."""
        window_runtime.init_playback_runtime_state(self)

    def _init_refresh_runtime_state(self) -> None:
        """Initialize queued refresh and debounce timers."""
        window_runtime.init_refresh_runtime_state(self)

    def _init_render_job_runtime_state(self) -> None:
        """Initialize caches, job manager, and render-related runtime state."""
        window_runtime.init_render_job_runtime_state(self)

    def _init_widget_placeholder_state(self) -> None:
        """Initialize widget references populated later during UI setup."""
        window_runtime.init_widget_placeholder_state(self)

    def _init_feature_runtime_state(self) -> None:
        """Initialize feature-specific runtime state and persisted toggles."""
        window_runtime.init_feature_runtime_state(self)

    def _init_runtime_state(self) -> None:
        """Initialize window runtime state in explicit phases."""
        window_runtime.init_runtime_state(self)

    def _init_controller_runtime(self, images: List[LazyImage], labels: Sequence[str] | None) -> None:
        """Create controller-owned runtime collaborators and dependent services."""
        window_runtime.init_controller_runtime(self, images, labels)

    def _bootstrap_runtime(self, images: List[LazyImage], labels: Sequence[str] | None) -> None:
        """Initialize window-local runtime state before widgets are built."""
        window_runtime.bootstrap_runtime(self, images, labels)

    def _bootstrap_ui(self) -> None:
        """Build widgets and then attach signal-driven runtime integrations."""
        window_services.bootstrap_ui(self)

    def _wire_view_sync_runtime(self) -> None:
        """Attach linked-view runtime handlers after widgets exist."""
        window_services.wire_view_sync_runtime(self)

    def _restore_runtime_action_state(self) -> None:
        """Restore widget-backed runtime toggles after UI setup."""
        window_services.restore_runtime_action_state(self)

    def _bind_runtime_services(self) -> None:
        """Bind queued signals, recorder hooks, and global exception handling."""
        window_services.bind_runtime_services(self)

    def _initialize_session_view(self) -> None:
        """Load initial images and establish the first synchronized viewport."""
        window_services.initialize_session_view(self)

    def _start_background_runtime(self) -> None:
        """Start low-priority background services after the first UI frame is queued."""
        window_services.start_background_runtime(self)

    def _finalize_runtime_startup(self) -> None:
        """Complete GUI startup after UI setup and signal binding."""
        window_services.finalize_runtime_startup(self)

    def __init__(self, images: List[LazyImage], labels: Sequence[str] | None = None) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__()

        # Register GUI owner with unified ActionLogger for real-time GUI display
        ActionLogger.set_gui_owner(self)

        self._configure_window_behavior()
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
        self._bootstrap_runtime(images, labels)
        self._bootstrap_ui()


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
    """Run gui for the current workflow."""
    images = [img for img in (read_metadata(p) for p in image_paths) if img is not None]
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = KeypointAnnotator(images)
    window.show()
    app.exec()
