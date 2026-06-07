"""Actions suggestion generation impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


def accept_suggestions_in_roi(owner) -> None:
    """Accept the currently visible suggestions inside the active ROI."""
    if not owner._ensure_annotation_write_context_confirmed("Accept suggestions in ROI"):
        return
    visible = owner._visible_suggestions()
    candidates = [s for s in visible if owner._point_in_roi(float(s.x), float(s.y))]
    blocked = 0
    allowed: list[PointSuggestion] = []
    for suggestion in candidates:
        accept_guard = getattr(owner, "_ensure_suggestion_accept_allowed", None)
        if accept_guard is not None and not accept_guard(
            suggestion,
            action_label="Accept suggestion in ROI",
            source="assist.accept.roi",
        ):
            blocked += 1
            continue
        allowed.append(suggestion)
    candidates = allowed
    accepted = 0
    for suggestion in list(candidates):
        cmd = AcceptSuggestionCommand(owner.controller, owner.primary_image.id, suggestion.suggestion_id)
        if owner.controller.execute_view_command(cmd):
            accepted += 1
            owner.controller.update_suggestion_metrics(correction_distance=0.0)
            if getattr(owner, "_interactive_learning_enabled", lambda: False)():
                owner._interactive_learning_model.add_example(suggestion, accepted=True)
            if bool(getattr(owner, "_timed_session_active", False)):
                owner._timed_session_accepts = int(getattr(owner, "_timed_session_accepts", 0)) + 1
                owner._timed_session_points = int(getattr(owner, "_timed_session_points", 0)) + 1
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    if accepted:
        owner._note_annotation_edit(owner.primary_image.id)
        owner._refresh_table()
        owner._request_ui_refresh("standard-actions")
        owner._schedule_qc_validation(owner.primary_image.id)
        owner.controller.append_audit_event(
            "suggestions_accepted_in_roi",
            image_id=owner.primary_image.id,
            count=accepted,
        )
    status_msg = f"Accepted {accepted} suggestion(s) in ROI."
    if blocked:
        status_msg += f" {blocked} stale suggestion(s) were blocked."
    owner._status_success(status_msg, source="assist.accept.roi")
    owner._refresh_assist_warmup_panel()

def clear_suggestions_current_image(owner) -> None:
    """Clear pending suggestions for the current image."""
    cmd = ClearSuggestionsCommand(owner.controller, owner.primary_image.id)
    if not owner.controller.execute_view_command(cmd):
        owner._status_info("No suggestions to clear.", source="assist.clear")
        return
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    owner._request_ui_refresh("standard-actions")
    owner._status_success("Cleared suggestions.", source="assist.clear")
    owner._refresh_assist_warmup_panel()
