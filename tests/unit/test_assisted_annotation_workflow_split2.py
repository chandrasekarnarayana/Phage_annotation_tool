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


from tests.unit.test_assisted_annotation_workflow_split1 import _Harness, _ControllerHarness

def test_classification_keeps_strict_truth_empty_when_only_non_strict_rows_exist() -> None:
    """Verify classification keeps strict truth empty when only non strict rows exist for the current workflow."""
    controller = _ControllerHarness()
    controller.session_state.annotations[0] = [
        Keypoint(0, "img", 0, 0, 12.0, 10.0, label="noise", source="suggestion"),
    ]
    row = PointSuggestion(0, "img", 0, 0, 11.0, 10.0, 0.7, label="phage")

    controller._classify_generated_suggestion(0, row)

    meta = dict(getattr(row, "meta", {}) or {})
    assert "distance_to_nearest_truth_strict" not in meta
    assert float(meta["distance_to_any_annotation"]) == 1.0

def test_local_rescore_adjustment_is_bounded() -> None:
    """Verify local rescore adjustment is bounded for the current workflow."""
    controller = _ControllerHarness()
    suggestion = PointSuggestion(0, "img", 0, 0, 8.0, 8.0, 0.6, label="phage")
    suggestion.meta["p_accept"] = 0.6
    controller.session_state.suggestions[0] = [suggestion]
    controller.session_state.annotations[0] = [
        Keypoint(0, "img", 0, 0, 8.5, 8.5, label="phage", source="manual"),
        Keypoint(0, "img", 0, 0, 12.0, 12.0, label="phage", source="manual"),
    ]
    controller.session_state.suggestion_history[0] = [
        PointSuggestion(0, "img", 0, 0, 8.2, 8.2, 0.2, label="phage", status="rejected")
    ]
    controller.session_state.assist_min_total_labels = 0
    controller.session_state.assist_min_positive_labels = 0
    controller.session_state.assist_min_negative_labels = 0
    controller.session_state.assist_min_labels_per_context = 0
    ranker = SimpleNamespace(
        trained_samples=32,
        apply_to_suggestions=lambda rows: [
            (
                row.meta.__setitem__("p_accept", 0.6),
                row.meta.__setitem__("confidence_available", True),
                setattr(row, "score", 0.6),
                row,
            )[-1]
            for row in rows
        ],
        fit=lambda *args, **kwargs: None,
        to_dict=lambda: {},
        predict_p_accept=lambda features: np.full((len(features),), 0.6, dtype=np.float64),
    )
    controller.suggestion_rankers_by_space = {"stack": ranker, "projection": ranker}

    summary = controller.local_rescore_visible_context({"image_id": 0, "t": 0, "z": 0, "annotation_space": "stack"})

    assert summary["rescored_count"] == 1
    adjustment = float(suggestion.meta["local_rescore_adjustment"])
    assert -0.08 <= adjustment <= 0.08

def test_local_truth_update_suppresses_nearby_duplicates_after_manual_add() -> None:
    """Verify local truth update suppresses nearby duplicates after manual add for the current workflow."""
    controller = _ControllerHarness()
    manual = Keypoint(0, "img", 0, 0, 10.0, 10.0, label="phage", source="manual")
    controller.session_state.annotations[0] = [manual]
    kept = PointSuggestion(0, "img", 0, 0, 30.0, 30.0, 0.7, label="phage")
    dup = PointSuggestion(0, "img", 0, 0, 10.2, 10.1, 0.9, label="phage")
    controller.session_state.suggestions[0] = [kept, dup]
    controller.session_state.suggestion_history[0] = []

    summary = controller.local_truth_update({"image_id": 0, "t": 0, "z": 0}, manual)

    assert summary["local_duplicates_suppressed"] == 1
    assert [s.suggestion_id for s in controller.session_state.suggestions[0]] == [kept.suggestion_id]
    assert controller.session_state.last_local_suggestion_update_summary["local_duplicates_suppressed"] == 1

def test_local_rescore_visible_context_updates_local_scores_and_sorts() -> None:
    """Verify local rescore visible context updates local scores and sorts for the current workflow."""
    controller = _ControllerHarness()
    anchor = Keypoint(0, "img", 0, 0, 8.0, 8.0, label="phage", source="manual")
    controller.session_state.annotations[0] = [anchor]
    near = PointSuggestion(0, "img", 0, 0, 9.0, 8.5, 0.9, label="phage")
    far = PointSuggestion(0, "img", 0, 0, 50.0, 50.0, 0.6, label="phage")
    near.meta["generator_score"] = 0.9
    far.meta["generator_score"] = 0.6
    controller.session_state.suggestions[0] = [near, far]

    summary = controller.local_rescore_visible_context({"image_id": 0, "t": 0, "z": 0})

    assert summary["rescored_count"] == 2
    assert float(near.meta["local_rescore_score"]) < 0.9
    assert float(far.meta["local_rescore_score"]) >= float(near.meta["local_rescore_score"])
    assert controller.session_state.suggestions[0][0].suggestion_id == far.suggestion_id

def test_accept_suggestion_command_preserves_provenance_fields() -> None:
    """Verify accept suggestion command preserves provenance fields for the current workflow."""
    harness = _Harness()
    suggestion = PointSuggestion(
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        y=5.0,
        x=7.0,
        score=0.9,
        source_model="local_peaks",
        roi_id="roi-A",
        meta={"p_accept": 0.82, "candidate_class": "conflict", "notes": "review closely"},
    )
    harness.session_state.suggestions[0].append(suggestion)

    accept = AcceptSuggestionCommand(harness, 0, suggestion.suggestion_id)
    assert harness.execute_view_command(accept)

    row = harness.session_state.annotations[0][0]
    assert row.status == "accepted"
    assert row.source == "suggested:local_peaks"
    assert row.confidence == 0.82
    assert row.roi_name == "roi-A"
    assert row.notes == "review closely"
    assert row.meta["candidate_class"] == "conflict"

def test_local_rescore_uses_heuristic_confidence_flag_when_ranker_not_ready() -> None:
    """Verify local rescore uses heuristic confidence flag when ranker not ready for the current workflow."""
    controller = _ControllerHarness()
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 10.0, 0.55, label="phage")

    out = controller.score_suggestions_for_context([suggestion], annotation_space="stack")

    assert out[0].meta["confidence_available"] is False
    assert out[0].meta["confidence_note"] == "heuristic_only"

def test_suggestion_ids_are_deterministic_for_identical_inputs() -> None:
    """Verify suggestion ids are deterministic for identical inputs for the current workflow."""
    a = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.5, label="phage", source_model="local_peaks", source_modality="raw")
    b = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.7, label="phage", source_model="local_peaks", source_modality="raw")

    assert a.suggestion_id == b.suggestion_id

def test_accept_undo_roundtrip_preserves_rich_suggestion_fields() -> None:
    """Verify accept undo roundtrip preserves rich suggestion fields for the current workflow."""
    harness = _Harness()
    suggestion = PointSuggestion(
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        y=5.0,
        x=7.0,
        score=0.9,
        source_model="local_peaks",
        source_modality="consensus",
        supporting_modalities=["raw", "mean_projection"],
        cross_modality_consistency_score=0.8,
        control_contradiction_score=0.2,
        uncertainty_score=0.4,
        uncertainty_reason="dense_region_ambiguity",
        density_context={"local_density": 0.12},
    )
    harness.session_state.suggestions[0].append(suggestion)

    accept = AcceptSuggestionCommand(harness, 0, suggestion.suggestion_id)
    assert harness.execute_view_command(accept)
    assert harness.undo()

    restored = harness.session_state.suggestions[0][0]
    assert restored.supporting_modalities == ["raw", "mean_projection"]
    assert restored.cross_modality_consistency_score == 0.8
    assert restored.control_contradiction_score == 0.2
    assert restored.uncertainty_score == 0.4
    assert restored.uncertainty_reason == "dense_region_ambiguity"
    assert restored.density_context["local_density"] == 0.12

def test_current_accept_path_honors_stale_guard_without_executing_command(monkeypatch) -> None:
    """Verify current accept path honors stale guard without executing command for the current workflow."""
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.9, suggestion_id="stale-one")
    calls = {"executed": 0}
    monkeypatch.setattr(
        standard,
        "AcceptSuggestionCommand",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("command should not be built")),
    )
    owner = SimpleNamespace(
        _ensure_annotation_write_context_confirmed=lambda _label: True,
        _visible_suggestions_uncertain_first=lambda: [suggestion],
        _suggestion_cursor=0,
        _ensure_suggestion_accept_allowed=lambda *_args, **_kwargs: False,
        _status_info=lambda *args, **kwargs: None,
        _refresh_assist_warmup_panel=lambda: None,
        _focus_current_uncertain_suggestion=lambda: None,
        controller=SimpleNamespace(execute_view_command=lambda _cmd: calls.__setitem__("executed", calls["executed"] + 1)),
        primary_image=SimpleNamespace(id=0),
    )

    standard.ActionsMixin._accept_current_uncertain_suggestion(owner)

    assert calls["executed"] == 0

def test_review_accept_path_honors_stale_guard_without_executing_command(monkeypatch) -> None:
    """Verify review accept path honors stale guard without executing command for the current workflow."""
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.9, suggestion_id="stale-review")
    decision_ctx = {"pending_item": suggestion, "suggestion": suggestion, "status": "proposed"}
    calls = {"executed": 0}
    monkeypatch.setattr(
        assist_review,
        "AcceptSuggestionCommand",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("command should not be built")),
    )
    owner = SimpleNamespace(
        primary_image=SimpleNamespace(id=0),
        _ensure_annotation_write_context_confirmed=lambda _label: True,
        _ensure_suggestion_accept_allowed=lambda *_args, **_kwargs: False,
        _status_warning=lambda *args, **kwargs: None,
        _status_info=lambda *args, **kwargs: None,
        _status_error=lambda *args, **kwargs: None,
        _status_success=lambda *args, **kwargs: None,
        controller=SimpleNamespace(
            get_suggestion_decision_context=lambda _image_id, _sid: decision_ctx,
            execute_view_command=lambda _cmd: calls.__setitem__("executed", calls["executed"] + 1),
            can_undo=lambda: False,
            can_redo=lambda: False,
        ),
        undo_act=SimpleNamespace(setEnabled=lambda _value: None),
        redo_act=SimpleNamespace(setEnabled=lambda _value: None),
        _note_annotation_edit=lambda _image_id: None,
        _refresh_table=lambda: None,
        _request_ui_refresh=lambda *args, **kwargs: None,
        _schedule_qc_validation=lambda _image_id: None,
        _refresh_assist_warmup_panel=lambda: None,
    )

    assist_review.set_selected_suggestion_decision(owner, suggestion.suggestion_id, "accepted")

    assert calls["executed"] == 0

def test_accept_in_roi_honors_stale_guard_and_write_context(monkeypatch) -> None:
    """Verify accept in roi honors stale guard and write context for the current workflow."""
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.9, suggestion_id="stale-roi")
    calls = {"executed": 0}
    monkeypatch.setattr(
        assist_generation,
        "AcceptSuggestionCommand",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("command should not be built")),
    )
    owner = SimpleNamespace(
        _ensure_annotation_write_context_confirmed=lambda _label: True,
        _visible_suggestions=lambda: [suggestion],
        _point_in_roi=lambda _x, _y: True,
        _ensure_suggestion_accept_allowed=lambda *_args, **_kwargs: False,
        controller=SimpleNamespace(
            execute_view_command=lambda _cmd: calls.__setitem__("executed", calls["executed"] + 1),
            can_undo=lambda: False,
            can_redo=lambda: False,
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
    )

    assist_generation.accept_suggestions_in_roi(owner)

    assert calls["executed"] == 0
