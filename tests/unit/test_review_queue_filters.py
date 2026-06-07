"""Unit tests for review queue filtering in annotation table pipeline."""

from __future__ import annotations

from types import SimpleNamespace

from phage_annotator.core.annotation import Keypoint
from phage_annotator.ui_qt.utils.table_status import TableStatusMixin


class _Check:
    def __init__(self, checked: bool):
        """Initialize the object and prepare its runtime state."""
        self._checked = checked

    def isChecked(self) -> bool:
        """Run the isChecked workflow."""
        return self._checked


class _Harness(TableStatusMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.primary_image = SimpleNamespace(id=0)
        self.annotations = {
            0: [
                Keypoint(0, "img", 0, 0, 1.0, 1.0, annotation_id="a1", meta={"assignee": "alice", "review_state": "new"}),
                Keypoint(0, "img", 0, 0, 2.0, 2.0, annotation_id="a2", meta={"assignee": "bob", "review_state": "approved"}),
                Keypoint(0, "img", 0, 0, 3.0, 3.0, annotation_id="a3", meta={"assignee": "alice", "review_state": "needs_changes"}),
            ]
        }
        self.filter_current_chk = _Check(False)
        self.t_slider = SimpleNamespace(value=lambda: 0)
        self.z_slider = SimpleNamespace(value=lambda: 0)
        self.controller = SimpleNamespace(session_state=SimpleNamespace(current_user="alice"))
        self._filter_by_modality = False
        self._review_queue_filter = "all"
        self.qc_state = SimpleNamespace(get_affected_annotation_ids=lambda respect_filters=False: {"a3"})


def test_review_queue_filters_apply_expected_subset() -> None:
    """Verify review queue filters apply expected subset for the current workflow."""
    h = _Harness()

    h._review_queue_filter = "all"
    assert {kp.annotation_id for kp in h._current_keypoints()} == {"a1", "a2", "a3"}

    h._review_queue_filter = "my_queue"
    assert {kp.annotation_id for kp in h._current_keypoints()} == {"a1", "a3"}

    h._review_queue_filter = "needs_review"
    assert {kp.annotation_id for kp in h._current_keypoints()} == {"a1", "a3"}

    h._review_queue_filter = "blocked_qc"
    assert {kp.annotation_id for kp in h._current_keypoints()} == {"a3"}
