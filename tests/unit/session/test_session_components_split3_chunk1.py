"""Split chunk from test_session_components_split3.py."""


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


from tests.unit.session.test_session_components_split1 import _ImageStub, _SessionViewHarness, _SessionImageViewHarness, _ControllerMutationHarness
from tests.unit.session.test_session_components_split2 import _StateProxyHarness

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
