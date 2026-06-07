"""Extracted method group 2 for TableStatusMixin."""

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



class AnnotationTypesMixin:
    """Method group 2 extracted from TableStatusMixin."""

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
    def _on_auto_follow_table_changed(self, state: int) -> None:
        """Persist auto-follow preference and refresh table view."""
        enabled = bool(state)
        if hasattr(self, "_settings"):
            self._settings.setValue("annotationTableAutoFollow", enabled)
        if enabled:
            self.filter_current_chk.blockSignals(True)
            self.filter_current_chk.setChecked(True)
            self.filter_current_chk.blockSignals(False)
        self._refresh_table()
    def _populate_table(self) -> None:
        """Populate the table from current keypoints."""
        rows = self._current_table_rows()
        self._table_rows = list(rows)
        expected_columns = len(self._ANNOT_TABLE_HEADERS)
        if self.annot_table.columnCount() != expected_columns:
            self.annot_table.setColumnCount(expected_columns)
            self.annot_table.setHorizontalHeaderLabels(self._ANNOT_TABLE_HEADERS)
        sorting = bool(self.annot_table.isSortingEnabled())
        if sorting:
            self.annot_table.setSortingEnabled(False)
        self.annot_table.blockSignals(True)
        self.annot_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            id_item = QtWidgets.QTableWidgetItem(str(row["id"])[:8])
            id_item.setData(QtCore.Qt.ItemDataRole.UserRole, {"kind": row["kind"], "id": row["id"]})
            if row["kind"] != "annotation":
                id_item.setFlags(id_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.annot_table.setItem(row_idx, 0, id_item)
            values = [
                str(row["label"]),
                str(row["t"]),
                str(row["z"]),
                f"{float(row['x']):.2f}",
                f"{float(row['y']):.2f}",
                str(row["source"]),
                str(row["status"]),
                "" if row["confidence"] in (None, "") else f"{float(row['confidence']):.4f}",
                str(row["candidate_class"] or ""),
                str(row["roi"] or ""),
                str(row["notes"] or ""),
            ]
            for col_idx, value in enumerate(values, start=1):
                item = QtWidgets.QTableWidgetItem(value)
                if row["kind"] != "annotation" or col_idx in (6, 8):
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if row["kind"] == "suggestion":
                    self._style_suggestion_table_item(item, row)
                self.annot_table.setItem(row_idx, col_idx, item)
            self._set_annotation_table_actions(row_idx, row)
        self.annot_table.blockSignals(False)
        self.annot_table.resizeColumnsToContents()
        if sorting:
            self.annot_table.setSortingEnabled(True)
    def _style_suggestion_table_item(self, item: "QtWidgets.QTableWidgetItem", row: dict) -> None:
        """Handle the style suggestion table item helper flow."""
        candidate_class = str(row.get("candidate_class", "")).strip().lower()
        status = str(row.get("status", "")).strip().lower()
        if status == "rejected":
            item.setForeground(QtCore.Qt.GlobalColor.gray)
        elif status == "accepted":
            item.setForeground(QtGui.QColor("#1565c0")) if hasattr(QtWidgets, "QTableWidget") else None
        elif candidate_class == "conflict":
            item.setBackground(QtGui.QColor("#ffebee"))
        elif candidate_class == "near_existing":
            item.setBackground(QtGui.QColor("#fff3e0"))
        else:
            item.setBackground(QtGui.QColor("#f5f5f5"))
    def _set_annotation_table_actions(self, row_idx: int, row: dict) -> None:
        """Set annotation table actions for the current workflow."""
        widget = QtWidgets.QWidget(self.annot_table)
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        if row["kind"] == "suggestion":
            accept_btn = QtWidgets.QToolButton(widget)
            accept_btn.setText("✓")
            accept_btn.setToolTip("Accept suggestion")
            reject_btn = QtWidgets.QToolButton(widget)
            reject_btn.setText("✕")
            reject_btn.setToolTip("Reject suggestion")
            jump_btn = QtWidgets.QToolButton(widget)
            jump_btn.setText("◎")
            jump_btn.setToolTip("Jump to suggestion")
            suggestion_id = str(row["id"])
            accept_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._set_selected_suggestion_decision(sid, "accepted"))
            reject_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._set_selected_suggestion_decision(sid, "rejected"))
            jump_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._jump_to_table_suggestion(sid))
            for btn in (accept_btn, reject_btn, jump_btn):
                layout.addWidget(btn)
        else:
            jump_btn = QtWidgets.QToolButton(widget)
            jump_btn.setText("◎")
            jump_btn.setToolTip("Jump to annotation")
            annotation_id = str(row["id"])
            jump_btn.clicked.connect(lambda _checked=False, aid=annotation_id: self._jump_to_table_annotation(aid))
            layout.addWidget(jump_btn)
        layout.addStretch(1)
        self.annot_table.setCellWidget(row_idx, 12, widget)
    def _keypoint_for_table_row(self, row: int) -> Optional[Keypoint]:
        """Resolve a keypoint from the currently visible table row using annotation id."""
        if row < 0:
            return None
        id_item = self.annot_table.item(int(row), 0)
        if id_item is None:
            return None
        payload = id_item.data(QtCore.Qt.ItemDataRole.UserRole) or {}
        if not isinstance(payload, dict) or payload.get("kind") != "annotation":
            return None
        ann_id = str(payload.get("id", "")).strip()
        for kp in self.annotations.get(self.primary_image.id, []):
            if str(kp.annotation_id) == ann_id:
                return kp
        return None
    def _focus_table_current_slice_row(self) -> None:
        """Auto-select and scroll to the first row matching current T/Z."""
        if not bool(getattr(self, "auto_follow_table_chk", None) and self.auto_follow_table_chk.isChecked()):
            return
        if self.annot_table.rowCount() <= 0:
            self.annot_table.clearSelection()
            return
        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        target_row = None
        for row in range(self.annot_table.rowCount()):
            t_item = self.annot_table.item(row, 2)
            z_item = self.annot_table.item(row, 3)
            if t_item is None or z_item is None:
                continue
            try:
                t_val = int(t_item.text())
                z_val = int(z_item.text())
            except ValueError:
                continue
            if t_val in (t_idx, -1) and z_val in (z_idx, -1):
                target_row = row
                break
        if target_row is None:
            self.annot_table.clearSelection()
            return
        self._block_table = True
        try:
            self.annot_table.selectRow(int(target_row))
            item = self.annot_table.item(int(target_row), 0)
            if item is not None:
                self.annot_table.scrollToItem(
                    item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter
                )
        finally:
            self._block_table = False
