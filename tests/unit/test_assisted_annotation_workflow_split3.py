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


def test_accept_in_roi_feeds_interactive_learning_when_enabled(monkeypatch) -> None:
    """Verify accept in roi feeds interactive learning when enabled for the current workflow."""
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.9, suggestion_id="roi-ml")
    added: list[str] = []

    class _FakeCmd:
        def __init__(self, _controller, _image_id, suggestion_id):
            """Initialize the object and prepare its runtime state."""
            self.suggestion_id = suggestion_id

    monkeypatch.setattr(assist_generation, "AcceptSuggestionCommand", _FakeCmd)
    owner = SimpleNamespace(
        _ensure_annotation_write_context_confirmed=lambda _label: True,
        _visible_suggestions=lambda: [suggestion],
        _point_in_roi=lambda _x, _y: True,
        _ensure_suggestion_accept_allowed=lambda *_args, **_kwargs: True,
        _interactive_learning_enabled=lambda: True,
        _interactive_learning_model=SimpleNamespace(
            add_example=lambda row, accepted=True: added.append(
                f"{row.suggestion_id}:{accepted}"
            )
        ),
        controller=SimpleNamespace(
            execute_view_command=lambda _cmd: True,
            update_suggestion_metrics=lambda **_kwargs: None,
            can_undo=lambda: False,
            can_redo=lambda: False,
            append_audit_event=lambda *args, **kwargs: None,
        ),
        primary_image=SimpleNamespace(id=0),
        undo_act=SimpleNamespace(setEnabled=lambda _value: None),
        redo_act=SimpleNamespace(setEnabled=lambda _value: None),
        _note_annotation_edit=lambda _image_id: None,
        _refresh_table=lambda: None,
        _request_ui_refresh=lambda *args, **kwargs: None,
        _schedule_qc_validation=lambda _image_id: None,
        _status_success=lambda *args, **kwargs: None,
        _refresh_assist_warmup_panel=lambda: None,
        _timed_session_active=False,
    )

    assist_generation.accept_suggestions_in_roi(owner)

    assert added == ["roi-ml:True"]

def test_rank_and_calibrate_clears_interactive_learning_metadata_when_feature_disabled() -> None:
    """Verify rank and calibrate clears interactive learning metadata when feature disabled for the current workflow."""
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.6, suggestion_id="ml-off")
    suggestion.meta.update(
        {
            "ml_prediction": True,
            "ml_confidence": 0.91,
            "ml_uncertainty": 0.09,
            "ml_method": "interactive",
        }
    )
    owner = SimpleNamespace(
        controller=SimpleNamespace(
            session_state=SimpleNamespace(annotation_space="stack"),
            score_suggestions_for_context=lambda rows, annotation_space="stack": list(rows),
            feature_enabled=lambda _name, default=False: False,
        ),
        _interactive_learning_model=SimpleNamespace(is_trained=True, predict=lambda rows: []),
        _interactive_learning_enabled=lambda: False,
    )

    ranked = standard.ActionsMixin._rank_and_calibrate_suggestions(owner, [suggestion])

    assert ranked[0].meta.get("ml_prediction") is None
    assert ranked[0].meta.get("ml_confidence") is None
    assert ranked[0].meta.get("ml_uncertainty") is None
    assert ranked[0].meta.get("ml_method") is None
