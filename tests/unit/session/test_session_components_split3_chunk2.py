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
