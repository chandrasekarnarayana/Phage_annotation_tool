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


from tests.unit.session.test_session_components_split1 import _ControllerMutationHarness

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
