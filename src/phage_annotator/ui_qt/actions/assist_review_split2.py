"""Split definitions from assist_review.py."""

from __future__ import annotations

import time

import numpy as np
from matplotlib.backends.qt_compat import QtGui, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import AcceptSuggestionCommand, RejectSuggestionCommand
from phage_annotator.ui_qt.assist_state import assist_state_label




import time

import numpy as np
from matplotlib.backends.qt_compat import QtGui, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import AcceptSuggestionCommand, RejectSuggestionCommand
from phage_annotator.ui_qt.assist_state import assist_state_label


from phage_annotator.ui_qt.actions.assist_review_split1 import confirm_suggestion_redecision

def set_selected_suggestion_decision(owner, suggestion_id: str, status: str) -> None:
    """Change suggestion decision through the controller/command layer."""
    image_id = int(owner.primary_image.id)
    sid = str(suggestion_id or "").strip()
    target_status = str(status or "").strip().lower()
    if not sid or target_status not in {"accepted", "rejected", "proposed"}:
        return
    if target_status == "accepted" and not owner._ensure_annotation_write_context_confirmed(
        "Change suggestion decision to accepted"
    ):
        return
    decision_ctx = owner.controller.get_suggestion_decision_context(image_id, sid)
    pending_item = decision_ctx.get("pending_item")
    suggestion = decision_ctx.get("suggestion")
    if suggestion is None:
        owner._status_warning("Suggestion not found for decision update.", source="assist.review")
        return
    current_status = str(decision_ctx.get("status", "") or "proposed")
    if current_status == target_status:
        owner._status_info(f"Suggestion already {target_status}.", source="assist.review")
        return
    if current_status == "accepted" and target_status in {"rejected", "proposed"} and not confirm_suggestion_redecision(owner, target_status):
        owner._status_info("Decision change cancelled.", source="assist.review")
        return
    if target_status == "accepted":
        accept_guard = getattr(owner, "_ensure_suggestion_accept_allowed", None)
        if accept_guard is not None and not accept_guard(
            suggestion,
            action_label="Accept selected suggestion",
            source="assist.review",
        ):
            return
    if pending_item is not None and target_status == "accepted":
        from phage_annotator.ui_qt.actions import assist_review as review_api
        command_cls = getattr(review_api, "AcceptSuggestionCommand", AcceptSuggestionCommand)
        cmd = command_cls(owner.controller, image_id, sid)
        if not owner.controller.execute_view_command(cmd):
            owner._status_error("Could not set accepted for selected suggestion.", source="assist.review")
            return
    elif pending_item is not None and target_status == "rejected":
        cmd = RejectSuggestionCommand(owner.controller, image_id, sid)
        if not owner.controller.execute_view_command(cmd):
            owner._status_error("Could not set rejected for selected suggestion.", source="assist.review")
            return
    else:
        if not owner.controller.update_suggestion_decision(int(image_id), sid, target_status):
            owner._status_error("Could not update suggestion decision.", source="assist.review")
            return
        if hasattr(owner.controller, "append_audit_event"):
            owner.controller.append_audit_event(
                "suggestion_decision_changed",
                image_id=int(image_id),
                suggestion_id=sid,
                status=target_status,
            )
    owner.undo_act.setEnabled(owner.controller.can_undo())
    owner.redo_act.setEnabled(owner.controller.can_redo())
    owner._note_annotation_edit(image_id)
    owner._refresh_table()
    owner._request_ui_refresh("standard-actions", table=True)
    owner._schedule_qc_validation(image_id)
    owner._refresh_assist_warmup_panel()
    owner._status_success(f"Suggestion decision set to {target_status}.", source="assist.review")
