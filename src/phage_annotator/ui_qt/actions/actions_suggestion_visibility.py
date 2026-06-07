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

class ActionsSuggestionVisibilityMixin:
    """Mixin for annotation write context guards, suggestion review, and annotation management."""

    # ── Annotation context guards ──────────────────────────────────────────

    def _visible_suggestions(self) -> list[PointSuggestion]:
        """Return suggestions visible on active image and T/Z slice."""
        visible = self.controller.get_visible_suggestions(
            self.primary_image.id,
            t_index=int(self.t_slider.value()),
            z_index=int(self.z_slider.value()),
            min_score=float(getattr(self, "_suggestion_score_threshold", 0.0)),
        )
        return self._filter_suggestions_to_active_roi(visible)

    def _suggestions_for_current_tz(self) -> list[PointSuggestion]:
        """Return all suggestions for active image and current T/Z, including decided history rows."""
        visible = self.controller.get_slice_suggestions(
            int(self.primary_image.id),
            t_index=int(self.t_slider.value()),
            z_index=int(self.z_slider.value()),
        )
        return self._filter_suggestions_to_active_roi(visible)

    def _filter_suggestions_to_active_roi(
        self, suggestions: list[PointSuggestion]
    ) -> list[PointSuggestion]:
        """Handle the filter suggestions to active roi helper flow."""
        if str(getattr(self, "roi_shape", "none")) == "none":
            return list(suggestions or [])
        return [
            suggestion
            for suggestion in list(suggestions or [])
            if self._point_in_roi(float(getattr(suggestion, "x", 0.0)), float(getattr(suggestion, "y", 0.0)))
        ]

    def _candidate_suggestion_strategies(self) -> list[str]:
        """Return available suggestion strategies for the current context."""
        options = [
            "current_view",
            "raw",
            "corrected",
            "mean_projection",
            "max_projection",
            "evidence_consensus",
            "evidence_contradiction",
        ]
        image = getattr(self, "primary_image", None)
        if image is not None and int(getattr(image, "channel_count", 1)) >= 2:
            options.extend(
                [
                    "channel_a_only",
                    "channel_b_only",
                    "channel_a_peak_b_low",
                    "channel_b_peak_a_low",
                ]
            )
        return options

    def _toggle_suggestions_overlay(self, checked: bool) -> None:
        """Toggle suggestion overlay rendering."""
        visible = bool(checked)
        self._show_suggestion_overlay = visible
        if getattr(self, "review_queue_panel", None) is not None and hasattr(
            self.review_queue_panel, "show_suggestions_chk"
        ):
            self.review_queue_panel.show_suggestions_chk.blockSignals(True)
            self.review_queue_panel.show_suggestions_chk.setChecked(visible)
            self.review_queue_panel.show_suggestions_chk.blockSignals(False)
        action = getattr(self, "toggle_suggestions_overlay_act", None)
        if action is not None and bool(action.isChecked()) != visible:
            action.blockSignals(True)
            action.setChecked(visible)
            action.blockSignals(False)
        self._request_ui_refresh("standard-actions")

    def _visible_suggestions_uncertain_first(self) -> list[PointSuggestion]:
        """Visible suggestions ranked by uncertainty (lowest score first)."""
        return sorted(
            self._visible_suggestions(),
            key=lambda s: float(
                dict(getattr(s, "meta", {}) or {}).get(
                    "p_accept", getattr(s, "score", getattr(s, "confidence", 0.0))
                )
            ),
        )

    def _review_throughput_snapshot(self) -> tuple[str, float]:
        """Return compact throughput text and avg sec/decision for current session."""
        return assist_review.review_throughput_snapshot(self)

    def _calibration_sparkline_text(self) -> str:
        """Return tiny reliability sparkline from p_accept bins."""
        return assist_review.calibration_sparkline_text(self)

    def _review_queue_progress_counts(self) -> tuple[int, int]:
        """Return (processed, total) counts for current image and T/Z context."""
        return assist_review.review_queue_progress_counts(self)
