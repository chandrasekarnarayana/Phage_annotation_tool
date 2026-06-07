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

class ActionsReviewQueueMixin:
    """Mixin for annotation write context guards, suggestion review, and annotation management."""

    # ── Annotation context guards ──────────────────────────────────────────

    def _refresh_review_queue_panel(self) -> None:
        """Refresh right-dock assisted review queue details and progress."""
        assist_review.refresh_review_queue_panel(self)

    def _on_review_queue_row_selected(self, row: int) -> None:
        """Handle row selection from suggested-points table."""
        assist_review.on_review_queue_row_selected(self, row)

    def _annotation_exists_for_suggestion(self, image_id: int, suggestion_id: str) -> bool:
        """Return True if an annotation linked to suggestion_id already exists."""
        sid = str(suggestion_id)
        rows = list(getattr(self.controller.session_state, "annotations", {}).get(int(image_id), []))
        for ann in rows:
            meta = dict(getattr(ann, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                return True
        return False

    def _remove_annotation_for_suggestion(self, image_id: int, suggestion_id: str) -> int:
        """Remove annotations linked to suggestion_id and return count removed."""
        return int(self.controller.remove_annotations_for_suggestion(int(image_id), str(suggestion_id)))

    def _append_annotation_from_suggestion(self, suggestion: PointSuggestion) -> None:
        """Create a committed annotation from suggestion if it does not already exist."""
        self.controller.append_annotation_from_suggestion(suggestion)

    def _set_selected_suggestion_decision(self, suggestion_id: str, status: str) -> None:
        """Set selected suggestion decision any time: accepted/rejected/proposed."""
        assist_review.set_selected_suggestion_decision(self, suggestion_id, status)

    def _confirm_suggestion_redecision(self, target_status: str) -> bool:
        """Confirm destructive re-decision from accepted to non-accepted state."""
        return assist_review.confirm_suggestion_redecision(self, target_status)
