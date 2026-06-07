"""Annotation table, status bar, and view stats helpers."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
try:
    from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui
except ImportError:  # pragma: no cover - exercised in headless CI/test envs
    class _MissingQtWidgets:
        def __getattr__(self, name: str) -> object:
            """Document the getattr flow."""
            raise ImportError(
                "Qt bindings are required for GUI table/status operations."
            )

    QtWidgets = _MissingQtWidgets()
    QtCore = _MissingQtWidgets()
    QtGui = _MissingQtWidgets()

from phage_annotator.ui_qt.services.panel_logging import get_panel_logger

from phage_annotator.annotation.core import Keypoint
from phage_annotator.tools import Tool
from phage_annotator.ui_qt.assist_state import (
    AssistState,
    assist_state_color,
    assist_state_label,
    infer_assist_state,
)
from phage_annotator.ui_qt.services.status import StatusText
from phage_annotator.ui_qt.services.status_derived import (
    DerivedStatusSnapshot,
    build_status_snapshot,
)

class TableStatusBarMixin:
    """Status bar, task counts, and assist state display."""

    def _canonical_assist_state(self, suggestions: Optional[List[object]] = None) -> AssistState:
        """Resolve assist-state from one canonical inference path."""
        rows = list(suggestions) if suggestions is not None else list(
            getattr(self, "suggestions", {}).get(self.primary_image.id, [])
        )
        annotation_space = str(
            getattr(self.controller.session_state, "annotation_space", "stack")
            if getattr(self, "controller", None) is not None
            else "stack"
        )
        return infer_assist_state(
            controller=getattr(self, "controller", None),
            image_name=str(getattr(self.primary_image, "name", "unknown")),
            annotation_space=annotation_space,
            suggestions=rows,
        )

    def _assist_context_need_count(self, suggestions: Optional[List[object]] = None) -> int:
        """Return remaining labels needed for current assist context."""
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "assist_need_breakdown"):
            return 0
        rows = list(suggestions) if suggestions is not None else list(
            getattr(self, "suggestions", {}).get(self.primary_image.id, [])
        )
        annotation_space = str(getattr(controller.session_state, "annotation_space", "stack"))
        if rows:
            context_key = controller._context_key(
                suggestion=rows[0], annotation_space=annotation_space
            )
        else:
            context_key = f"{self.primary_image.name}|{annotation_space}|current_view"
        breakdown = controller.assist_need_breakdown(
            annotation_space=annotation_space,
            context_key=context_key,
        )
        return int(
            max(
                breakdown.get("need_total", 0),
                breakdown.get("need_pos", 0),
                breakdown.get("need_neg", 0),
                breakdown.get("need_context", 0),
            )
        )

    def _style_assist_state_label(
        self,
        widget: Optional["QtWidgets.QLabel"],
        state: AssistState,
        prefix: str = "Assist: ",
        suffix: str = "",
    ) -> None:
        """Apply canonical assist-state wording and color to a label."""
        if widget is None:
            return
        widget.setText(f"{prefix}{assist_state_label(state)}{suffix}")
        widget.setStyleSheet(
            "font-weight: 600; "
            f"color: {assist_state_color(state)};"
        )

    def _bottom_task_counts(self) -> tuple[int, int, int]:
        """Return counts for task-specific bottom tabs: (qc_issues, results_rows, log_alerts)."""
        qc_count = 0
        qc_state = getattr(self, "qc_state", None)
        if qc_state is not None:
            qc_count = int(len(getattr(qc_state, "issues", []) or []))
        results_rows = 0
        results_widget = getattr(self, "results_widget", None)
        if results_widget is not None and getattr(results_widget, "table", None) is not None:
            results_rows = int(results_widget.table.rowCount())
        log_alerts = 0
        all_logs = list(getattr(self, "_all_logs", []) or [])
        for row in all_logs[-200:]:
            if isinstance(row, dict):
                level = str(row.get("severity", "")).upper()
                txt = f"{row.get('summary', '')}\n{row.get('details', '')}".upper()
            else:
                level = ""
                txt = str(row).upper()
            if level in {"ERROR", "WARNING"} or "ERROR" in txt or "WARNING" in txt or "[EXCEPTION]" in txt:
                log_alerts += 1
        return qc_count, results_rows, log_alerts

    def _update_bottom_task_panels(self) -> None:
        """Auto-collapse bottom panel by default; expand only for non-empty task tabs."""
        qc_count, results_rows, log_alerts = self._bottom_task_counts()
        has_qc = qc_count > 0
        if str(getattr(self, "_active_layout_preset", "")) == "Assist Expert":
            has_qc = True
        has_results = results_rows > 0
        has_logs = log_alerts > 0
        if hasattr(self, "set_panel_visible"):
            self.set_panel_visible("results", has_results, source="bottom_task_auto")
            # Keep QC/Diagnostics opt-in to avoid surprise panel popups.
            if has_qc and getattr(self, "dock_qc_issues", None) is not None and self.dock_qc_issues.isVisible():
                self.set_panel_visible("qc_issues", True, source="bottom_task_auto")
            if has_logs and getattr(self, "dock_logs", None) is not None and self.dock_logs.isVisible():
                self.set_panel_visible("logs", True, source="bottom_task_auto")
        # Keep task-specific auto-layout restricted to bottom task docks only.
        # QC/Diagnostics are managed as right-sidebar panels and should not be
        # re-tabified from status updates.
        dock_results = getattr(self, "dock_results", None)
        dock_qc = getattr(self, "dock_qc_issues", None)
        dock_logs = getattr(self, "dock_logs", None)
        # Collapse bottom to slim footprint when empty; expand modestly when active.
        # Only resize docks that are actually in the bottom area.
        bottom_docks = [
            d
            for d in (dock_results, dock_qc, dock_logs)
            if d is not None
            and d.isVisible()
            and self.dockWidgetArea(d) == QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
        ]
        if bottom_docks:
            try:
                target = max(64, int(max(1, self.height()) * 0.12))
                self.resizeDocks(bottom_docks, [target for _ in bottom_docks], QtCore.Qt.Orientation.Vertical)
            except Exception:
                pass

    def _update_status(self) -> None:
        """Build one derived status snapshot and let the presenter render it."""
        snapshot = self._build_status_snapshot()
        self._apply_menu_action_state(snapshot)
        self._apply_legacy_status_snapshot(snapshot)
        status_service = getattr(self, "status_service", None)
        if status_service is not None:
            throttle_ms = 120 if bool(getattr(self, "_playback_mode", False) or getattr(self, "_interactive", False)) else 0
            status_service.set_derived_status(snapshot.model, throttle_ms=throttle_ms)
        if hasattr(self, "_refresh_review_qc_page_summary"):
            self._refresh_review_qc_page_summary()
        if hasattr(self, "_refresh_advanced_page_summary"):
            self._refresh_advanced_page_summary()
        self._update_bottom_task_panels()
        if self.tool_label is not None and self.tool_router is not None:
            self.tool_label.setText(f"Tool: {self._tool_label(self.tool_router.tool)}")
        if self.cache_stats_label is not None:
            self.cache_stats_label.setText(
                f"Cache: {snapshot.cache_mb} MB | Items: {snapshot.cache_items}"
            )
        self._update_buffer_stats()

    def _build_status_snapshot(self) -> DerivedStatusSnapshot:
        """Build a structured status snapshot from current GUI/session state."""
        return build_status_snapshot(self)

    def _apply_menu_action_state(self, snapshot: DerivedStatusSnapshot) -> None:
        """Keep menu actions aligned with the current derived session/view state."""
        for attr, enabled in dict(getattr(snapshot, "action_enabled", {}) or {}).items():
            action = getattr(self, attr, None)
            if action is None:
                continue
            try:
                action.setEnabled(bool(enabled))
                base_tip = str(action.property("baseStatusTip") or action.statusTip() or "").strip()
                base_tooltip = str(action.property("baseToolTip") or action.toolTip() or "").strip()
                disabled_reason = str(
                    dict(getattr(snapshot, "action_disabled_reason", {}) or {}).get(attr, "")
                ).strip()
                if enabled:
                    if base_tip:
                        action.setStatusTip(base_tip)
                    if base_tooltip:
                        action.setToolTip(base_tooltip)
                else:
                    reason = disabled_reason or "This action is not available in the current context."
                    if base_tip:
                        action.setStatusTip(f"{base_tip} Disabled: {reason}")
                    else:
                        action.setStatusTip(reason)
                    action.setToolTip(reason)
            except Exception:
                continue
