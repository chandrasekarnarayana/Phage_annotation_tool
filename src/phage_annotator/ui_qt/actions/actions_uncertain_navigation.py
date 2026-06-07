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

class ActionsUncertainNavigationMixin:
    """Mixin for annotation write context guards, suggestion review, and annotation management."""

    # ── Annotation context guards ──────────────────────────────────────────

    def _focus_suggestion(self, suggestion: PointSuggestion) -> None:
        """Jump view to a suggestion and auto-pan only when it is off-screen."""
        if hasattr(self, "t_slider"):
            self.t_slider.setValue(
                max(self.t_slider.minimum(), min(int(suggestion.t), self.t_slider.maximum()))
            )
        if hasattr(self, "z_slider"):
            self.z_slider.setValue(
                max(self.z_slider.minimum(), min(int(suggestion.z), self.z_slider.maximum()))
            )
        frame_ax = (
            self.renderer.axes.get("frame") if getattr(self, "renderer", None) is not None else None
        )
        if frame_ax is not None:
            x = float(suggestion.x)
            y = float(suggestion.y)
            x0, x1 = frame_ax.get_xlim()
            y0, y1 = frame_ax.get_ylim()
            bounds_ok = np.isfinite(np.asarray([x0, x1, y0, y1], dtype=float)).all()
            if bounds_ok:
                x_min, x_max = (x0, x1) if x0 <= x1 else (x1, x0)
                y_min, y_max = (y0, y1) if y0 <= y1 else (y1, y0)
                in_view = (x_min <= x <= x_max) and (y_min <= y <= y_max)
                if not in_view:
                    span_x = abs(x1 - x0)
                    span_y = abs(y1 - y0)
                    fallback_half = float(getattr(self, "_suggestion_focus_zoom_px", 160.0)) / 2.0
                    half_x = span_x / 2.0 if span_x > 0 else fallback_half
                    half_y = span_y / 2.0 if span_y > 0 else fallback_half
                    frame_ax.set_xlim(x - half_x, x + half_x)
                    if y0 <= y1:
                        frame_ax.set_ylim(y - half_y, y + half_y)
                    else:
                        frame_ax.set_ylim(y + half_y, y - half_y)
            else:
                zoom_px = float(getattr(self, "_suggestion_focus_zoom_px", 160.0))
                half = zoom_px / 2.0
                frame_ax.set_xlim(x - half, x + half)
                frame_ax.set_ylim(y + half, y - half)
        self._request_ui_refresh("standard-actions")

    def _focus_current_uncertain_suggestion(self) -> None:
        """Handle the focus current uncertain suggestion helper flow."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        self._focus_suggestion(current)
        self._status_info(
            f"Suggestion {self._suggestion_cursor + 1}/{len(ranked)} score={float(current.score):.3f}",
            timeout_ms=2500,
            source="standard.suggestion_focus",
        )
        self._refresh_review_queue_panel()

    def _next_uncertain_suggestion(self) -> None:
        """Handle the next uncertain suggestion helper flow."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = (int(getattr(self, "_suggestion_cursor", 0)) + 1) % len(ranked)
        self._focus_current_uncertain_suggestion()

    def _prev_uncertain_suggestion(self) -> None:
        """Handle the prev uncertain suggestion helper flow."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = (int(getattr(self, "_suggestion_cursor", 0)) - 1) % len(ranked)
        self._focus_current_uncertain_suggestion()

    def _schedule_suggestion_decision_followup(self, *, refresh_table: bool, run_qc: bool) -> None:
        """Defer review follow-up work so accept/reject feels responsive."""
        def _run() -> None:
            """Run run for the current workflow."""
            if refresh_table:
                self._refresh_table()
            self._request_ui_refresh("standard-actions")
            if run_qc:
                self._schedule_qc_validation(self.primary_image.id)
            self._refresh_assist_warmup_panel()
            self._focus_current_uncertain_suggestion()

        QtCore.QTimer.singleShot(0, _run)

    def _accept_current_uncertain_suggestion(self) -> None:
        """Handle the accept current uncertain suggestion helper flow."""
        if not self._ensure_annotation_write_context_confirmed("Accept current suggestion"):
            return
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        if not self._ensure_suggestion_accept_allowed(
            current,
            action_label="Accept current suggestion",
            source="standard.suggestion_focus",
        ):
            return

        if self._interactive_learning_enabled():
            self._interactive_learning_model.add_example(current, accepted=True)

        cmd = AcceptSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self._note_annotation_edit(self.primary_image.id)
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            if bool(getattr(self, "_timed_session_active", False)):
                self._timed_session_accepts = int(getattr(self, "_timed_session_accepts", 0)) + 1
                self._timed_session_points = int(getattr(self, "_timed_session_points", 0)) + 1
            self._schedule_suggestion_decision_followup(refresh_table=True, run_qc=True)

    def _accept_and_next_uncertain_suggestion(self) -> None:
        """Mirror keyboard cadence A then N for mixed-input review workflows."""
        if not self._ensure_annotation_write_context_confirmed("Accept current suggestion"):
            return
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._accept_current_uncertain_suggestion()
        self._next_uncertain_suggestion()

    def _reject_current_uncertain_suggestion(self) -> None:
        """Handle the reject current uncertain suggestion helper flow."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]

        if self._interactive_learning_enabled():
            self._interactive_learning_model.add_example(current, accepted=False)

        cmd = RejectSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            if bool(getattr(self, "_timed_session_active", False)):
                self._timed_session_rejects = int(getattr(self, "_timed_session_rejects", 0)) + 1
            self._schedule_suggestion_decision_followup(refresh_table=False, run_qc=False)
