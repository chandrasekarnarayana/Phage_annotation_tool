"""Regression tests for the 3-layer workspace snapshot helpers."""

from __future__ import annotations

from types import SimpleNamespace

from phage_annotator.core.session_state import ViewState
from phage_annotator.core.workspace_snapshot import (
    apply_workspace_snapshot_to_controller,
    build_workspace_snapshot,
)
from phage_annotator.data.display_mapping import DisplayMapping


class _Emitter:
    """Minimal Qt-like signal stub used by controller harnesses."""

    def __init__(self) -> None:
        self.count = 0

    def emit(self) -> None:
        self.count += 1


def test_apply_workspace_snapshot_restores_active_frame_display_mapping() -> None:
    """Snapshot apply should restore the active frame display mapping."""
    controller = SimpleNamespace(
        session_state=SimpleNamespace(active_primary_id=3),
        view_state=ViewState(),
        display_mapping=DisplayMapping(0.0, 1.0),
        display_changed=_Emitter(),
    )

    snapshot = {
        "session_workspace": {
            "active_primary_id": 3,
            "display_mapping_frame": {
                "min": 12.5,
                "max": 42.0,
                "gamma": 1.7,
                "lut": 4,
                "invert": True,
            },
        }
    }

    apply_workspace_snapshot_to_controller(controller, snapshot)

    mapping = controller.display_mapping.mapping_for(3, "frame")
    assert mapping.min_val == 12.5
    assert mapping.max_val == 42.0
    assert mapping.gamma == 1.7
    assert mapping.lut == 4
    assert mapping.invert is True
    assert controller.display_changed.count == 1


def test_workspace_snapshot_round_trips_lazy_sync_topology() -> None:
    """Snapshot build/apply should preserve lazy sync groups, modes, and ROI group state."""
    session_state = SimpleNamespace(
        active_primary_id=3,
        active_support_id=1,
        fps=12,
        current_label="Phage",
        labels=["Phage"],
        dirty=False,
        project_path=None,
        project_save_time=None,
        last_folder=None,
        recent_images=[],
        images=[],
        annotations={},
        annotation_space="stack",
        generation_space="stack",
        lazy_sync_groups={0: "1", "builtin:mean": "1", 1: "2"},
        lazy_sync_modes={
            0: {"contrast": True, "zoom": True, "playback": False},
            "builtin:mean": {"contrast": True, "zoom": False, "playback": False},
        },
        roi_by_sync_group={"1": {"shape": "circle", "rect": (1.0, 2.0, 3.0, 4.0)}},
        feature_flags={"annotation_provenance_schema": True},
        workflow_metrics={"annotations_added": 3, "provenance_complete_fraction": 1.0},
    )
    controller = SimpleNamespace(
        session_state=session_state,
        view_state=ViewState(),
        display_mapping=DisplayMapping(0.0, 1.0),
        display_changed=_Emitter(),
    )

    snapshot = build_workspace_snapshot(controller, {}, {})
    assert snapshot["session_workspace"]["lazy_sync_groups"] == {"0": "1", "builtin:mean": "1", "1": "2"}
    assert snapshot["session_workspace"]["lazy_sync_modes"]["builtin:mean"]["zoom"] is False
    assert snapshot["session_workspace"]["roi_by_sync_group"]["1"]["shape"] == "circle"

    target = SimpleNamespace(
        session_state=SimpleNamespace(
            active_primary_id=0,
            active_support_id=0,
            fps=10,
            current_label="",
            lazy_sync_groups={},
            lazy_sync_modes={},
            roi_by_sync_group={},
            feature_flags={},
            workflow_metrics={},
        ),
        view_state=ViewState(),
        display_mapping=DisplayMapping(0.0, 1.0),
        display_changed=_Emitter(),
    )

    apply_workspace_snapshot_to_controller(target, snapshot)

    assert target.session_state.lazy_sync_groups == {0: "1", "builtin:mean": "1", 1: "2"}
    assert target.session_state.lazy_sync_modes["builtin:mean"]["zoom"] is False
    assert target.session_state.roi_by_sync_group["1"]["rect"] == (1.0, 2.0, 3.0, 4.0)
    assert target.session_state.feature_flags["annotation_provenance_schema"] is True
    assert target.session_state.workflow_metrics["annotations_added"] == 3
