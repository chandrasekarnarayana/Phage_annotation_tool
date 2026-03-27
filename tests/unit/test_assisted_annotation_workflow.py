"""Unit tests for assisted annotation suggestions and commands."""

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


class _ControllerHarness(SessionControllerSuggestionsMixin):
    def __init__(self) -> None:
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
        self.session_state.dirty = bool(dirty)

    def record_workflow_event(self, kind: str, **details) -> None:
        self._workflow_events.append((str(kind), dict(details)))

    def save_suggestion_ranker_state(self) -> None:
        self.session_state.suggestion_ranker_state = {}



def test_local_peak_model_generates_candidates() -> None:
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


def test_classification_keeps_strict_truth_empty_when_only_non_strict_rows_exist() -> None:
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
    controller = _ControllerHarness()
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 10.0, 0.55, label="phage")

    out = controller.score_suggestions_for_context([suggestion], annotation_space="stack")

    assert out[0].meta["confidence_available"] is False
    assert out[0].meta["confidence_note"] == "heuristic_only"


def test_suggestion_ids_are_deterministic_for_identical_inputs() -> None:
    a = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.5, label="phage", source_model="local_peaks", source_modality="raw")
    b = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.7, label="phage", source_model="local_peaks", source_modality="raw")

    assert a.suggestion_id == b.suggestion_id


def test_accept_undo_roundtrip_preserves_rich_suggestion_fields() -> None:
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


def test_accept_in_roi_feeds_interactive_learning_when_enabled(monkeypatch) -> None:
    suggestion = PointSuggestion(0, "img", 0, 0, 10.0, 12.0, 0.9, suggestion_id="roi-ml")
    added: list[str] = []

    class _FakeCmd:
        def __init__(self, _controller, _image_id, suggestion_id):
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
