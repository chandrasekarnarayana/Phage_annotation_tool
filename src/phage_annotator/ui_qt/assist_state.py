"""Canonical assist-state definitions and presentation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class AssistState(str, Enum):
    """Canonical assisted-annotation trust states."""

    HEURISTIC = "heuristic"
    LEARNED_UNCALIBRATED = "learned_uncalibrated"
    CALIBRATED = "calibrated"


@dataclass(frozen=True)
class AssistStatePresentation:
    """Display metadata for assist-state widgets/tooltips."""

    label: str
    color: str
    order: int


ASSIST_STATE_PRESENTATION: dict[AssistState, AssistStatePresentation] = {
    AssistState.HEURISTIC: AssistStatePresentation(
        label="Heuristic", color="#9e9e9e", order=0
    ),
    AssistState.LEARNED_UNCALIBRATED: AssistStatePresentation(
        label="Learned (Uncalibrated)", color="#fdd835", order=1
    ),
    AssistState.CALIBRATED: AssistStatePresentation(
        label="Calibrated", color="#43a047", order=2
    ),
}


def assist_state_label(state: AssistState) -> str:
    """Return the canonical label for an assist state."""
    return ASSIST_STATE_PRESENTATION[state].label


def assist_state_color(state: AssistState) -> str:
    """Return the canonical color for an assist state."""
    return ASSIST_STATE_PRESENTATION[state].color


def infer_assist_state(
    *,
    controller,
    image_name: str,
    annotation_space: str,
    suggestions: Iterable | None = None,
) -> AssistState:
    """Infer canonical assist-state from controller status and suggestion metadata."""
    rows = list(suggestions or [])
    if controller is None:
        return AssistState.HEURISTIC

    if rows:
        context_key = controller._context_key(
            suggestion=rows[0], annotation_space=annotation_space
        )
    else:
        context_key = f"{image_name}|{annotation_space}|current_view"
    level, _msg = controller.assist_status(
        annotation_space=annotation_space,
        context_key=context_key,
    )

    if any(
        bool(dict(getattr(suggestion, "meta", {}) or {}).get("confidence_available", False))
        for suggestion in rows
    ):
        return AssistState.CALIBRATED

    if str(level) == "learned":
        return AssistState.LEARNED_UNCALIBRATED

    rankers = getattr(controller, "suggestion_rankers_by_space", {}) or {}
    trained = 0
    for ranker in rankers.values():
        trained = max(trained, int(getattr(ranker, "trained_samples", 0)))
    auto_enabled = bool(
        getattr(controller.session_state, "suggestion_auto_retrain_enabled", False)
    )
    if auto_enabled and trained > 0:
        return AssistState.LEARNED_UNCALIBRATED
    return AssistState.HEURISTIC
