"""Extracted method group 3 for TableStatusMixin."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
try:
    from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui
except ImportError:  # pragma: no cover - exercised in headless CI/test envs
    class _MissingQtWidgets:
        def __getattr__(self, name: str) -> object:
            """Delegate unknown attribute access to the wrapped value."""
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



class SourceProtocolsOverlaysMixin:
    """Method group 3 extracted from TableStatusMixin."""

    def _on_table_selection(self) -> None:
        """Handle the on table selection helper flow."""
        logger = get_panel_logger("annotation_table")
        if self._block_table:
            return
        selected_ids = set()
        selected_annotations = []
        selected_suggestions = []
        if self.annot_table.selectionModel() is not None:
            for idx in self.annot_table.selectionModel().selectedRows():
                kp = self._keypoint_for_table_row(idx.row())
                if kp is not None:
                    selected_ids.add(str(kp.annotation_id))
                    selected_annotations.append({
                        "annotation_id": str(kp.annotation_id),
                        "label": str(kp.label),
                        "t": int(kp.t),
                        "z": int(kp.z),
                    })
                else:
                    suggestion = self._suggestion_for_table_row(idx.row())
                    if suggestion is not None:
                        self._selected_suggestion_id = str(getattr(suggestion, "suggestion_id", ""))
                        selected_suggestions.append({
                            "suggestion_id": self._selected_suggestion_id,
                            "score": float(getattr(suggestion, "score", 0.0)),
                        })
                        self._focus_suggestion(suggestion)
                        self._refresh_suggestion_explain_panel(suggestion)
        
        logger.log_action(
            "table_selection_changed",
            annotation_count=len(selected_annotations),
            suggestion_count=len(selected_suggestions),
            annotation_ids=selected_annotations,
            suggestion_ids=selected_suggestions,
        )
        
        self._selected_annotation_ids = selected_ids
        self._request_ui_refresh("table-status", table=True)
    def _on_table_item_changed(self, item: "QtWidgets.QTableWidgetItem") -> None:
        """Handle the on table item changed helper flow."""
        if self._block_table:
            return
        row = item.row()
        col = item.column()
        kp = self._keypoint_for_table_row(row)
        if kp is None:
            return
        text = item.text()
        try:
            new_meta = dict(kp.meta)
            new_kp = Keypoint(
                kp.image_id,
                kp.image_name,
                kp.t,
                kp.z,
                kp.y,
                kp.x,
                kp.label,
                source=str(getattr(kp, "source", "manual")),
                meta=new_meta,
                modality_idx=kp.modality_idx,
                annotation_context=getattr(kp, "annotation_context", ""),
            )
            new_kp.annotation_id = kp.annotation_id
            if col == 1:
                new_kp.label = text
            elif col == 2:
                new_kp.t = int(text)
            elif col == 3:
                new_kp.z = int(text)
            elif col == 4:
                new_kp.x = float(text)
            elif col == 5:
                new_kp.y = float(text)
            elif col == 6:
                new_kp.source = str(text or "manual")
            elif col == 7:
                new_kp.status = str(text or "active")
            elif col == 8:
                new_kp.confidence = None if not str(text).strip() else float(text)
            elif col == 10:
                new_kp.roi_name = str(text)
            elif col == 11:
                new_kp.notes = str(text)
            else:
                return
        except ValueError:
            return
        self.controller.update_annotation(kp.image_id, kp, new_kp)
        self._mark_dirty()
        self._refresh_table()
        self._request_ui_refresh("table-status", table=True)
    def _delete_selected_annotations(self) -> None:
        """Delete selected annotations with confirmation (P3.3)."""
        if self.annot_table.selectionModel() is None:
            return
        rows = sorted({idx.row() for idx in self.annot_table.selectionModel().selectedRows()})
        if not rows:
            return
        removed: List[Keypoint] = []
        for row in reversed(rows):
            kp = self._keypoint_for_table_row(row)
            if kp is not None:
                removed.append(kp)
        if not removed:
            return
        # Confirmation dialog (P3.3)
        if self._settings.value("confirmDeleteAnnotations", True, type=bool):
            count = len(removed)
            reply = QtWidgets.QMessageBox.question(
                self,
                "Delete Annotations",
                f"Delete {count} annotation{'s' if count != 1 else ''}?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        logger = get_panel_logger("annotate")
        by_image = {}
        for kp in removed:
            by_image.setdefault(int(kp.image_id), []).append(kp)
        for image_id, rows in by_image.items():
            self.controller.delete_annotations(int(image_id), rows)
        logger.log_action(
            "delete_selected_annotations",
            count=len(removed),
            by_image_id={str(img_id): len(pts) for img_id, pts in by_image.items()},
            labels=[str(kp.label) for kp in removed],
        )
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._request_ui_refresh("table-status", table=True)
        self._update_status()
        self._mark_dirty()
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
