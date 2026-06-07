"""Split definitions from test_assisted_annotation_workflow.py."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.core.session_state import ViewState
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.annotations import SessionAnnotationsMixin
from phage_annotator.session.controller_suggestions import SessionControllerSuggestionsMixin
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.session.view import SessionViewMixin
from phage_annotator.ui_qt.actions import assist_generation, assist_review, standard


class _Emitter:
    def emit(self) -> None:
        """Emit emit for the current workflow."""
        return None

class _Harness(SessionViewMixin, SessionAnnotationsMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self._undo_stack = []
        self._redo_stack = []
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.session_state = SimpleNamespace(
            annotations={0: []},
            suggestions={0: []},
            suggestion_history={0: []},
            current_user="tester",
            suggestion_metrics={
                "generated": 0.0,
                "accepted": 0.0,
                "rejected": 0.0,
                "mean_correction_distance": 0.0,
            },
            audit_log=[],
            dirty=False,
            annotations_loaded={0: True},
        )
        self.view_state = ViewState(t=0, z=0)
        self.display_mapping = DisplayMapping(0.0, 1.0)

    def set_dirty(self, dirty: bool = True) -> None:
        """Set dirty for the current workflow."""
        self.session_state.dirty = dirty

    def append_audit_event(self, event_type: str, **details: object) -> None:
        """Append audit event for the current workflow."""
        self.session_state.audit_log.append({"event_type": event_type, "details": details})

    def update_suggestion_metrics(self, **kwargs) -> None:
        """Update suggestion metrics for the current workflow."""
        self.session_state.suggestion_metrics["generated"] += kwargs.get("generated", 0)
        self.session_state.suggestion_metrics["accepted"] += kwargs.get("accepted", 0)
        self.session_state.suggestion_metrics["rejected"] += kwargs.get("rejected", 0)

class _ControllerHarness(SessionControllerSuggestionsMixin):
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.session_state = SimpleNamespace(
            annotations={0: []},
            suggestions={0: []},
            suggestion_history={0: []},
            suggestion_metrics={
                "generated": 0.0,
                "accepted": 0.0,
                "rejected": 0.0,
                "mean_correction_distance": 0.0,
                "classified_new": 0.0,
                "classified_near_existing": 0.0,
                "classified_conflict": 0.0,
                "classified_duplicate": 0.0,
            },
            last_suggestion_generation_summary={},
            last_local_suggestion_update_summary={},
            dirty=False,
            annotations_loaded={0: True},
            annotation_space="stack",
            assist_local_update_radius_px=24.0,
            assist_local_rescore_radius_px=48.0,
            assist_local_rescore_debounce_ms=700,
            assist_local_rescore_edit_threshold=4,
            suggestion_auto_retrain_enabled=True,
            suggestion_auto_retrain_min_labels=25,
            suggestion_training_pending=0,
            suggestion_training_samples=[],
            suggestion_context_stats={},
            assist_min_total_labels=30,
            assist_min_positive_labels=15,
            assist_min_negative_labels=15,
            assist_min_labels_per_context=10,
        )
        self.view_state = ViewState(t=0, z=0, crop_rect=(0.0, 0.0, 64.0, 64.0))
        self._workflow_events = []
        self._local_rescore_edit_count = 0
        self._pending_local_rescore_context = None
        self.suggestion_ranker = SimpleNamespace(trained_samples=0)
        ranker = SimpleNamespace(
            trained_samples=0,
            apply_to_suggestions=lambda rows: rows,
            fit=lambda *args, **kwargs: None,
            to_dict=lambda: {},
        )
        self.suggestion_rankers_by_space = {"stack": ranker, "projection": ranker}

    def set_dirty(self, dirty: bool = True) -> None:
        """Set dirty for the current workflow."""
        self.session_state.dirty = bool(dirty)

    def record_workflow_event(self, kind: str, **details) -> None:
        """Record workflow event for the current workflow."""
        self._workflow_events.append((str(kind), dict(details)))

    def save_suggestion_ranker_state(self) -> None:
        """Save suggestion ranker state for the current workflow."""
        self.session_state.suggestion_ranker_state = {}

def test_local_peak_model_generates_candidates() -> None:
    """Verify local peak model generates candidates for the current workflow."""
    image = np.zeros((24, 24), dtype=np.float32)
    image[10, 10] = 20.0
    image[16, 18] = 18.0
    model = LocalPeakSuggestionModel(min_distance_px=2, max_points=10, threshold_quantile=0.5)
    results = model.predict(
        image,
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        label="phage",
    )
    assert isinstance(results, list)
    assert all(0.0 <= s.score <= 1.0 for s in results)
    assert results == sorted(results, key=lambda s: s.score, reverse=True)
    assert all("peak" in s.score_components for s in results)
    assert all(isinstance(s.density_context, dict) for s in results)
    assert all(hasattr(s, "uncertainty_score") for s in results)

def test_local_peak_model_keeps_dense_valid_candidates_without_max_point_truncation() -> None:
    """Verify local peak model keeps dense valid candidates without max point truncation for the current workflow."""
    rng = np.random.default_rng(7)
    image = (rng.random((48, 48), dtype=np.float32) * 2.0).astype(np.float32)
    coords = [(8, 8), (8, 20), (8, 32), (20, 8), (20, 20), (20, 32), (32, 8), (32, 20)]
    for y, x in coords:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                yy = y + dy
                xx = x + dx
                if 0 <= yy < image.shape[0] and 0 <= xx < image.shape[1]:
                    dist = np.sqrt(float(dy * dy + dx * dx))
                    image[yy, xx] = max(image[yy, xx], 120.0 * np.exp(-(dist ** 2) / 2.0))
    model = LocalPeakSuggestionModel(min_distance_px=2, max_points=2, threshold_quantile=0.9)

    results = model.predict(
        image,
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        label="phage",
    )

    assert len(results) >= len(coords)
    assert all("local_density" in s.score_components for s in results)

def test_accept_reject_and_clear_suggestion_commands_roundtrip() -> None:
    """Verify accept reject and clear suggestion commands roundtrip for the current workflow."""
    harness = _Harness()
    suggestion = PointSuggestion(
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        y=5.0,
        x=7.0,
        score=0.9,
    )
    harness.session_state.suggestions[0].append(suggestion)

    accept = AcceptSuggestionCommand(harness, 0, suggestion.suggestion_id)
    assert harness.execute_view_command(accept)
    assert len(harness.session_state.annotations[0]) == 1
    assert len(harness.session_state.suggestions[0]) == 0

    assert harness.undo()
    assert len(harness.session_state.annotations[0]) == 0
    assert len(harness.session_state.suggestions[0]) == 1

    assert harness.redo()
    assert len(harness.session_state.annotations[0]) == 1

    # add one more suggestion then reject/clear
    extra = PointSuggestion(
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        y=8.0,
        x=9.0,
        score=0.5,
    )
    harness.session_state.suggestions[0].append(extra)

    reject = RejectSuggestionCommand(harness, 0, extra.suggestion_id)
    assert harness.execute_view_command(reject)
    assert all(s.suggestion_id != extra.suggestion_id for s in harness.session_state.suggestions[0])

    remaining = PointSuggestion(
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        y=2.0,
        x=3.0,
        score=0.4,
    )
    harness.session_state.suggestions[0].append(remaining)

    clear = ClearSuggestionsCommand(harness, 0)
    assert harness.execute_view_command(clear)
    assert harness.session_state.suggestions[0] == []

def test_generated_suggestions_are_classified_against_existing_truth() -> None:
    """Verify generated suggestions are classified against existing truth for the current workflow."""
    controller = _ControllerHarness()
    controller.session_state.annotations[0] = [
        Keypoint(0, "img", 0, 0, 10.0, 10.0, label="phage", source="manual"),
        Keypoint(0, "img", 0, 0, 30.0, 30.0, label="debris", source="manual"),
    ]
    rows = [
        PointSuggestion(0, "img", 0, 0, 10.1, 10.2, 0.95, label="phage"),
        PointSuggestion(0, "img", 0, 0, 31.0, 30.0, 0.80, label="phage"),
        PointSuggestion(0, "img", 0, 0, 15.0, 15.0, 0.70, label="phage"),
    ]

    summary = controller.append_generated_suggestions(0, rows, sort_pending=True)

    assert summary["duplicate_count"] == 1
    assert summary["conflict_count"] == 1
    assert summary["new_count"] == 1
    assert summary["queued_count"] == 2
    assert len(controller.session_state.suggestions[0]) == 2
    assert controller.session_state.suggestion_history[0][0].status == "duplicate"
    queued_classes = {
        str(dict(getattr(s, "meta", {}) or {}).get("candidate_class", ""))
        for s in controller.session_state.suggestions[0]
    }
    assert "conflict" in queued_classes
    assert "new" in queued_classes
    assert all("uncertainty_reason" in s.meta for s in controller.session_state.suggestions[0])
    assert controller.session_state.last_suggestion_generation_summary["duplicate_count"] == 1
    assert controller.session_state.suggestion_metrics["classified_duplicate"] == 1.0
    assert controller.session_state.suggestion_metrics["classified_conflict"] == 1.0

def test_classification_tracks_strict_truth_and_any_annotation_distances() -> None:
    """Verify classification tracks strict truth and any annotation distances for the current workflow."""
    controller = _ControllerHarness()
    controller.session_state.annotations[0] = [
        Keypoint(0, "img", 0, 0, 10.0, 10.0, label="phage", source="manual"),
        Keypoint(0, "img", 0, 0, 12.0, 10.0, label="noise", source="suggestion"),
    ]
    row = PointSuggestion(0, "img", 0, 0, 11.0, 10.0, 0.7, label="phage")

    controller._classify_generated_suggestion(0, row)

    meta = dict(getattr(row, "meta", {}) or {})
    assert float(meta["distance_to_nearest_truth_strict"]) == 1.0
    assert float(meta["distance_to_any_annotation"]) == 1.0
