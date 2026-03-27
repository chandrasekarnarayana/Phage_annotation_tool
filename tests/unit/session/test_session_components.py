"""Unit tests for session package modules without GUI instantiation."""

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
        self.count = 0

    def emit(self) -> None:
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
        if self.session_state.dirty == dirty:
            return
        self.session_state.dirty = dirty
        self.state_changed.emit()

    def get_annotations(self, image_id: int):
        return self.session_state.annotations.setdefault(int(image_id), [])

    def _push_undo(self, action: dict) -> None:
        self._undo_stack.append(action)
        self._redo_stack.clear()

    def execute_view_command(self, command) -> bool:
        return session_view_module.SessionViewMixin.execute_view_command(self, command)

    def _push_undo_view(self, command_dict: dict) -> None:
        return session_view_module.SessionViewMixin._push_undo_view(self, command_dict)

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)


class _StateProxyHarness(StateMixin):
    """Harness for verifying GUI state proxies are read-only snapshots."""

    def __init__(self) -> None:
        self.controller = SimpleNamespace(
            session_state=SessionState(
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
            ),
            view_state=ViewState(),
            display_mapping=DisplayMapping(0.0, 1.0),
            set_images=lambda value: None,
            set_current_label=lambda value: None,
            set_primary=lambda value: None,
            set_support=lambda value: None,
            set_lut=lambda value: None,
            set_display_mapping=lambda *args, **kwargs: None,
            stop_playback=lambda: None,
            start_playback=lambda value: None,
            set_loop=lambda value: None,
            set_profile_line=lambda value: None,
            set_profile_enabled=lambda value: None,
            set_hist_enabled=lambda value: None,
            set_hist_bins=lambda value: None,
            set_hist_region=lambda value: None,
            set_link_zoom=lambda value: None,
            set_roi=lambda *args, **kwargs: None,
            set_crop=lambda value: None,
            set_annotate_target=lambda value: None,
            set_annotation_scope=lambda value: None,
            set_show_annotations=lambda frame, mean: None,
            set_dirty=lambda value: None,
            set_project_path=lambda value: None,
            set_last_folder=lambda value: None,
            set_project_save_time=lambda value: None,
            set_overlay_enabled=lambda value: None,
        )


def test_session_images_build_image_state_respects_axis_flags(tmp_path: Path) -> None:
    """Image-state dims should map to canonical (T, Z, Y, X) based on flags."""
    harness = _SessionImageHarness(
        [
            _ImageStub(0, tmp_path / "a.tif", (64, 32), has_time=False, has_z=False),
        ]
    )

    two_d = harness._build_image_state(_ImageStub(0, tmp_path / "a.tif", (64, 32), False, False))
    time_3d = harness._build_image_state(_ImageStub(0, tmp_path / "b.tif", (5, 64, 32), True, False))
    z_3d = harness._build_image_state(_ImageStub(0, tmp_path / "c.tif", (7, 64, 32), False, True))
    four_d = harness._build_image_state(
        _ImageStub(0, tmp_path / "d.tif", (2, 3, 64, 32), True, True)
    )

    assert two_d.dims == (1, 1, 64, 32)
    assert time_3d.dims == (5, 1, 64, 32)
    assert z_3d.dims == (1, 7, 64, 32)
    assert four_d.dims == (2, 3, 64, 32)


def test_annotation_context_defaults_are_projection_aware() -> None:
    """Raw rows default to independent contexts while projections share source context."""
    harness = _ControllerMutationHarness()

    frame = harness.ensure_annotation_context_for_panel("frame")
    mean = harness.ensure_annotation_context_for_panel("mean")
    support = harness.ensure_annotation_context_for_panel("support")

    assert frame["mode"] == "independent"
    assert support["mode"] == "independent"
    assert mean["mode"] == "shared_source"
    assert str(mean["context_key"]).startswith("img:0|space:stack|shared")


def test_annotations_for_panel_prefers_explicit_context_and_tracks_binding() -> None:
    """Panel lookups should resolve by annotation context, not just raw image id."""
    harness = _ControllerMutationHarness()

    frame_context = harness.ensure_annotation_context_for_panel("frame")
    support_context = harness.ensure_annotation_context_for_panel("support")

    frame_point = Keypoint(
        image_id=0,
        image_name="img0",
        t=-1,
        z=-1,
        y=10.0,
        x=20.0,
        label="Point",
        modality_idx=0,
        annotation_context=str(frame_context["context_key"]),
    )
    support_point = Keypoint(
        image_id=0,
        image_name="img0",
        t=-1,
        z=-1,
        y=11.0,
        x=21.0,
        label="Point",
        modality_idx=1,
        annotation_context=str(support_context["context_key"]),
    )
    harness.session_state.annotations[0] = [frame_point, support_point]

    assert harness.annotations_for_panel("frame") == [frame_point]
    assert harness.annotations_for_panel("support") == [support_point]

    harness.bind_annotation_file_to_panel("support", "/tmp/support.annotations.json", fmt="json")
    binding = harness.annotation_binding_for_panel("support")
    assert binding["path"] == "/tmp/support.annotations.json"


def test_annotation_context_mode_switch_updates_writability_without_losing_binding() -> None:
    """Mode changes should preserve logical context behavior and file binding."""
    harness = _ControllerMutationHarness()
    harness.ensure_annotation_context_for_panel("mean")
    harness.bind_annotation_file_to_panel("mean", "/tmp/mean.annotations.json", fmt="json")

    readonly = harness.set_annotation_context_mode_for_panel("mean", "read_only")
    assert readonly["mode"] == "read_only"
    assert readonly["writable"] is False
    assert harness.annotation_binding_for_panel("mean")["path"] == "/tmp/mean.annotations.json"

    shared = harness.set_annotation_context_mode_for_panel("mean", "shared_source")
    assert shared["mode"] == "shared_source"
    assert shared["ownership_mode"] == "shared_source"
    assert shared["writable"] is True

    harness.clear_annotation_binding_for_panel("mean")
    assert harness.annotation_binding_for_panel("mean") == {}


def test_lazy_sync_group_and_modes_are_controller_owned() -> None:
    """Lazy sync grouping should persist through controller APIs, not window locals."""
    harness = _ControllerMutationHarness()

    assert harness.get_lazy_sync_groups() == {}
    assert harness.set_lazy_sync_group("builtin:mean", "7") == "7"
    assert harness.get_lazy_sync_groups()["builtin:mean"] == "7"

    state = harness.set_lazy_sync_mode("builtin:mean", "zoom", False)
    assert state["zoom"] is False
    assert harness.get_lazy_sync_modes()["builtin:mean"]["zoom"] is False
    assert harness.view_changed.count >= 2


def test_roi_sync_state_is_stored_by_group_in_session_state() -> None:
    """ROI sharing should use controller-owned sync-group storage."""
    harness = _ControllerMutationHarness()

    harness.set_roi_state_for_sync_group(
        "3",
        {"shape": "circle", "rect": (1.0, 2.0, 30.0, 40.0)},
    )
    assert harness.roi_state_for_sync_group("3") == {
        "shape": "circle",
        "rect": (1.0, 2.0, 30.0, 40.0),
    }
    harness.set_roi_state_for_sync_group("3", None)
    assert harness.roi_state_for_sync_group("3") is None


def test_feature_flags_and_workflow_metrics_foundation() -> None:
    """Phase 0/1 rollout flags and workflow metrics should be controller-owned."""
    harness = _ControllerMutationHarness()

    assert harness.feature_enabled("annotation_provenance_schema", False) is True
    harness.set_feature_flag("baseline_workflow_metrics", True)
    harness.set_feature_flag("annotation_provenance_schema", True)

    added = harness.add_annotation(
        image_id=0,
        image_name="img0",
        t=0,
        z=0,
        y=10.0,
        x=20.0,
        label="Point",
        scope="current",
        source="assist",
        status="accepted",
        confidence=0.88,
        roi_name="roi-a",
        notes="baseline",
    )

    assert harness.feature_enabled("annotation_provenance_schema", False) is True
    assert added.status == "accepted"
    assert added.confidence == 0.88
    assert added.roi_name == "roi-a"
    assert added.notes == "baseline"

    snapshot = harness.workflow_metrics_snapshot()
    assert snapshot["annotations_added"] == 1
    assert snapshot["first_annotation_at"] is not None
    assert snapshot["annotation_count"] == 1
    assert snapshot["provenance_complete_count"] == 1


def test_assist_preferences_are_controller_owned_and_notified() -> None:
    """Assist preference toggles should persist through controller-owned setters."""
    harness = _ControllerMutationHarness()

    assert harness.feature_enabled("interactive_learning_experimental", False) is False
    harness.set_feature_flag("interactive_learning_experimental", True)
    harness.set_generation_space_value("projection")
    harness.set_disable_bulk_accept_when_stale_value(False)
    harness.set_assist_minima(min_total=42, min_positive=18, min_negative=17, min_per_context=9)

    assert harness.feature_enabled("interactive_learning_experimental", False) is True
    assert harness.session_state.generation_space == "projection"
    assert harness.session_state.disable_bulk_accept_when_stale is False
    assert harness.session_state.assist_min_total_labels == 42
    assert harness.session_state.assist_min_positive_labels == 18
    assert harness.session_state.assist_min_negative_labels == 17
    assert harness.session_state.assist_min_labels_per_context == 9
    assert harness.state_changed.count >= 4


def test_session_images_set_images_reindexes_and_resets_state(tmp_path: Path) -> None:
    """Replacing images should rebuild IDs, annotations, and active indices."""
    initial = [_ImageStub(0, tmp_path / "orig.tif", (16, 16), False, False)]
    harness = _SessionImageHarness(initial)

    replacement = [
        _ImageStub(99, tmp_path / "i0.tif", (16, 16), False, False),
        _ImageStub(100, tmp_path / "i1.tif", (16, 16), False, False),
    ]
    harness.set_images(replacement)

    assert [img.id for img in harness.session_state.images] == [0, 1]
    assert sorted(harness.session_state.annotations.keys()) == [0, 1]
    assert harness.session_state.active_primary_id == 0
    assert harness.session_state.active_support_id == 1
    assert harness.state_changed.count == 1
    assert harness.annotations_changed.count == 1


def test_session_commands_crop_and_threshold_undo_redo() -> None:
    """Session commands should support execute/undo/redo and serialization."""
    controller = SimpleNamespace(
        view_state=SimpleNamespace(crop_rect=(0.0, 0.0, 10.0, 10.0)),
        session_state=SimpleNamespace(threshold_configs_by_image={0: {"method": "Otsu"}}),
        display_mapping=DisplayMapping(0.0, 1.0),
    )

    crop_cmd = SetCropCommand(controller, image_id=0, new_crop_rect=(2.0, 2.0, 8.0, 8.0))
    assert crop_cmd.execute() is True
    assert controller.view_state.crop_rect == (2.0, 2.0, 8.0, 8.0)
    assert crop_cmd.undo() is True
    assert controller.view_state.crop_rect == (0.0, 0.0, 10.0, 10.0)
    assert crop_cmd.redo() is True
    assert controller.view_state.crop_rect == (2.0, 2.0, 8.0, 8.0)

    thr_cmd = SetThresholdCommand(controller, image_id=0, new_settings={"method": "Li"})
    assert thr_cmd.execute() is True
    assert controller.session_state.threshold_configs_by_image[0]["method"] == "Li"
    serialized = thr_cmd.to_dict()
    restored = command_from_dict(serialized, controller)
    assert restored is not None
    assert restored.undo() is True
    assert controller.session_state.threshold_configs_by_image[0]["method"] == "Otsu"
    assert restored.redo() is True
    assert controller.session_state.threshold_configs_by_image[0]["method"] == "Li"


def test_session_state_facade_exports_core_dataclasses() -> None:
    """session.state should expose core session dataclasses for compatibility."""
    assert session_state_module.SessionState is SessionState
    state = session_state_module.ViewState()
    assert isinstance(state.roi_spec, RoiSpec)
    assert state.roi_spec.shape == "circle"


def test_view_state_legacy_roi_aliases_roundtrip() -> None:
    """Legacy view-state ROI aliases should stay mapped to roi_spec."""
    state = ViewState()
    state.roi_rect = (11.0, 22.0, 33.0, 44.0)
    state.roi_shape = "box"
    assert state.roi_spec.rect == (11.0, 22.0, 33.0, 44.0)
    assert state.roi_spec.shape == "box"
    # Legacy accessor used by project/session adapters.
    assert state.roi.x == 11.0
    assert state.roi.y == 22.0
    assert state.roi.w == 33.0
    assert state.roi.h == 44.0


def test_display_mapping_legacy_aliases_roundtrip() -> None:
    """Legacy mapping aliases (vmin/vmax/lut_name) should remain stable."""
    mapping = DisplayMapping(0.1, 0.9, lut=3)
    mapping.vmin = 0.2
    mapping.vmax = 0.8
    assert mapping.min_val == 0.2
    assert mapping.max_val == 0.8
    assert mapping.vmin == 0.2
    assert mapping.vmax == 0.8
    assert mapping.lut_name == "3"


def test_mapping_from_dict_accepts_legacy_minmax_keys() -> None:
    """Deserializer should accept old vmin/vmax and min/max keys."""
    m1 = mapping_from_dict({"vmin": 5.0, "vmax": 7.0}, DisplayMapping(0.0, 1.0))
    assert m1.min_val == 5.0
    assert m1.max_val == 7.0
    m2 = mapping_from_dict({"min": 2.5, "max": 9.5}, DisplayMapping(0.0, 1.0))
    assert m2.min_val == 2.5
    assert m2.max_val == 9.5


def test_session_view_mixin_basic_state_mutations() -> None:
    """SessionViewMixin should update view/display fields consistently."""
    harness = _SessionViewHarness()

    harness.set_t(2)
    harness.set_z(3)
    assert harness.view_state.t == 2
    assert harness.view_state.z == 3
    assert harness.view_changed.count >= 2

    harness.set_roi_box(10.0, 20.0, 30.0, 40.0)
    assert harness.view_state.roi_spec.shape == "box"
    assert harness.view_state.roi_spec.rect == (10.0, 20.0, 30.0, 40.0)
    harness.clear_roi()
    assert harness.view_state.roi_spec.shape == "none"

    harness.set_display_mapping(0.2, 0.8, gamma=1.1)
    harness.set_lut(4)
    harness.set_invert(True)
    harness.set_gamma(0.9)

    mapping = harness.display_mapping.mapping_for(0, "frame")
    assert mapping.min_val == 0.2
    assert mapping.max_val == 0.8
    assert mapping.lut == 4
    assert mapping.invert is True
    assert mapping.gamma == 0.9
    assert harness.display_changed.count >= 1


def test_execute_view_command_crop_emits_view_changed_not_state_changed() -> None:
    """Crop commands should publish typed view updates instead of generic state only."""
    harness = _SessionViewHarness()

    ok = harness.execute_view_command(
        SetCropCommand(harness, image_id=0, new_crop_rect=(2.0, 2.0, 8.0, 8.0))
    )

    assert ok is True
    assert harness.view_state.crop_rect == (2.0, 2.0, 8.0, 8.0)
    assert harness.view_changed.count == 1
    assert harness.state_changed.count == 0

    assert harness.undo_view_command() is True
    assert harness.view_state.crop_rect is None
    assert harness.view_changed.count == 2
    assert harness.redo_view_command() is True
    assert harness.view_state.crop_rect == (2.0, 2.0, 8.0, 8.0)
    assert harness.view_changed.count == 3


def test_execute_view_command_display_mapping_emits_display_changed() -> None:
    """Display-mapping commands should publish typed display updates."""
    harness = _SessionViewHarness()

    ok = harness.execute_view_command(
        SetDisplayMappingCommand(
            harness,
            image_id=0,
            panel="frame",
            new_vmin=0.25,
            new_vmax=0.75,
            new_gamma=1.2,
        )
    )

    mapping = harness.display_mapping.mapping_for(0, "frame")
    assert ok is True
    assert mapping.min_val == 0.25
    assert mapping.max_val == 0.75
    assert mapping.gamma == 1.2
    assert harness.display_changed.count == 1
    assert harness.state_changed.count == 0


def test_execute_view_command_navigation_does_not_duplicate_notifications(tmp_path: Path) -> None:
    """Navigation commands already emit through controller setters and should not double-fire."""
    image = _ImageStub(0, tmp_path / "nav.tif", (5, 1, 16, 16), True, True)
    harness = _SessionImageViewHarness([image])

    ok = harness.execute_view_command(JumpToFrameCommand(harness, image_id=0, target_t=3))

    assert ok is True
    assert harness.view_state.t == 3
    assert harness.view_changed.count == 1
    assert harness.state_changed.count == 0


def test_session_controller_threshold_settings_store_and_emit() -> None:
    """Threshold config commits should update both stores and publish state."""
    controller = _ControllerMutationHarness()

    controller.set_threshold_preview_settings(0, {"method": "Li", "value": 0.42})
    controller.store_threshold_mask(0, {"path": "mask.npy", "threshold": 0.42})
    controller.set_particles_config(0, {"min_area": 5, "max_area": 15})

    assert controller.session_state.threshold_settings["method"] == "Li"
    assert controller.session_state.threshold_configs_by_image[0]["value"] == 0.42
    assert controller.session_state.threshold_masks[0]["path"] == "mask.npy"
    assert controller.session_state.particles_configs_by_image[0]["min_area"] == 5
    assert controller.state_changed.count == 3


def test_session_controller_suggestion_decision_flow_updates_annotations() -> None:
    """Suggestion state transitions should keep pending/history/annotations aligned."""
    controller = _ControllerMutationHarness()

    lower = PointSuggestion(0, "image0.tif", 0, 0, 10.0, 12.0, 0.3, suggestion_id="low")
    higher = PointSuggestion(0, "image0.tif", 0, 0, 20.0, 24.0, 0.9, suggestion_id="high")
    controller.append_generated_suggestions(0, [lower, higher])

    pending = controller.session_state.suggestions[0]
    history = controller.session_state.suggestion_history[0]
    assert [item.suggestion_id for item in pending] == ["high", "low"]
    assert len(history) == 2

    assert controller.update_suggestion_decision(0, "high", "accepted") is True
    accepted = next(
        item for item in controller.session_state.suggestion_history[0] if item.suggestion_id == "high"
    )
    assert accepted.status == "accepted"
    assert len(controller.session_state.annotations[0]) == 1
    accepted_ids = {
        ann.meta.get("suggestion_id") for ann in controller.session_state.annotations[0]
    }
    assert "high" in accepted_ids

    assert controller.update_suggestion_decision(0, "high", "proposed") is True
    assert len(controller.session_state.annotations[0]) == 0
    reproposed = next(
        item for item in controller.session_state.suggestions[0] if item.suggestion_id == "high"
    )
    assert reproposed.status == "proposed"

    assert controller.update_suggestion_decision(0, "high", "rejected") is True
    rejected = next(
        item for item in controller.session_state.suggestion_history[0] if item.suggestion_id == "high"
    )
    assert rejected.status == "rejected"
    assert len(controller.session_state.annotations[0]) == 0
    assert controller.annotations_changed.count >= 3


def test_session_controller_can_resort_pending_suggestions() -> None:
    """Pending suggestion order should be controller-owned, not UI-owned."""
    controller = _ControllerMutationHarness()
    controller.session_state.suggestions[0] = [
        PointSuggestion(0, "image0.tif", 0, 0, 1.0, 1.0, 0.1, suggestion_id="low"),
        PointSuggestion(0, "image0.tif", 0, 0, 2.0, 2.0, 0.8, suggestion_id="high"),
        PointSuggestion(0, "image0.tif", 0, 0, 3.0, 3.0, 0.5, suggestion_id="mid"),
    ]

    controller.sort_pending_suggestions(0)

    assert [row.suggestion_id for row in controller.session_state.suggestions[0]] == [
        "high",
        "mid",
        "low",
    ]
    assert controller.state_changed.count == 1


def test_session_controller_returns_suggestion_decision_context() -> None:
    """Suggestion lookup details should be computed inside the controller boundary."""
    controller = _ControllerMutationHarness()
    proposed = PointSuggestion(0, "image0.tif", 0, 0, 5.0, 6.0, 0.7, suggestion_id="pending")
    accepted = PointSuggestion(0, "image0.tif", 0, 0, 7.0, 8.0, 0.8, suggestion_id="history")
    accepted.status = "accepted"
    controller.session_state.suggestions[0] = [proposed]
    controller.session_state.suggestion_history[0] = [accepted]

    pending_ctx = controller.get_suggestion_decision_context(0, "pending")
    history_ctx = controller.get_suggestion_decision_context(0, "history")
    missing_ctx = controller.get_suggestion_decision_context(0, "missing")

    assert pending_ctx["pending_item"] is proposed
    assert pending_ctx["history_item"] is None
    assert pending_ctx["status"] == "proposed"
    assert history_ctx["pending_item"] is None
    assert history_ctx["history_item"] is accepted
    assert history_ctx["status"] == "accepted"
    assert missing_ctx["suggestion"] is None
    assert missing_ctx["status"] == ""


def test_session_controller_slice_suggestion_queries_filter_and_merge() -> None:
    """Slice-level suggestion queries should be controller-owned and deterministic."""
    controller = _ControllerMutationHarness()
    pending_visible = PointSuggestion(0, "image0.tif", 1, 2, 5.0, 6.0, 0.7, suggestion_id="pending")
    pending_hidden = PointSuggestion(0, "image0.tif", 9, 9, 7.0, 8.0, 0.9, suggestion_id="other")
    history_visible = PointSuggestion(0, "image0.tif", 1, 2, 9.0, 10.0, 0.4, suggestion_id="history")
    duplicate_history = PointSuggestion(0, "image0.tif", 1, 2, 11.0, 12.0, 0.3, suggestion_id="pending")
    controller.session_state.suggestions[0] = [pending_visible, pending_hidden]
    controller.session_state.suggestion_history[0] = [history_visible, duplicate_history]

    visible = controller.get_visible_suggestions(0, t_index=1, z_index=2, min_score=0.5)
    merged = controller.get_slice_suggestions(0, t_index=1, z_index=2)

    assert visible == [pending_visible]
    assert merged == [pending_visible, history_visible]


def test_state_proxies_return_read_only_snapshots() -> None:
    """GUI state proxies should not expose mutable live controller-owned containers."""
    harness = _StateProxyHarness()
    harness.controller.session_state.annotations[0] = [Keypoint(0, "img.tif", 0, 0, 1.0, 2.0, "Point")]
    harness.controller.session_state.suggestions[0] = [
        PointSuggestion(0, "img.tif", 0, 0, 1.0, 2.0, 0.9, suggestion_id="s1")
    ]

    annotations_view = harness.annotations
    suggestions_view = harness.suggestions

    assert isinstance(annotations_view[0], tuple)
    assert isinstance(suggestions_view[0], tuple)

    try:
        annotations_view[0].append("bad")  # type: ignore[attr-defined]
        assert False, "annotation snapshot should be immutable"
    except AttributeError:
        pass

    try:
        suggestions_view[0] = ()  # type: ignore[index]
        assert False, "suggestion snapshot mapping should be immutable"
    except TypeError:
        pass


def test_session_controller_suggestion_retrain_config_emits_state() -> None:
    """Retrain-config persistence should remain controller-owned."""
    controller = _ControllerMutationHarness()

    controller.set_suggestion_retrain_config(enabled=False, min_labels=13)

    assert controller.session_state.suggestion_auto_retrain_enabled is False
    assert controller.session_state.suggestion_auto_retrain_min_labels == 13
    assert controller.state_changed.count == 1


def test_session_controller_channel_display_settings_marks_dirty_and_emits() -> None:
    """Channel-display persistence should flow through controller ownership."""
    controller = _ControllerMutationHarness()

    controller.set_channel_display_settings_value({"channels": [{"name": "DNA", "visible": True}]})

    assert controller.session_state.channel_display_settings == {
        "channels": [{"name": "DNA", "visible": True}]
    }
    assert controller.session_state.dirty is True
    assert controller.display_changed.count == 1


def test_session_controller_current_user_updates_emit_state() -> None:
    """Current-user changes should remain a controller-owned state update."""
    controller = _ControllerMutationHarness()

    controller.set_current_user_value("reviewer_01")

    assert controller.session_state.current_user == "reviewer_01"
    assert controller.state_changed.count == 1


def test_update_metadata_command_emits_annotation_change() -> None:
    """Metadata commands should publish through the annotation channel."""
    controller = _ControllerMutationHarness()
    ann = Keypoint(0, "image0.tif", 0, 0, 5.0, 6.0, meta={"comment": "old"})
    controller.session_state.annotations[0] = [ann]

    cmd = UpdateMetadataCommand(
        controller,
        image_id=0,
        annotation_id=ann.annotation_id,
        field_name="comment",
        new_value="new",
    )

    assert cmd.execute() is True
    assert ann.meta["comment"] == "new"
    assert controller.session_state.dirty is True
    assert controller.annotations_changed.count == 1

    assert cmd.undo() is True
    assert ann.meta["comment"] == "old"
    assert controller.annotations_changed.count == 2


def test_batch_assign_label_command_emits_per_image_annotation_updates() -> None:
    """Batch QC label assignment should use centralized annotation notifications."""
    controller = _ControllerMutationHarness()
    ann0 = Keypoint(0, "image0.tif", 0, 0, 5.0, 6.0, label="")
    ann1 = Keypoint(1, "image1.tif", 0, 0, 7.0, 8.0, label="")
    controller.session_state.annotations = {0: [ann0], 1: [ann1]}

    issues = [
        SimpleNamespace(
            issue_type="missing_label",
            image_id=0,
            affected_annotation_ids=[ann0.annotation_id],
        ),
        SimpleNamespace(
            issue_type="missing_label",
            image_id=1,
            affected_annotation_ids=[ann1.annotation_id],
        ),
    ]

    cmd = BatchAssignLabelCommand(controller, issues, default_label="phage")

    assert cmd.execute() is True
    assert ann0.label == "phage"
    assert ann1.label == "phage"
    assert controller.session_state.dirty is True
    assert controller.annotations_changed.count == 2

    assert cmd.undo() is True
    assert ann0.label == ""
    assert ann1.label == ""
    assert controller.annotations_changed.count == 4


def test_session_controller_metadata_command_helpers_execute_on_stack() -> None:
    """Controller wrappers should integrate metadata commands into public APIs."""
    controller = _ControllerMutationHarness()
    ann = Keypoint(0, "image0.tif", 0, 0, 5.0, 6.0, label="old", meta={"comment": "old"})
    controller.session_state.annotations[0] = [ann]

    assert controller.update_annotation_metadata(0, ann.annotation_id, "comment", "new") is True
    assert controller.update_annotation_label(0, ann.annotation_id, "new-label") is True

    assert controller.session_state.annotations[0][0].meta["comment"] == "new"
    assert controller.session_state.annotations[0][0].label == "new-label"
    assert controller.can_undo() is True


def test_session_controller_batch_command_helpers_execute_on_stack() -> None:
    """Batch command wrappers should keep batch commands integrated, not orphaned."""
    controller = _ControllerMutationHarness()
    ann = Keypoint(0, "image0.tif", 0, 0, 5.0, 6.0, label="")
    controller.session_state.annotations[0] = [ann]
    controller.session_state.qc_issues = [
        SimpleNamespace(
            issue_type="missing_label",
            image_id=0,
            affected_annotation_ids=[ann.annotation_id],
        )
    ]

    assert controller.batch_assign_missing_labels(default_label="phage", image_ids=[0]) is True
    assert controller.session_state.annotations[0][0].label == "phage"
    assert controller.can_undo() is True


def test_session_controller_exposes_reusable_qc_and_calibration_helpers() -> None:
    """Reusable review helpers should live behind the controller boundary."""
    controller = _ControllerMutationHarness()
    accepted = PointSuggestion(0, "image0.tif", 0, 0, 1.0, 1.0, 0.9, suggestion_id="a")
    accepted.status = "accepted"
    accepted.meta["confidence_available"] = True
    accepted.meta["p_accept"] = 0.8
    rejected = PointSuggestion(0, "image0.tif", 0, 0, 2.0, 2.0, 0.3, suggestion_id="b")
    rejected.status = "rejected"
    rejected.meta["confidence_available"] = True
    rejected.meta["p_accept"] = 0.2
    controller.session_state.suggestion_history[0] = [accepted, rejected]
    controller.session_state.qc_issues = [
        SimpleNamespace(issue_type="missing_label", image_id=0, affected_annotation_ids=[]),
        SimpleNamespace(issue_type="duplicate", image_id=1, affected_annotation_ids=[]),
    ]

    assert controller.get_qc_issues(issue_type="missing_label", image_ids=[0]) == [
        controller.session_state.qc_issues[0]
    ]
    assert controller.get_suggestion_calibration_samples() == [(0.8, 1), (0.2, 0)]
