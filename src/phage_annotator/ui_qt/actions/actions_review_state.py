"""Annotation context guards, suggestion review, and annotation management actions."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions import assist_generation, assist_review

logger = logging.getLogger(__name__)

class ActionsReviewStateMixin:
    """Mixin for annotation write context guards, suggestion review, and annotation management."""

    # ── Annotation context guards ──────────────────────────────────────────

    def _set_selected_review_state(self, state: str) -> None:
        """Set review state on selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._status_info(
                "Select one or more annotations first.",
                timeout_ms=2500,
                source="standard.annotation_selection",
            )
            return
        updated = 0
        now_ts = time.time()
        for kp in selected:
            new_meta = dict(kp.meta)
            new_meta["review_state"] = state
            new_meta["reviewer"] = self.controller.session_state.current_user
            new_meta["reviewed_at"] = now_ts
            replacement = type(kp)(
                image_id=kp.image_id,
                image_name=kp.image_name,
                t=kp.t,
                z=kp.z,
                y=kp.y,
                x=kp.x,
                label=kp.label,
                annotation_id=kp.annotation_id,
                image_key=kp.image_key,
                source=kp.source,
                meta=new_meta,
                modality_idx=kp.modality_idx,
            )
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                updated += 1
        if updated:
            self.controller.append_audit_event(
                "review_state_updated", state=state, count=updated
            )
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Updated review state for {updated} annotation(s).",
            timeout_ms=3000,
            source="standard.review_state",
        )

    def _assign_selected_annotations_dialog(self) -> None:
        """Set assignee for selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._status_info(
                "Select one or more annotations first.",
                timeout_ms=2500,
                source="standard.annotation_selection",
            )
            return
        assignee, ok = QtWidgets.QInputDialog.getText(
            self,
            "Assign Selected Annotations",
            "Assignee:",
            text=self.controller.session_state.current_user,
        )
        if not ok:
            return
        assignee = assignee.strip()
        updated = 0
        for kp in selected:
            new_meta = dict(kp.meta)
            new_meta["assignee"] = assignee
            replacement = type(kp)(
                image_id=kp.image_id,
                image_name=kp.image_name,
                t=kp.t,
                z=kp.z,
                y=kp.y,
                x=kp.x,
                label=kp.label,
                annotation_id=kp.annotation_id,
                image_key=kp.image_key,
                source=kp.source,
                meta=new_meta,
                modality_idx=kp.modality_idx,
            )
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                updated += 1
        if updated:
            self.controller.append_audit_event(
                "assignee_updated", assignee=assignee, count=updated
            )
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Assigned {updated} annotation(s) to '{assignee}'.",
            timeout_ms=3000,
            source="standard.assignee",
        )

    def _set_current_user_dialog(self) -> None:
        """Set current local user identity for review/audit actions."""
        current = self.controller.session_state.current_user
        user, ok = QtWidgets.QInputDialog.getText(self, "Set Current User", "User:", text=current)
        if not ok:
            return
        user = user.strip() or "local_user"
        self.controller.set_current_user_value(user)
        self.controller.append_audit_event("current_user_changed", user=user)
        self._status_info(
            f"Current user set to '{user}'.",
            timeout_ms=2500,
            source="standard.current_user",
        )

    def _set_review_queue_filter(self, mode: str) -> None:
        """Switch annotation table queue filter mode."""
        self._review_queue_filter = str(mode)
        action_map = {
            "all": getattr(self, "queue_all_act", None),
            "my_queue": getattr(self, "queue_my_act", None),
            "needs_review": getattr(self, "queue_needs_review_act", None),
            "blocked_qc": getattr(self, "queue_blocked_qc_act", None),
        }
        for key, action in action_map.items():
            if action is None:
                continue
            action.blockSignals(True)
            action.setChecked(key == self._review_queue_filter)
            action.blockSignals(False)
        self._refresh_table()
        self._refresh_review_queue_panel()
        self._request_ui_refresh("standard-actions")
        self._status_info(
            f"Review queue: {self._review_queue_filter}.",
            timeout_ms=2500,
            source="standard.review_queue",
        )

    def _selected_table_keypoints(self) -> list:
        """Return currently selected keypoints from annotation table."""
        if getattr(self, "annot_table", None) is None or self.annot_table.selectionModel() is None:
            return []
        rows = sorted({idx.row() for idx in self.annot_table.selectionModel().selectedRows()})
        selected = []
        for row in rows:
            kp = self._keypoint_for_table_row(row) if hasattr(self, "_keypoint_for_table_row") else None
            if kp is not None:
                selected.append(kp)
        return selected
