"""Top-level assist generation action helpers.

These functions are imported by action shims and delegate through the owner
object so the GUI can keep generation, acceptance, and rejection responsive.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    RejectSuggestionCommand,
)


def _set_generation_progress(owner, value: Optional[int], message: str = "") -> None:
    """Update assist generation progress widgets when they are present."""
    owner._assist_generation_progress = value
    panel = getattr(owner, "review_queue_panel", None)
    if panel is None:
        return
    progress_bar = getattr(panel, "progress_bar", None)
    if progress_bar is not None and value is not None:
        progress_bar.setValue(int(max(0, min(100, int(value)))))
    label = getattr(panel, "progress_label", None)
    if label is not None and message:
        label.setText(str(message))


def _current_label(owner) -> str:
    """Return the active annotation label for generated suggestions."""
    state = getattr(getattr(owner, "controller", None), "session_state", None)
    return str(getattr(state, "current_label", "phage") or "phage")


def _append_generated(owner, rows: list[PointSuggestion]) -> None:
    """Append generated rows through the controller and refresh UI hooks."""
    image_id = int(getattr(getattr(owner, "primary_image", None), "id", 0))
    controller = getattr(owner, "controller", None)
    if controller is not None and hasattr(controller, "append_generated_suggestions"):
        controller.append_generated_suggestions(image_id, rows)
    if hasattr(owner, "_request_ui_refresh"):
        owner._request_ui_refresh("assist-generation")


def suggest_points_current_slice(owner) -> None:
    """Generate suggestions for the currently visible slice."""
    image = getattr(owner, "primary_image", None)
    model = getattr(owner, "_suggestion_model", None)
    frame = getattr(owner, "current_image", None)
    if model is None or image is None or frame is None:
        return
    _set_generation_progress(owner, 10, "Generating suggestions")
    rows = model.predict(
        np.asarray(frame),
        image_id=int(image.id),
        image_name=str(getattr(image, "name", "")),
        t=int(getattr(getattr(owner, "view_state", None), "t", 0)),
        z=int(getattr(getattr(owner, "view_state", None), "z", 0)),
        label=_current_label(owner),
    )
    _append_generated(owner, list(rows))
    _set_generation_progress(owner, 100, "Suggestions ready")


def suggest_points_current_image(owner) -> None:
    """Generate suggestions for the current image using the visible slice path."""
    suggest_points_current_slice(owner)


def preview_batch_accept_dialog(owner, *args, **kwargs) -> bool:
    """Return whether a batch accept action should proceed."""
    return True


def accept_visible_suggestions(owner) -> None:
    """Accept suggestions currently visible in the review queue."""
    for suggestion in list(getattr(owner, "_visible_suggestions", lambda: [])()):
        command = AcceptSuggestionCommand(
            owner.controller,
            int(owner.primary_image.id),
            suggestion.suggestion_id,
        )
        owner.controller.execute_view_command(command)


def accept_high_confidence_suggestions(owner) -> None:
    """Accept visible suggestions over the configured confidence threshold."""
    threshold = float(getattr(owner, "suggestion_accept_threshold", 0.8))
    rows = [
        row for row in list(getattr(owner, "_visible_suggestions", lambda: [])())
        if float(getattr(row, "score", 0.0)) >= threshold
    ]
    for row in rows:
        owner.controller.execute_view_command(
            AcceptSuggestionCommand(owner.controller, int(owner.primary_image.id), row.suggestion_id)
        )


def reject_visible_suggestions(owner) -> None:
    """Reject suggestions currently visible in the review queue."""
    for suggestion in list(getattr(owner, "_visible_suggestions", lambda: [])()):
        command = RejectSuggestionCommand(
            owner.controller,
            int(owner.primary_image.id),
            suggestion.suggestion_id,
        )
        owner.controller.execute_view_command(command)
