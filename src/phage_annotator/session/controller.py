"""Session controller for application state mutations.

This module keeps `SessionController` as the public entrypoint while routing
feature-specific behavior through focused controller mixins.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from phage_annotator.analysis.suggestion_ranker import LightweightSuggestionRanker
from phage_annotator.config.density import DensityConfig
from phage_annotator.core.rollout import default_workflow_metrics, normalize_feature_flags
from phage_annotator.core.session_state import SessionState, ViewState
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.density.model import DensityPredictor
from phage_annotator.roi.manager import Roi
from phage_annotator.session.annotation_io import SessionAnnotationIOMixin
from phage_annotator.session.annotations import SessionAnnotationsMixin
from phage_annotator.session.controller_annotation_contexts import SessionControllerAnnotationContextsMixin
from phage_annotator.session.controller_annotation_commands import SessionControllerAnnotationCommandsMixin
from phage_annotator.session.controller_display import SessionControllerDisplayMixin
from phage_annotator.session.controller_preferences import SessionControllerPreferencesMixin
from phage_annotator.session.controller_sync import SessionControllerSyncMixin
from phage_annotator.session.controller_smlm import SessionControllerSmlmMixin
from phage_annotator.session.controller_suggestions import SessionControllerSuggestionsMixin
from phage_annotator.session.controller_threshold_particles import SessionControllerThresholdParticlesMixin
from phage_annotator.session.images import SessionImageMixin
from phage_annotator.session.playback import SessionPlaybackMixin
from phage_annotator.session.project import SessionProjectMixin
from phage_annotator.session.view import SessionViewMixin

try:
    from phage_annotator.framework import get_log_service

    _logger = get_log_service().get_logger(__name__)
except (ImportError, RuntimeError, AttributeError):
    import logging

    _logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from phage_annotator.data.models import LazyImage


class SessionController(
    QtCore.QObject,
    SessionImageMixin,
    SessionViewMixin,
    SessionPlaybackMixin,
    SessionAnnotationsMixin,
    SessionAnnotationIOMixin,
    SessionControllerAnnotationContextsMixin,
    SessionProjectMixin,
    SessionControllerThresholdParticlesMixin,
    SessionControllerSuggestionsMixin,
    SessionControllerDisplayMixin,
    SessionControllerSmlmMixin,
    SessionControllerPreferencesMixin,
    SessionControllerSyncMixin,
    SessionControllerAnnotationCommandsMixin,
):
    """Main state controller for the GUI."""

    state_changed = QtCore.Signal()
    view_changed = QtCore.Signal()
    display_changed = QtCore.Signal()
    annotations_changed = QtCore.Signal()
    playback_changed = QtCore.Signal()
    error_occurred = QtCore.Signal(str)
    roi_changed = QtCore.Signal()

    def __init__(
        self,
        parent: QtCore.QObject,
        images: List["LazyImage"],
        labels: Sequence[str],
        settings: QtCore.QSettings,
        *,
        proj_cache=None,
        pyramid_cache=None,
        ring_buffer=None,
        colormaps: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(parent)
        if not images:
            raise ValueError("No images provided.")
        for idx, img in enumerate(images):
            img.id = idx
        label_list = list(labels) if labels else ["Point", "Region"]
        annotations = {img.id: [] for img in images}
        image_states = {img.id: self._build_image_state(img) for img in images}
        annotations_loaded = {img.id: False for img in images}
        self.session_state = SessionState(
            project_path=None,
            project_save_time=None,
            dirty=False,
            last_folder=None,
            recent_images=[],
            active_primary_id=0,
            active_support_id=0 if len(images) == 1 else 1,
            images=images,
            image_states=image_states,
            annotations=annotations,
            labels=label_list,
            current_label=label_list[0] if label_list else "",
            fps=int(settings.value("defaultFPS", 12, type=int)),
            annotations_loaded=annotations_loaded,
            suggestions={img.id: [] for img in images},
            suggestion_history={img.id: [] for img in images},
            feature_flags=normalize_feature_flags(
                {
                    key: settings.value(f"featureFlags/{key}", default, type=bool)
                    for key, default in normalize_feature_flags().items()
                }
            ),
            workflow_metrics=default_workflow_metrics(),
        )
        self.view_state = ViewState(
            t=0,
            z=0,
            crop_rect=(300.0, 300.0, 600.0, 600.0),
            hist_bins=int(settings.value("histBinsDefault", 100, type=int)),
        )
        self.display_mapping = DisplayMapping(0.0, 1.0)
        self.display_mapping.ensure_panels(("frame", "mean", "support", "std"))
        self.rois_by_image: Dict[int, List[Roi]] = {}
        self._settings = settings
        self._colormaps = list(colormaps) if colormaps is not None else []
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        self.proj_cache = proj_cache
        self.pyramid_cache = pyramid_cache
        self.ring_buffer = ring_buffer
        self._metadata_cache: Dict[pathlib.Path, object] = {}
        self.density_predictor: Optional[DensityPredictor] = None
        self.density_config = DensityConfig()
        self.density_infer_options = None
        self.density_model_path: Optional[str] = None
        self.density_device: str = "auto"
        self.density_target_panel: str = "frame"
        self.suggestion_ranker = LightweightSuggestionRanker()
        self._visible_context_suggestion_model = LocalPeakSuggestionModel()
        self.suggestion_rankers_by_space: Dict[str, LightweightSuggestionRanker] = {
            "stack": LightweightSuggestionRanker(),
            "projection": LightweightSuggestionRanker(),
        }
        self.session_state.suggestion_auto_retrain_enabled = bool(
            settings.value("suggestionAutoRetrainEnabled", True, type=bool)
        )
        self.session_state.suggestion_auto_retrain_min_labels = int(
            settings.value("suggestionAutoRetrainMinLabels", 25, type=int)
        )
        self.session_state.assist_min_total_labels = int(
            settings.value("assistMinTotalLabels", 30, type=int)
        )
        self.session_state.assist_min_positive_labels = int(
            settings.value("assistMinPositiveLabels", 15, type=int)
        )
        self.session_state.assist_min_negative_labels = int(
            settings.value("assistMinNegativeLabels", 15, type=int)
        )
        self.session_state.assist_min_labels_per_context = int(
            settings.value("assistMinLabelsPerContext", 10, type=int)
        )
        self._ranker_retrain_timer = QtCore.QTimer(self)
        self._ranker_retrain_timer.setSingleShot(True)
        self._ranker_retrain_timer.setInterval(800)
        self._ranker_retrain_timer.timeout.connect(self._retrain_timer_fired)
        self._local_suggestion_rescore_timer = QtCore.QTimer(self)
        self._local_suggestion_rescore_timer.setSingleShot(True)
        self._local_suggestion_rescore_timer.setInterval(
            int(self.session_state.assist_local_rescore_debounce_ms)
        )
        self._local_suggestion_rescore_timer.timeout.connect(self._local_rescore_timer_fired)
        self._pending_local_rescore_context: dict[str, object] | None = None
        self._local_rescore_edit_count = 0
