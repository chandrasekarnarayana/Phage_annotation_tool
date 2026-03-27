"""Derived menu-action state tests."""

from __future__ import annotations

from types import SimpleNamespace

from phage_annotator.ui_qt.assist_state import AssistState
from phage_annotator.ui_qt.services.status_derived import build_status_snapshot


class _Slider:
    def __init__(self, value: int = 0, maximum: int = 0):
        self._value = value
        self._maximum = maximum

    def value(self) -> int:
        return self._value

    def maximum(self) -> int:
        return self._maximum


class _SelectionModel:
    def __init__(self, rows: int):
        self._rows = rows

    def selectedRows(self):
        return [object() for _ in range(self._rows)]


class _AnnotTable:
    def __init__(self, rows: int):
        self._rows = rows

    def selectionModel(self):
        return _SelectionModel(self._rows)


class _Cache:
    def stats(self):
        return (0.0, 0)


def _make_owner(*, mode: str = "independent", has_suggestions: bool = False, has_qc: bool = False, selected_rows: int = 0):
    primary_image = SimpleNamespace(
        id=1,
        name="sample_a",
        array=SimpleNamespace(shape=(5, 3), filename=None),
        downsampled=False,
    )
    controller = SimpleNamespace(
        session_state=SimpleNamespace(dirty=False, modality_manager=None),
        current_annotation_context=lambda: {
            "mode": mode,
            "ownership_mode": mode,
            "context_key": f"ctx:{mode}",
        },
        annotation_binding_for_panel=lambda _target: {},
    )
    qc_state = None
    if has_qc:
        qc_state = SimpleNamespace(
            issues=[SimpleNamespace(severity=SimpleNamespace(value="warning"))]
        )
    owner = SimpleNamespace(
        primary_image=primary_image,
        annotations={1: [SimpleNamespace(t=0)] if selected_rows or has_qc else []},
        suggestions={1: [object()] if has_suggestions else []},
        t_slider=_Slider(0, 4),
        z_slider=_Slider(0, 2),
        speed_slider=_Slider(12, 30),
        annot_table=_AnnotTable(selected_rows),
        proj_cache=_Cache(),
        controller=controller,
        current_label="Phage",
        roi_shape="box",
        roi_rect=(0, 0, 0, 0),
        _panel_modality_map={},
        annotate_target="modality_0",
        _playback_mode=False,
        _assist_mode_enabled=False,
        _settings=None,
        _last_autosave_timestamp=None,
        jobs=None,
        qc_state=qc_state,
        tool_router=None,
        _layout_history=[],
        _last_smlm_run_config=None,
        _timed_session_active=False,
        _render_scales={},
        _lod_mode_active={},
        _active_modality_idx=0,
    )
    owner._current_keypoints = lambda: list(owner.annotations[1])
    owner._view_density_stats = lambda: (0, 0.0)
    owner._roi_total_stats = lambda: (0, 0.0)
    owner._canonical_assist_state = lambda: AssistState.HEURISTIC
    owner._assist_context_need_count = lambda: 0
    owner._bottom_task_counts = lambda: (1 if has_qc else 0, 0, 0)
    owner._effective_assist_context_line = lambda: "-"
    owner._suggestion_freshness_state = lambda _image_id: {
        "has_suggestions": has_suggestions,
        "age_text": "fresh",
        "is_stale": False,
    }
    owner._sync_key_for_panel = lambda _panel: "1"
    owner._sync_mode_enabled_for_panel = lambda _panel, _mode: True
    owner._is_annotation_context_guard_pending = lambda: False
    return owner


def test_menu_action_state_respects_read_only_context() -> None:
    owner = _make_owner(mode="read_only", has_suggestions=True)
    snapshot = build_status_snapshot(owner)

    assert snapshot.action_enabled["save_csv_act"] is False
    assert snapshot.action_enabled["save_json_act"] is False
    assert snapshot.action_enabled["suggest_points_act"] is False
    assert snapshot.action_enabled["accept_visible_suggestions_act"] is False
    assert snapshot.action_enabled["reject_visible_suggestions_act"] is False
    assert snapshot.action_enabled["export_view_act"] is True
    assert "writable annotation context" in snapshot.action_disabled_reason["save_csv_act"].lower()


def test_menu_action_state_enables_review_and_qc_actions_from_state() -> None:
    owner = _make_owner(mode="independent", has_suggestions=True, has_qc=True, selected_rows=2)
    snapshot = build_status_snapshot(owner)

    assert snapshot.action_enabled["set_current_user_act"] is True
    assert snapshot.action_enabled["mark_selected_approved_act"] is True
    assert snapshot.action_enabled["assign_selected_act"] is True
    assert snapshot.action_enabled["qc_validate_act"] is True
    assert snapshot.action_enabled["qc_jump_next_act"] is True
    assert snapshot.action_enabled["queue_blocked_qc_act"] is True
    assert snapshot.action_enabled["show_suggestion_patch_act"] is True


def test_menu_action_state_explains_qc_and_selection_requirements() -> None:
    owner = _make_owner(mode="independent", has_suggestions=False, has_qc=False, selected_rows=0)
    snapshot = build_status_snapshot(owner)

    assert snapshot.action_enabled["mark_selected_approved_act"] is False
    assert snapshot.action_enabled["qc_jump_next_act"] is False
    assert "select one or more annotations" in snapshot.action_disabled_reason["mark_selected_approved_act"].lower()
    assert "no qc issues" in snapshot.action_disabled_reason["qc_jump_next_act"].lower()
