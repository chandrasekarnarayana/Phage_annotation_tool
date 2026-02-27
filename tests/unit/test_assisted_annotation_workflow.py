"""Unit tests for assisted annotation suggestions and commands."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.core.session_state import ViewState
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.annotations import SessionAnnotationsMixin
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.session.view import SessionViewMixin


class _Emitter:
    def emit(self) -> None:
        return None


class _Harness(SessionViewMixin, SessionAnnotationsMixin):
    def __init__(self) -> None:
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
        self.session_state.dirty = dirty

    def append_audit_event(self, event_type: str, **details: object) -> None:
        self.session_state.audit_log.append({"event_type": event_type, "details": details})

    def update_suggestion_metrics(self, **kwargs) -> None:
        self.session_state.suggestion_metrics["generated"] += kwargs.get("generated", 0)
        self.session_state.suggestion_metrics["accepted"] += kwargs.get("accepted", 0)
        self.session_state.suggestion_metrics["rejected"] += kwargs.get("rejected", 0)



def test_local_peak_model_generates_candidates() -> None:
    image = np.zeros((24, 24), dtype=np.float32)
    image[10, 10] = 20.0
    image[16, 18] = 18.0
    model = LocalPeakSuggestionModel(min_distance_px=2, max_points=10, threshold_quantile=0.9)
    results = model.predict(
        image,
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        label="phage",
    )
    assert len(results) >= 2
    assert all(0.0 <= s.score <= 1.0 for s in results)
    assert results == sorted(results, key=lambda s: s.score, reverse=True)
    assert all("peak" in s.score_components for s in results)


def test_accept_reject_and_clear_suggestion_commands_roundtrip() -> None:
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
