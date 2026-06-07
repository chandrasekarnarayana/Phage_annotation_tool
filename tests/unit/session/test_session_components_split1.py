"""Split definitions from test_session_components.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.core.session_state import RoiSpec, SessionState, ViewState
from phage_annotator.data.display_mapping import DisplayMapping, mapping_from_dict
from phage_annotator.annotation.core import Keypoint
from phage_annotator.session.commands import (
    SetCropCommand,
    SetDisplayMappingCommand,
    SetThresholdCommand,
    command_from_dict,
)
from phage_annotator.session.batch_commands import BatchAssignLabelCommand
from phage_annotator.session.navigation_commands import JumpToFrameCommand
from phage_annotator.session.metadata_commands import UpdateMetadataCommand
from phage_annotator.session.controller import SessionController
from phage_annotator.session.images import SessionImageMixin
import phage_annotator.session.state as session_state_module
import phage_annotator.session.view as session_view_module
from phage_annotator.ui_qt.utils.state import StateMixin


class _Emitter:
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.count = 0

    def emit(self) -> None:
        """Emit emit for the current workflow."""
        self.count += 1

@dataclass
class _ImageStub:
    id: int
    path: Path
    shape: tuple[int, ...]
    has_time: bool
    has_z: bool
    interpret_3d_as: str = "auto"
    metadata_summary: dict = field(default_factory=dict)
    pixel_size_um: float = 0.0
    ome_axes: Optional[str] = None
    axis_auto_used: bool = False
    axis_auto_mode: Optional[str] = None
    array: Optional[np.ndarray] = None

class _SessionImageHarness(SessionImageMixin):
    def __init__(self, images: list[_ImageStub]) -> None:
        """Initialize the object and prepare its runtime state."""
        self.state_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self._metadata_cache = {}

        image_states = {}
        for img in images:
            image_states[img.id] = self._build_image_state(img)

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
            annotations={img.id: [] for img in images},
            labels=["Point"],
            current_label="Point",
            annotations_loaded={img.id: False for img in images},
        )

class _SessionViewHarness(session_view_module.SessionViewMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.session_state = SimpleNamespace(active_primary_id=0)
        self.view_state = ViewState()
        self.display_mapping = DisplayMapping(0.1, 0.9)

class _SessionImageViewHarness(SessionImageMixin, session_view_module.SessionViewMixin):
    def __init__(self, images: list[_ImageStub]) -> None:
        """Initialize the object and prepare its runtime state."""
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self._metadata_cache = {}
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

        image_states = {}
        for img in images:
            image_states[img.id] = self._build_image_state(img)

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
            annotations={img.id: [] for img in images},
            labels=["Point"],
            current_label="Point",
            annotations_loaded={img.id: False for img in images},
        )
        self.view_state = ViewState()
        self.display_mapping = DisplayMapping(0.1, 0.9)

class _ControllerMutationHarness:
    """Minimal non-Qt harness for exercising controller mutation methods."""

    set_threshold_preview_settings = SessionController.set_threshold_preview_settings
    store_threshold_mask = SessionController.store_threshold_mask
    set_particles_config = SessionController.set_particles_config
    append_generated_suggestions = SessionController.append_generated_suggestions
    sort_pending_suggestions = SessionController.sort_pending_suggestions
    get_suggestion_decision_context = SessionController.get_suggestion_decision_context
    get_visible_suggestions = SessionController.get_visible_suggestions
    get_slice_suggestions = SessionController.get_slice_suggestions
    remove_annotations_for_suggestion = SessionController.remove_annotations_for_suggestion
    append_annotation_from_suggestion = SessionController.append_annotation_from_suggestion
    update_suggestion_decision = SessionController.update_suggestion_decision
    set_channel_display_settings_value = SessionController.set_channel_display_settings_value
    set_current_user_value = SessionController.set_current_user_value
    set_suggestion_retrain_config = SessionController.set_suggestion_retrain_config
    set_assist_minima = SessionController.set_assist_minima
    set_generation_space_value = SessionController.set_generation_space_value
    set_disable_bulk_accept_when_stale_value = (
        SessionController.set_disable_bulk_accept_when_stale_value
    )
    get_qc_issues = SessionController.get_qc_issues
    get_suggestion_calibration_samples = SessionController.get_suggestion_calibration_samples
    update_annotation_metadata = SessionController.update_annotation_metadata
    bulk_update_annotation_metadata = SessionController.bulk_update_annotation_metadata
    update_annotation_label = SessionController.update_annotation_label
    batch_assign_missing_labels = SessionController.batch_assign_missing_labels
    batch_delete_duplicate_annotations = SessionController.batch_delete_duplicate_annotations
    batch_delete_out_of_bounds_annotations = SessionController.batch_delete_out_of_bounds_annotations
    batch_review_density_clusters = SessionController.batch_review_density_clusters
    annotation_context_key_for_panel = SessionController.annotation_context_key_for_panel
    ensure_annotation_context_for_panel = SessionController.ensure_annotation_context_for_panel
    current_annotation_context = SessionController.current_annotation_context
    annotations_for_panel = SessionController.annotations_for_panel
    bind_annotation_file_to_panel = SessionController.bind_annotation_file_to_panel
    annotation_binding_for_panel = SessionController.annotation_binding_for_panel
    clear_annotation_binding_for_panel = SessionController.clear_annotation_binding_for_panel
    set_annotation_context_mode_for_panel = SessionController.set_annotation_context_mode_for_panel
    get_lazy_sync_groups = SessionController.get_lazy_sync_groups
    set_lazy_sync_group = SessionController.set_lazy_sync_group
    get_lazy_sync_modes = SessionController.get_lazy_sync_modes
    set_lazy_sync_mode = SessionController.set_lazy_sync_mode
    roi_state_for_sync_group = SessionController.roi_state_for_sync_group
    set_roi_state_for_sync_group = SessionController.set_roi_state_for_sync_group
    feature_enabled = SessionController.feature_enabled
    set_feature_flag = SessionController.set_feature_flag
    record_workflow_event = SessionController.record_workflow_event
    workflow_metrics_snapshot = SessionController.workflow_metrics_snapshot
    refresh_provenance_coverage_metrics = SessionController.refresh_provenance_coverage_metrics
    add_annotation = SessionController.add_annotation
    append_audit_event = SessionController.append_audit_event
    _find_annotation_context_spec = SessionController._find_annotation_context_spec
    _panel_source_image_id = SessionController._panel_source_image_id
    _panel_modality_idx = SessionController._panel_modality_idx
    _panel_projection_key = SessionController._panel_projection_key
    _default_annotation_context_mode = SessionController._default_annotation_context_mode
    _stable_suggestion_sort_key = staticmethod(SessionController._stable_suggestion_sort_key)
    _normalize_local_context = SessionController._normalize_local_context
    _row_matches_context = SessionController._row_matches_context
    _suggestion_distance_px = SessionController._suggestion_distance_px
    _update_local_suggestion_features = SessionController._update_local_suggestion_features
    get_local_neighbors = SessionController.get_local_neighbors

    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.state_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.display_changed = _Emitter()
        self.view_changed = _Emitter()
        self.roi_changed = _Emitter()
        self.session_state = SessionState(
            project_path=None,
            project_save_time=None,
            dirty=False,
            last_folder=None,
            recent_images=[],
            active_primary_id=0,
            active_support_id=0,
            images=[],
            image_states={},
            annotations={0: []},
            labels=["Point"],
            current_label="Point",
            annotations_loaded={0: False},
            suggestions={0: []},
            suggestion_history={0: []},
        )
        self._ranker_retrain_timer = SimpleNamespace(start=lambda *args, **kwargs: None)
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.view_state = ViewState()
        self.display_mapping = DisplayMapping(0.0, 1.0)
        self._settings = SimpleNamespace(setValue=lambda *args, **kwargs: None)

    def set_dirty(self, dirty: bool = True) -> None:
        """Set dirty for the current workflow."""
        if self.session_state.dirty == dirty:
            return
        self.session_state.dirty = dirty
        self.state_changed.emit()

    def get_annotations(self, image_id: int):
        """Return annotations for the current workflow."""
        return self.session_state.annotations.setdefault(int(image_id), [])

    def _push_undo(self, action: dict) -> None:
        """Handle the push undo helper flow."""
        self._undo_stack.append(action)
        self._redo_stack.clear()

    def execute_view_command(self, command) -> bool:
        """Execute view command for the current workflow."""
        return session_view_module.SessionViewMixin.execute_view_command(self, command)

    def _push_undo_view(self, command_dict: dict) -> None:
        """Handle the push undo view helper flow."""
        return session_view_module.SessionViewMixin._push_undo_view(self, command_dict)

    def can_undo(self) -> bool:
        """Run the can undo workflow."""
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        """Run the can redo workflow."""
        return bool(self._redo_stack)
