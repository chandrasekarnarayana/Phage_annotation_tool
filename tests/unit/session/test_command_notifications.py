"""Regression tests for typed command notifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from phage_annotator.analysis.qc_validators import IssueSeverity, QCIssue
from phage_annotator.annotation.core import Keypoint
from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.core.session_state import SessionState, ViewState
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.batch_commands import BatchAssignLabelCommand
from phage_annotator.session.commands import TransactionCommand
from phage_annotator.session.metadata_commands import UpdateMetadataCommand
from phage_annotator.session.suggestion_commands import AcceptSuggestionCommand
from phage_annotator.session.view import SessionViewMixin


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
    metadata_summary: dict = field(default_factory=dict)
    pixel_size_um: float = 0.0
    ome_axes: Optional[str] = None
    axis_auto_used: bool = False
    axis_auto_mode: Optional[str] = None


class _CommandHarness(SessionViewMixin):
    """Minimal controller-like harness for exercising command notifications."""

    def __init__(self, tmp_path: Path) -> None:
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.roi_changed = _Emitter()
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.view_state = ViewState()
        self.display_mapping = DisplayMapping(0.0, 1.0)
        self.session_state = SessionState(
            project_path=None,
            project_save_time=None,
            dirty=False,
            last_folder=None,
            recent_images=[],
            active_primary_id=0,
            active_support_id=0,
            images=[_ImageStub(0, tmp_path / "img.tif", (1, 16, 16), False, False)],
            image_states={},
            annotations={0: []},
            labels=["Point"],
            current_label="Point",
            annotations_loaded={0: False},
            suggestions={0: []},
            suggestion_history={0: []},
        )

    def get_annotations(self, image_id: int):
        return self.session_state.annotations.setdefault(int(image_id), [])

    def append_audit_event(self, *_args, **_kwargs) -> None:
        return None


def test_metadata_command_execute_undo_redo_emit_annotations_only(tmp_path: Path) -> None:
    """Metadata commands should emit annotation notifications through the command stack."""
    harness = _CommandHarness(tmp_path)
    keypoint = Keypoint(0, "img.tif", 0, 0, 10.0, 12.0, "Point", meta={"score": 1})
    harness.session_state.annotations[0] = [keypoint]

    command = UpdateMetadataCommand(harness, 0, keypoint.annotation_id, "score", 7)

    assert harness.execute_view_command(command)
    assert keypoint.meta["score"] == 7
    assert harness.annotations_changed.count == 1
    assert harness.state_changed.count == 0
    assert harness.view_changed.count == 0
    assert harness.display_changed.count == 0

    assert command.undo() is True
    assert keypoint.meta["score"] == 1
    assert harness.annotations_changed.count == 2

    assert command.redo() is True
    assert keypoint.meta["score"] == 7
    assert harness.annotations_changed.count == 3


def test_batch_command_execute_undo_redo_emit_annotations_only(tmp_path: Path) -> None:
    """Batch annotation commands should stay on the typed annotation notification path."""
    harness = _CommandHarness(tmp_path)
    keypoint = Keypoint(0, "img.tif", 0, 0, 10.0, 12.0, "", meta={})
    harness.session_state.annotations[0] = [keypoint]
    issues = [
        QCIssue(
            issue_id="missing-1",
            severity=IssueSeverity.WARNING,
            issue_type="missing_label",
            message="missing label",
            image_id=0,
            affected_annotation_ids=[keypoint.annotation_id],
        )
    ]

    command = BatchAssignLabelCommand(harness, issues, "Point")

    assert harness.execute_view_command(command)
    assert keypoint.label == "Point"
    assert harness.annotations_changed.count == 1
    assert harness.state_changed.count == 0
    assert harness.view_changed.count == 0
    assert harness.display_changed.count == 0

    assert command.undo() is True
    assert keypoint.label == ""
    assert harness.annotations_changed.count == 2

    assert command.redo() is True
    assert keypoint.label == "Point"
    assert harness.annotations_changed.count == 3


def test_suggestion_command_execute_undo_redo_emit_annotations_only(tmp_path: Path) -> None:
    """Suggestion commands should publish typed annotation notifications only."""
    harness = _CommandHarness(tmp_path)
    suggestion = PointSuggestion(
        0,
        "img.tif",
        0,
        0,
        10.0,
        11.0,
        0.95,
        suggestion_id="s-1",
    )
    harness.session_state.suggestions[0] = [suggestion]

    command = AcceptSuggestionCommand(harness, 0, "s-1")

    assert harness.execute_view_command(command)
    assert len(harness.session_state.annotations[0]) == 1
    assert harness.annotations_changed.count == 1
    assert harness.state_changed.count == 0
    assert harness.view_changed.count == 0
    assert harness.display_changed.count == 0

    assert command.undo() is True
    assert not harness.session_state.annotations[0]
    assert harness.annotations_changed.count == 2

    assert command.redo() is True
    assert len(harness.session_state.annotations[0]) == 1
    assert harness.annotations_changed.count == 3


def test_transaction_command_coalesces_annotation_notifications(tmp_path: Path) -> None:
    """Transaction-wrapped annotation commands should flush one annotation signal per phase."""
    harness = _CommandHarness(tmp_path)
    first = Keypoint(0, "img.tif", 0, 0, 10.0, 12.0, "Point", meta={"score": 1})
    second = Keypoint(0, "img.tif", 0, 0, 14.0, 16.0, "Point", meta={"score": 2})
    harness.session_state.annotations[0] = [first, second]

    transaction = TransactionCommand(harness, image_id=0, transaction_name="Bulk metadata update")
    transaction.add_command(UpdateMetadataCommand(harness, 0, first.annotation_id, "score", 10))
    transaction.add_command(UpdateMetadataCommand(harness, 0, second.annotation_id, "score", 20))

    assert harness.execute_view_command(transaction) is True
    assert first.meta["score"] == 10
    assert second.meta["score"] == 20
    assert harness.annotations_changed.count == 1
    assert harness.state_changed.count == 0

    assert transaction.undo() is True
    assert first.meta["score"] == 1
    assert second.meta["score"] == 2
    assert harness.annotations_changed.count == 2

    assert transaction.redo() is True
    assert first.meta["score"] == 10
    assert second.meta["score"] == 20
    assert harness.annotations_changed.count == 3
