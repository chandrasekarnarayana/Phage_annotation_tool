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
