"""Split chunk from test_session_components_split2.py."""


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


from tests.unit.session.test_session_components_split1 import _ImageStub, _SessionImageHarness, _ControllerMutationHarness

class _StateProxyHarness(StateMixin):
    """Harness for verifying GUI state proxies are read-only snapshots."""

    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
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
