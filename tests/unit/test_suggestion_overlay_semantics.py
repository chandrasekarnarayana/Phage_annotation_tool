"""Tests for assisted suggestion overlay trust semantics."""

from __future__ import annotations

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.ui_qt.rendering.renderer import RenderingMixin


class _Harness(RenderingMixin):
    pass


def _suggestion(*, score: float = 0.0, confidence_available: bool = False, p_accept: float | None = None):
    """Handle the suggestion helper flow."""
    suggestion = PointSuggestion(
        image_id=0,
        image_name="img",
        t=0,
        z=0,
        x=10.0,
        y=20.0,
        score=float(score),
    )
    suggestion.meta["confidence_available"] = bool(confidence_available)
    if p_accept is not None:
        suggestion.meta["p_accept"] = float(p_accept)
    return suggestion


def test_heuristic_only_is_gray() -> None:
    """Verify heuristic only is gray for the current workflow."""
    harness = _Harness()
    color, state = harness._suggestion_overlay_style(_suggestion(score=0.9, confidence_available=False))
    assert state == "heuristic"
    assert color == "#9e9e9e"


def test_calibrated_probability_bands_use_green_yellow_red() -> None:
    """Verify calibrated probability bands use green yellow red for the current workflow."""
    harness = _Harness()
    green, state_g = harness._suggestion_overlay_style(
        _suggestion(score=0.2, confidence_available=True, p_accept=0.80)
    )
    yellow, state_y = harness._suggestion_overlay_style(
        _suggestion(score=0.9, confidence_available=True, p_accept=0.60)
    )
    red, state_r = harness._suggestion_overlay_style(
        _suggestion(score=0.9, confidence_available=True, p_accept=0.30)
    )
    assert (green, state_g) == ("#43a047", "calibrated_high")
    assert (yellow, state_y) == ("#fdd835", "calibrated_mid")
    assert (red, state_r) == ("#e53935", "calibrated_low")
