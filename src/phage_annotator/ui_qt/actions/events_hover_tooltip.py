"""Extracted method group 3 for EventsMixin."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.keyboard_events import KeyboardEventsMixin

logger = logging.getLogger(__name__)



class EventsHoverTooltipMixin:
    """Method group 3 extracted from EventsMixin."""

    def _update_suggestion_hover_tooltip(self, event) -> None:
        """Show suggestion details on hover near a visible suggestion marker."""
        inaxes = getattr(event, "inaxes", None)
        if inaxes is None or getattr(event, "xdata", None) is None or getattr(event, "ydata", None) is None:
            QtWidgets.QToolTip.hideText()
            return
        panel_axes = []
        if getattr(self, "renderer", None) is not None:
            panel_axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if inaxes not in panel_axes:
            QtWidgets.QToolTip.hideText()
            return
        if not bool(getattr(self, "_show_suggestion_overlay", True)):
            QtWidgets.QToolTip.hideText()
            return

        suggestions = []
        if hasattr(self, "_visible_suggestions"):
            suggestions = list(self._visible_suggestions())
        if not suggestions:
            QtWidgets.QToolTip.hideText()
            return

        hover_radius = max(4.0, float(getattr(self, "click_radius_px", 6.0)) * 1.5)
        best = None
        best_dist = None
        for suggestion in suggestions:
            sx, sy = self._to_display_coords(inaxes, float(suggestion.x), float(suggestion.y))
            dx = float(event.xdata) - float(sx)
            dy = float(event.ydata) - float(sy)
            dist = float((dx * dx + dy * dy) ** 0.5)
            if dist > hover_radius:
                continue
            if best is None or dist < float(best_dist):
                best = suggestion
                best_dist = dist
        if best is None:
            QtWidgets.QToolTip.hideText()
            return

        meta = dict(getattr(best, "meta", {}) or {})
        confidence_available = bool(meta.get("confidence_available", False))
        generator_score = float(
            meta.get("generator_score", getattr(best, "score", getattr(best, "confidence", 0.0)))
        )
        state_txt = "Heuristic"
        if hasattr(self, "_canonical_assist_state"):
            state_txt = assist_state_label(self._canonical_assist_state([best]))
        if confidence_available:
            p_accept = float(meta.get("p_accept", getattr(best, "score", 0.0)))
            if p_accept >= 0.75:
                triage = "likely accept"
            elif p_accept >= 0.5:
                triage = "needs review"
            else:
                triage = "unlikely accept"
            lines = [
                f"Generator score: {generator_score:.2f}",
                f"Acceptance likelihood (p_accept): {p_accept:.2f} ({triage})",
                "p_accept predicts acceptance behavior, not ground-truth correctness.",
                f"Assist state: {state_txt}",
            ]
        else:
            lines = [
                f"Generator score: {generator_score:.2f}",
                "Acceptance likelihood (p_accept): not available (heuristic only)",
                f"Assist state: {state_txt}",
            ]
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "\n".join(lines), self.canvas)
