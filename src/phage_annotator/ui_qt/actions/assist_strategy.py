"""Suggestion-strategy UI helpers extracted from the main actions mixin."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets


class AssistStrategyMixin:
    """Mixin for suggestion-strategy selection and status-bar synchronization."""

    def _sync_status_strategy_selector(self) -> None:
        """Keep status-bar strategy selector in sync with available/current strategy."""
        combo = getattr(self, "status_strategy_combo", None)
        if combo is None:
            return
        options = self._candidate_suggestion_strategies()
        current = str(getattr(self, "_suggestion_strategy", "current_view"))
        combo.blockSignals(True)
        combo.clear()
        for opt in options:
            combo.addItem(self._strategy_display_label(opt), opt)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _strategy_display_label(self, strategy: str) -> str:
        """Return user-facing label for strategy keys while preserving stable internal ids."""
        key = str(strategy or "").strip()
        labels = {
            "raw": "Source Frame",
            "current_view": "Current View",
            "corrected": "Corrected",
            "mean_projection": "Mean Projection",
            "evidence_consensus": "Evidence Consensus",
            "evidence_contradiction": "Evidence Contradiction",
        }
        return str(labels.get(key, key.replace("_", " ").title()))

    def _strategy_from_display_label(self, strategy: str) -> str:
        """Map display labels back to canonical strategy keys."""
        text = str(strategy or "").strip()
        if not text:
            return "current_view"
        options = self._candidate_suggestion_strategies()
        if text in options:
            return text
        for option in options:
            if self._strategy_display_label(option).lower() == text.lower():
                return option
        return text

    def _set_suggestion_strategy(self, strategy: str, *, source: str = "ui") -> None:
        """Set suggestion strategy from any UI surface."""
        selected = self._strategy_from_display_label(str(strategy or "current_view"))
        strategies = self._candidate_suggestion_strategies()
        if selected not in strategies:
            selected = strategies[0] if strategies else "current_view"
        self._suggestion_strategy = selected
        self.controller.set_suggestion_strategy_value(self._suggestion_strategy)
        self._sync_status_strategy_selector()
        self._status_info(
            f"Suggestion strategy ({source}): {self._strategy_display_label(self._suggestion_strategy)}.",
            source="assist.strategy",
        )
        self._append_assist_change_log(
            "strategy_changed",
            source=str(source),
            strategy=self._suggestion_strategy,
        )
        self._maybe_emit_assist_context_delta("strategy")
        self._refresh_assist_warmup_panel()

    def _select_suggestion_strategy_dialog(self) -> None:
        """Choose proposal strategy used by Suggest actions."""
        strategies = self._candidate_suggestion_strategies()
        current = str(getattr(self, "_suggestion_strategy", "current_view"))
        idx = strategies.index(current) if current in strategies else 0
        selected, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Suggest Points Using",
            "Strategy:",
            strategies,
            idx,
            False,
        )
        if not ok:
            return
        self._set_suggestion_strategy(str(selected), source="dialog")

    def _set_suggestion_score_threshold_dialog(self) -> None:
        """Set display threshold for proposal score."""
        current = float(getattr(self, "_suggestion_score_threshold", 0.0))
        value, ok = QtWidgets.QInputDialog.getDouble(
            self,
            "Show Suggestions With Score >= X",
            "Score threshold (0-1):",
            current,
            0.0,
            1.0,
            2,
        )
        if not ok:
            return
        self._suggestion_score_threshold = float(value)
        self.controller.set_suggestion_score_threshold_value(self._suggestion_score_threshold)
        self._request_ui_refresh("standard-actions")
        self._status_info(
            "Show suggestions with acceptance likelihood (p_accept) >= "
            f"{self._suggestion_score_threshold:.2f}; generator score is heuristic.",
            source="assist.strategy",
        )
        self._refresh_assist_warmup_panel()
