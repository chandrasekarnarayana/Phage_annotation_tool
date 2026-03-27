"""Assist-context helpers extracted from the main actions mixin.

This module keeps suggestion freshness and assist-context bookkeeping separate
from the broader menu/dialog action surface.
"""

from __future__ import annotations

import time
from typing import Optional

from phage_annotator.core.annotation import PointSuggestion


class AssistContextMixin:
    """Mixin for suggestion freshness and assist-context tracking."""

    def _format_age_short(self, seconds: float) -> str:
        """Return compact age string for status labels."""
        age = max(0.0, float(seconds))
        if age < 60.0:
            return f"{int(round(age))}s"
        if age < 3600.0:
            return f"{int(round(age / 60.0))} min"
        return f"{age / 3600.0:.1f} h"

    def _suggestion_freshness_state(
        self,
        image_id: Optional[int] = None,
        suggestions: Optional[list[PointSuggestion]] = None,
    ) -> dict:
        """Return freshness metadata for pending suggestions on an image."""
        target_id = int(self.primary_image.id if image_id is None else image_id)
        rows = list(self.suggestions.get(target_id, [])) if suggestions is None else list(suggestions)
        ts_vals = []
        for row in rows:
            ts = dict(getattr(row, "meta", {}) or {}).get("generated_at_ts")
            if ts is None:
                continue
            try:
                ts_vals.append(float(ts))
            except Exception:
                continue
        if not ts_vals:
            return {
                "has_suggestions": bool(rows),
                "has_timestamp": False,
                "age_seconds": None,
                "age_text": "n/a",
                "is_stale": False,
                "reason": "",
            }
        latest_gen_ts = max(ts_vals)
        age_seconds = max(0.0, float(time.time()) - latest_gen_ts)
        by_image = getattr(self, "_annotation_edit_ts_by_image", {}) or {}
        last_edit_ts = float(by_image.get(target_id, 0.0))
        is_stale = last_edit_ts > latest_gen_ts
        reason = "Edits happened after suggestion generation." if is_stale else ""
        return {
            "has_suggestions": bool(rows),
            "has_timestamp": True,
            "age_seconds": age_seconds,
            "age_text": self._format_age_short(age_seconds),
            "is_stale": bool(is_stale),
            "reason": reason,
        }

    def _effective_assist_context_parts(
        self,
        suggestions: Optional[list[PointSuggestion]] = None,
    ) -> dict[str, str]:
        """Return compact effective assist context components for trust-critical display."""
        projection_txt = "raw"
        if getattr(self, "projection_selector", None) is not None:
            try:
                p_name, p_axis = self.projection_selector.current_selection()
                if str(p_name).strip().lower() == "raw":
                    p_name = "source frame"
                projection_txt = f"{p_name} ({p_axis})"
            except Exception:
                projection_txt = "source frame"
        scope = "stack" if str(getattr(self, "annotation_scope", "current")) == "all" else "slice"
        target = str(getattr(self, "annotate_target", "frame"))
        strategy = str(getattr(self, "_suggestion_strategy", "current_view"))
        preset = str(getattr(self, "_active_evidence_preset_name", "custom"))
        freshness = self._suggestion_freshness_state(self.primary_image.id, suggestions)
        stale_txt = "stale" if freshness.get("is_stale", False) else "fresh"
        return {
            "strategy": strategy,
            "preset": preset,
            "projection": projection_txt,
            "scope": scope,
            "target": target,
            "stale": stale_txt,
        }

    def _effective_assist_context_line(
        self,
        suggestions: Optional[list[PointSuggestion]] = None,
    ) -> str:
        """Build immutable one-line context summary for status/review surfaces."""
        parts = self._effective_assist_context_parts(suggestions)
        return (
            f"Strategy={parts['strategy']} | Preset={parts['preset']} | Projection={parts['projection']} | "
            f"Scope={parts['scope']} | Target={parts['target']} | State={parts['stale']}"
        )

    def _remember_generation_context(self, suggestions: Optional[list[PointSuggestion]] = None) -> None:
        """Persist context snapshot at suggestion-generation time for delta notices."""
        parts = self._effective_assist_context_parts(suggestions)
        self._last_generation_context_signature = dict(parts)
        self._last_generation_context_text = self._effective_assist_context_line(suggestions)
        self._last_assist_context_delta_text = ""

    def _maybe_emit_assist_context_delta(self, source: str) -> None:
        """Emit concise context-delta hint when effective generation context changed."""
        last = dict(getattr(self, "_last_generation_context_signature", {}) or {})
        if not last:
            return
        now = self._effective_assist_context_parts()
        watched_keys = ("strategy", "preset", "projection")
        changed = [key for key in watched_keys if str(last.get(key, "")) != str(now.get(key, ""))]
        if not changed:
            return
        delta = ", ".join(f"{key}: {last.get(key)} -> {now.get(key)}" for key in changed)
        text = f"Assist context changed ({source}): {delta}"
        self._last_assist_context_delta_text = text
        self._status_info(text, timeout_ms=3000, source="assist.context")
        self._append_assist_change_log("context_delta", source=source, delta=delta)
        self._refresh_assist_warmup_panel()

    def _append_assist_change_log(self, event: str, **details) -> None:
        """Append assist context log entries for reproducibility and export."""
        payload = {"event": str(event), "details": dict(details), "ts": float(time.time())}
        if hasattr(self.controller, "append_audit_event"):
            self.controller.append_audit_event("assist_change", **payload)
        if hasattr(self, "_append_log"):
            self._append_log(f"[ASSIST] {event}: {details}")
