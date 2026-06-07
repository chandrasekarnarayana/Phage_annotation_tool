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

class ActionsAnnotationContextMixin2:
    """Mixin for annotation write context guards, suggestion review, and annotation management."""

    # ── Annotation context guards ──────────────────────────────────────────

    def _current_annotation_write_context(self) -> tuple[str, str]:
        """Return the current write context as (context_key, panel_key)."""
        context = (
            dict(self.controller.current_annotation_context() or {})
            if hasattr(self.controller, "current_annotation_context")
            else {}
        )
        return (
            str(context.get("context_key", "img:0|panel:frame|space:stack")),
            str(context.get("panel_key", getattr(self, "annotate_target", "frame"))),
        )

    def _mark_annotation_context_changed(self, reason: str) -> None:
        """Mark write context as changed and requiring explicit confirmation."""
        self._annotation_write_context_pending = True
        self._annotation_context_change_reason = str(reason or "context changed")
        self._annotation_write_context_pending_value = self._current_annotation_write_context()
        self._update_status()

    def _is_annotation_context_guard_pending(self) -> bool:
        """True when write actions should request confirmation before commit."""
        pending = bool(getattr(self, "_annotation_write_context_pending", False))
        confirmed = getattr(self, "_annotation_write_context_confirmed", None)
        current = self._current_annotation_write_context()
        if pending and isinstance(confirmed, tuple) and tuple(confirmed) == current:
            self._annotation_write_context_pending = False
            self._annotation_context_change_reason = ""
            self._annotation_write_context_pending_value = None
            pending = False
        if pending:
            return True
        return confirmed is not None and tuple(confirmed) != current

    def _ensure_annotation_write_context_confirmed(self, action_label: str) -> bool:
        """Prompt before write if annotation context changed since last confirmation."""
        current = self._current_annotation_write_context()
        confirmed = getattr(self, "_annotation_write_context_confirmed", None)
        needs_confirm = self._is_annotation_context_guard_pending()
        if not needs_confirm:
            self._annotation_write_context_confirmed = current
            return True

        reason = str(
            getattr(self, "_annotation_context_change_reason", "")
            or "annotation context changed"
        )
        prev_txt = (
            f"{confirmed[0]} / {confirmed[1]}"
            if isinstance(confirmed, tuple) and len(confirmed) == 2
            else "unknown"
        )
        cur_txt = f"{current[0]} / {current[1]}"
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Confirm Annotation Write Context")
        msg.setText(f"{action_label} will write annotations in a new context.")
        msg.setInformativeText(
            f"Previous confirmed context: {prev_txt}\n"
            f"Current context: {cur_txt}\n"
            f"Reason: {reason}\n\n"
            "Proceed with this write?"
        )
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel
        )
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        if msg.exec() != QtWidgets.QMessageBox.Yes:
            self._status_warning(
                "Write cancelled: context confirmation required.",
                timeout_ms=3000,
                source="standard.write_context",
            )
            return False
        self._annotation_write_context_confirmed = current
        self._annotation_write_context_pending = False
        self._annotation_context_change_reason = ""
        self._annotation_write_context_pending_value = None
        self._update_status()
        return True
