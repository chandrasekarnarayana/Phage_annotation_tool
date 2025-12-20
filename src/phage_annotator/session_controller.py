"""Session controller for application state mutations.

This module provides the SessionController QObject that owns session, view, and
display state for the GUI. The controller emits signals back to the UI when
state changes, ensuring mutation happens in one place and the GUI only reacts
to state updates.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Sequence

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.density_config import DensityConfig
from phage_annotator.density_model import DensityPredictor
from phage_annotator.display_mapping import DisplayMapping
from phage_annotator.roi_manager import Roi
from phage_annotator.session_state import SessionState, ViewState
from phage_annotator.session_controller_annotations import SessionAnnotationsMixin
from phage_annotator.session_controller_annotation_io import SessionAnnotationIOMixin
from phage_annotator.session_controller_images import SessionImageMixin
from phage_annotator.session_controller_playback import SessionPlaybackMixin
from phage_annotator.session_controller_project import SessionProjectMixin
from phage_annotator.session_controller_view import SessionViewMixin


class SessionController(
    QtCore.QObject,
    SessionImageMixin,
    SessionViewMixin,
    SessionPlaybackMixin,
    SessionAnnotationsMixin,
    SessionAnnotationIOMixin,
    SessionProjectMixin,
):
    """Main state controller for the GUI.

    Notes
    -----
    All state mutations should occur through this controller, which emits
    Qt signals for the GUI to react. Arrays may be memmapped; annotations
    are always stored in full-resolution pixel coordinates.
    """

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
        label_list = list(labels)
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
        )
        self.view_state = ViewState(
            t=0,
            z=0,
            crop_rect=(300.0, 300.0, 600.0, 600.0),
        )
        self.display_mapping = DisplayMapping(0.0, 1.0)
        self.display_mapping.ensure_panels(("frame", "mean", "composite", "support", "std"))
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
