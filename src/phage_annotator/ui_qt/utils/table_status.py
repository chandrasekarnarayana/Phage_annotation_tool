"""Annotation table, status bar, and view stats helpers."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
try:
    from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui
except ImportError:  # pragma: no cover - exercised in headless CI/test envs
    class _MissingQtWidgets:
        def __getattr__(self, name: str) -> object:
            raise ImportError(
                "Qt bindings are required for GUI table/status operations."
            )

    QtWidgets = _MissingQtWidgets()
    QtCore = _MissingQtWidgets()
    QtGui = _MissingQtWidgets()

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


class TableStatusMixin:
    """Mixin for annotation table and status rendering."""

    _ANNOT_TABLE_HEADERS = [
        "ID",
        "Label",
        "T",
        "Z",
        "X",
        "Y",
        "Source",
        "Status",
        "Confidence",
        "Candidate Class",
        "ROI",
        "Notes",
        "Actions",
    ]

    def _annotation_table_truth_columns_enabled(self) -> bool:
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "feature_enabled"):
            return False
        return bool(controller.feature_enabled("annotation_table_truth_columns", False))

    def _refresh_table(self) -> None:
        """Refresh table rows and keep selection focused for current T/Z when enabled."""
        self._populate_table()
        self._focus_table_current_slice_row()
        if hasattr(self, "_refresh_review_queue_panel"):
            self._refresh_review_queue_panel()

    def _annotation_table_mode(self) -> str:
        combo = getattr(self, "annotation_table_mode_combo", None)
        return str(combo.currentData() or "truth") if combo is not None else "truth"

    def _table_filter_value(self, attr: str) -> str:
        combo = getattr(self, attr, None)
        return str(combo.currentData() or "all") if combo is not None else "all"

    def _suggestion_for_table_row(self, row: int):
        if row < 0:
            return None
        id_item = self.annot_table.item(int(row), 0)
        if id_item is None:
            return None
        payload = id_item.data(QtCore.Qt.ItemDataRole.UserRole) or {}
        if not isinstance(payload, dict) or payload.get("kind") != "suggestion":
            return None
        suggestion_id = str(payload.get("id", ""))
        for suggestion in self._suggestions_for_current_tz():
            if str(getattr(suggestion, "suggestion_id", "")) == suggestion_id:
                return suggestion
        return None

    def _annotation_row_payload(self, kp: Keypoint) -> dict:
        meta = dict(getattr(kp, "meta", {}) or {})
        return {
            "kind": "annotation",
            "id": str(kp.annotation_id),
            "label": str(kp.label),
            "t": int(kp.t),
            "z": int(kp.z),
            "x": float(kp.x),
            "y": float(kp.y),
            "source": str(getattr(kp, "source", "manual")),
            "status": str(getattr(kp, "status", "active")),
            "confidence": getattr(kp, "confidence", None),
            "candidate_class": str(meta.get("candidate_class", "")),
            "roi": str(getattr(kp, "roi_name", "") or ""),
            "notes": str(getattr(kp, "notes", "") or ""),
            "object": kp,
        }

    def _suggestion_row_payload(self, suggestion) -> dict:
        meta = dict(getattr(suggestion, "meta", {}) or {})
        source_model = str(getattr(suggestion, "source_model", "assist"))
        source_modality = str(getattr(suggestion, "source_modality", "raw"))
        return {
            "kind": "suggestion",
            "id": str(getattr(suggestion, "suggestion_id", "")),
            "label": str(getattr(suggestion, "label", "")),
            "t": int(getattr(suggestion, "t", -1)),
            "z": int(getattr(suggestion, "z", -1)),
            "x": float(getattr(suggestion, "x", 0.0)),
            "y": float(getattr(suggestion, "y", 0.0)),
            "source": f"assist:{source_model}:{source_modality}",
            "status": str(getattr(suggestion, "status", "proposed")),
            "confidence": meta.get("p_accept", getattr(suggestion, "score", None)),
            "candidate_class": str(meta.get("candidate_class", "new")),
            "roi": str(getattr(suggestion, "roi_id", "") or ""),
            "notes": str(meta.get("notes", "") or ""),
            "object": suggestion,
        }

    def _apply_annotation_table_filters(self, rows: List[dict]) -> List[dict]:
        source_filter = self._table_filter_value("annotation_table_source_filter")
        status_filter = self._table_filter_value("annotation_table_status_filter")
        candidate_filter = self._table_filter_value("annotation_table_candidate_filter")
        roi_filter = self._table_filter_value("annotation_table_roi_filter")
        if self.filter_current_chk.isChecked():
            t = int(self.t_slider.value())
            z = int(self.z_slider.value())
            rows = [row for row in rows if int(row["t"]) in (t, -1) and int(row["z"]) in (z, -1)]
        if source_filter != "all":
            rows = [row for row in rows if str(row["source"]) == source_filter]
        if status_filter != "all":
            rows = [row for row in rows if str(row["status"]) == status_filter]
        if candidate_filter != "all":
            rows = [row for row in rows if str(row["candidate_class"] or "") == candidate_filter]
        if roi_filter == "current_frame":
            t = int(self.t_slider.value())
            z = int(self.z_slider.value())
            rows = [row for row in rows if int(row["t"]) in (t, -1) and int(row["z"]) in (z, -1)]
        elif roi_filter != "all":
            rows = [row for row in rows if str(row["roi"] or "") == roi_filter]
        return rows

    def _refresh_annotation_table_filters(self, rows: List[dict]) -> None:
        combos = [
            ("annotation_table_source_filter", "All sources", lambda row: str(row["source"] or "")),
            ("annotation_table_status_filter", "All status", lambda row: str(row["status"] or "")),
            ("annotation_table_candidate_filter", "All classes", lambda row: str(row["candidate_class"] or "")),
            ("annotation_table_roi_filter", "All ROI / frame", lambda row: str(row["roi"] or "")),
        ]
        for attr, label, getter in combos:
            combo = getattr(self, attr, None)
            if combo is None:
                continue
            current = str(combo.currentData() or "all")
            values = sorted({getter(row) for row in rows if getter(row)})
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(label, "all")
            if attr == "annotation_table_roi_filter":
                combo.addItem("Current frame", "current_frame")
            for value in values:
                combo.addItem(value, value)
            idx = max(0, combo.findData(current))
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _current_table_rows(self) -> List[dict]:
        rows = [self._annotation_row_payload(kp) for kp in self._current_keypoints()]
        if self._annotation_table_mode() == "review":
            rows.extend(self._suggestion_row_payload(s) for s in self._suggestions_for_current_tz())
        self._refresh_annotation_table_filters(rows)
        return self._apply_annotation_table_filters(rows)

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
            refine_btn = QtWidgets.QToolButton(widget)
            refine_btn.setText("↔")
            refine_btn.setToolTip("Accept and refine")
            suggestion_id = str(row["id"])
            accept_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._set_selected_suggestion_decision(sid, "accepted"))
            reject_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._set_selected_suggestion_decision(sid, "rejected"))
            jump_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._jump_to_table_suggestion(sid))
            refine_btn.clicked.connect(lambda _checked=False, sid=suggestion_id: self._accept_and_refine_suggestion(sid))
            for btn in (accept_btn, reject_btn, jump_btn, refine_btn):
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

    def _on_table_selection(self) -> None:
        if self._block_table:
            return
        selected_ids = set()
        if self.annot_table.selectionModel() is not None:
            for idx in self.annot_table.selectionModel().selectedRows():
                kp = self._keypoint_for_table_row(idx.row())
                if kp is not None:
                    selected_ids.add(str(kp.annotation_id))
                else:
                    suggestion = self._suggestion_for_table_row(idx.row())
                    if suggestion is not None:
                        self._selected_suggestion_id = str(getattr(suggestion, "suggestion_id", ""))
                        self._focus_suggestion(suggestion)
                        self._refresh_suggestion_explain_panel(suggestion)
        self._selected_annotation_ids = selected_ids
        self._request_ui_refresh("table-status", table=True)

    def _on_table_item_changed(self, item: "QtWidgets.QTableWidgetItem") -> None:
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
        by_image = {}
        for kp in removed:
            by_image.setdefault(int(kp.image_id), []).append(kp)
        for image_id, rows in by_image.items():
            self.controller.delete_annotations(int(image_id), rows)
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

    def _apply_legacy_status_snapshot(self, snapshot: DerivedStatusSnapshot) -> None:
        """Update compatibility widgets from the unified status snapshot."""
        status_modality_combo = getattr(self, "status_modality_combo", None)
        if status_modality_combo is not None and getattr(self, "primary_combo", None) is not None:
            status_modality_combo.blockSignals(True)
            status_modality_combo.clear()
            for idx in range(self.primary_combo.count()):
                status_modality_combo.addItem(self.primary_combo.itemText(idx), idx)
            if 0 <= int(getattr(self, "current_image_idx", 0)) < status_modality_combo.count():
                status_modality_combo.setCurrentIndex(int(self.current_image_idx))
            status_modality_combo.setToolTip(
                f"Active modality/view source: {snapshot.modality_txt}. "
                "Use this selector to switch annotation/suggestion source."
            )
            status_modality_combo.blockSignals(False)
        assist_state = snapshot.assist_state
        need = snapshot.assist_need
        state_name = str(getattr(assist_state, "name", ""))
        prev_state = getattr(self, "_last_assist_state_name", None)
        if prev_state is None:
            self._last_assist_state_name = state_name
        elif prev_state != state_name:
            self._last_assist_state_name = state_name
            transition_txt = f"Assist state transitioned: {prev_state.lower()} -> {state_name.lower()}."
            self._status_info(transition_txt, timeout_ms=2500, source="assist.transition")
            if getattr(self, "canvas", None) is not None:
                try:
                    QtWidgets.QToolTip.showText(self.canvas.mapToGlobal(QtCore.QPoint(16, 16)), transition_txt, self.canvas)
                except Exception:
                    pass
        readiness = f"Assist readiness: heuristic-only, need {need} more labels in this context." if assist_state == AssistState.HEURISTIC and need > 0 else f"Assist readiness: {assist_state_label(assist_state)}."
        for attr in ("suggest_points_act", "suggest_points_image_act", "accept_visible_suggestions_act", "accept_green_suggestions_act", "train_ranker_now_act"):
            action = getattr(self, attr, None)
            if action is not None:
                action.setToolTip(readiness)
                action.setStatusTip(readiness)
        for act_name in ("accept_visible_suggestions_act", "accept_green_suggestions_act"):
            act = getattr(self, act_name, None)
            if act is not None and snapshot.freshness.get("is_stale", False):
                act.setToolTip("Stale suggestions detected: preview dialog will require one-shot override acknowledgement.")
        if getattr(self, "evidence_strip_lbl", None) is not None:
            projection_txt = "raw"
            if getattr(self, "projection_selector", None) is not None:
                try:
                    projection_txt, axis_txt = self.projection_selector.current_selection()
                    if str(projection_txt).strip().lower() == "raw":
                        projection_txt = "source frame"
                    projection_txt = f"{projection_txt} ({axis_txt})"
                except Exception:
                    projection_txt = "source frame"
            modality_count = len(getattr(self, "_panel_modality_map", {}) or {})
            self.evidence_strip_lbl.setText(
                f"Evidence: modality={snapshot.modality_txt} | "
                f"target={snapshot.target_state} | projection={projection_txt} | "
                f"mapped modalities={modality_count}"
            )

    def _tool_label(self, tool: Tool) -> str:
        labels = {
            Tool.PAN_ZOOM: "Pan/Zoom",
            Tool.ANNOTATE_POINT: "Annotate",
            Tool.ROI_BOX: "ROI Box",
            Tool.ROI_CIRCLE: "ROI Circle",
            Tool.ROI_EDIT: "ROI Edit",
            Tool.PROFILE_LINE: "Profile Line",
            Tool.ERASER: "Eraser",
        }
        return labels.get(tool, tool.value)

    def _label_color(self, label: str, faded: bool = False) -> str:
        palette = {
            "phage": "#1f77b4",
            "not_phage": "#ff7f0e",
            "background": "#2ca02c",
            "other": "#d62728",
        }
        color = palette.get(label, "#2ca02c")
        if faded:
            color = "#cccccc"
        return color

    def _view_density_stats(self) -> Tuple[int, float]:
        """Calculate view+ROI density statistics.
        
        Returns
        -------
        pts_view : int
            Points in visible view intersected with ROI.
        area_um2 : float
            Area of visible view intersected with ROI in μm².
        
        Note: Use _roi_total_stats() for total ROI statistics.
        """
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if not axes:
            return 0, 0.0
        scale = self._axis_scale(axes[0])
        xlim, ylim = axes[0].get_xlim(), axes[0].get_ylim()
        xlim = (xlim[0] * scale, xlim[1] * scale)
        ylim = (ylim[0] * scale, ylim[1] * scale)
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        circle_mode = self.roi_shape == "circle"
        circle_center = None
        circle_r = None
        if circle_mode and roi_active:
            rx, ry, rw, rh = self.roi_rect
            circle_center = (rx + rw / 2, ry + rh / 2)
            circle_r = min(rw, rh) / 2
        pts = self._current_keypoints()
        pts_view = 0
        for kp in pts:
            if kp.x < xlim[0] or kp.x > xlim[1] or kp.y < ylim[1] or kp.y > ylim[0]:
                continue
            if roi_active:
                if circle_mode and circle_center and circle_r is not None:
                    if (kp.x - circle_center[0]) ** 2 + (
                        kp.y - circle_center[1]
                    ) ** 2 > circle_r**2:
                        continue
                else:
                    rx, ry, rw, rh = self.roi_rect
                    if not (rx <= kp.x <= rx + rw and ry <= kp.y <= ry + rh):
                        continue
            pts_view += 1
        
        # Calculate area of intersection between view and ROI
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        
        if roi_active:
            # Calculate intersection of view bounds and ROI
            rx, ry, rw, rh = self.roi_rect
            if circle_mode and circle_center and circle_r is not None:
                # For circle ROI, approximate as bounding box intersection
                # (true circle-rect intersection is complex, this is good enough for density)
                roi_left, roi_right = rx, rx + rw
                roi_bottom, roi_top = ry + rh, ry
            else:
                roi_left, roi_right = rx, rx + rw
                roi_bottom, roi_top = ry + rh, ry
            
            # View bounds (note: ylim is inverted in matplotlib image coordinates)
            view_left, view_right = xlim[0], xlim[1]
            view_bottom, view_top = max(ylim), min(ylim)
            
            # Intersection bounds
            intersect_left = max(roi_left, view_left)
            intersect_right = min(roi_right, view_right)
            intersect_bottom = max(roi_bottom, view_bottom)
            intersect_top = min(roi_top, view_top)
            
            # Calculate intersection area
            if intersect_right > intersect_left and intersect_bottom > intersect_top:
                width = intersect_right - intersect_left
                height = intersect_bottom - intersect_top
                area_um2 = (width * height) * (px_um**2) if px_um else 0.0
            else:
                area_um2 = 0.0  # No intersection
        else:
            # No ROI active, use full view area
            width = abs(xlim[1] - xlim[0])
            height = abs(ylim[1] - ylim[0])
            area_um2 = (width * height) * (px_um**2) if px_um else 0.0
        
        return pts_view, area_um2
    
    def _roi_total_stats(self) -> Tuple[int, float]:
        """Calculate total ROI statistics (entire ROI, not just visible view).
        
        Returns
        -------
        pts_roi : int
            Total points in entire ROI.
        roi_area_um2 : float
            Total area of entire ROI in μm².
        """
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        if not roi_active:
            return 0, 0.0
        
        circle_mode = self.roi_shape == "circle"
        rx, ry, rw, rh = self.roi_rect
        
        # Calculate total ROI area
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        
        if circle_mode:
            circle_r = min(rw, rh) / 2
            roi_area_um2 = (np.pi * circle_r**2) * (px_um**2) if px_um else 0.0
        else:
            roi_area_um2 = (rw * rh) * (px_um**2) if px_um else 0.0
        
        # Count total points in ROI
        pts = self._current_keypoints()
        pts_roi = 0
        
        if circle_mode:
            circle_center = (rx + rw / 2, ry + rh / 2)
            circle_r = min(rw, rh) / 2
            for kp in pts:
                if (kp.x - circle_center[0]) ** 2 + (kp.y - circle_center[1]) ** 2 <= circle_r**2:
                    pts_roi += 1
        else:
            for kp in pts:
                if rx <= kp.x <= rx + rw and ry <= kp.y <= ry + rh:
                    pts_roi += 1
        
        return pts_roi, roi_area_um2

    def _point_in_roi(self, x: float, y: float) -> bool:
        if self.roi_shape == "none":
            return True
        rx, ry, rw, rh = self.roi_rect
        if rw <= 0 or rh <= 0:
            return True
        if self.roi_shape == "box":
            return rx <= x <= rx + rw and ry <= y <= ry + rh
        cx, cy = rx + rw / 2, ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r**2

    def _current_keypoints(self) -> List[Keypoint]:
        target = str(getattr(self, "annotate_target", "frame")).strip().lower() or "frame"
        if hasattr(getattr(self, "controller", None), "annotations_for_panel"):
            pts = list(self.controller.annotations_for_panel(target))
        else:
            primary_id = int(getattr(getattr(self, "primary_image", None), "id", 0))
            pts = list(getattr(self, "annotations", {}).get(primary_id, []))
        if self.filter_current_chk.isChecked():
            t = self.t_slider.value()
            z = self.z_slider.value()
            pts = [kp for kp in pts if (kp.t in (t, -1) and kp.z in (z, -1))]

        queue_mode = getattr(self, "_review_queue_filter", "all")
        if queue_mode == "my_queue":
            user = getattr(self.controller.session_state, "current_user", "local_user")
            pts = [kp for kp in pts if kp.meta.get("assignee", "") == user]
        elif queue_mode == "needs_review":
            pts = [
                kp
                for kp in pts
                if kp.meta.get("review_state", "new") in ("new", "in_review", "needs_changes")
            ]
        elif queue_mode == "blocked_qc":
            qc_state = getattr(self, "qc_state", None)
            affected_ids = (
                qc_state.get_affected_annotation_ids(respect_filters=False)
                if qc_state is not None
                else set()
            )
            pts = [kp for kp in pts if kp.annotation_id in affected_ids]
        
        return pts

    def _jump_to_table_suggestion(self, suggestion_id: str) -> None:
        for suggestion in self._suggestions_for_current_tz():
            if str(getattr(suggestion, "suggestion_id", "")) == str(suggestion_id):
                self._selected_suggestion_id = str(suggestion_id)
                self._focus_suggestion(suggestion)
                self._refresh_suggestion_explain_panel(suggestion)
                self._request_ui_refresh("table-jump-suggestion", image=True, table=True)
                return

    def _jump_to_table_annotation(self, annotation_id: str) -> None:
        for kp in self.annotations.get(self.primary_image.id, []):
            if str(getattr(kp, "annotation_id", "")) != str(annotation_id):
                continue
            if hasattr(self, "t_slider") and int(kp.t) >= 0:
                self.t_slider.setValue(max(self.t_slider.minimum(), min(int(kp.t), self.t_slider.maximum())))
            if hasattr(self, "z_slider") and int(kp.z) >= 0:
                self.z_slider.setValue(max(self.z_slider.minimum(), min(int(kp.z), self.z_slider.maximum())))
            self._selected_annotation_ids = {str(annotation_id)}
            self._request_ui_refresh("table-jump-annotation", image=True, table=True)
            return

    def _accept_and_refine_suggestion(self, suggestion_id: str) -> None:
        self._set_selected_suggestion_decision(suggestion_id, "accepted")
        self._assist_refine_pending_annotation_id = str(suggestion_id)
        self._status_info(
            "Accepted suggestion. Click a refined position on the canvas to adjust it.",
            source="assist.table.refine",
        )
    
    def _get_current_modality_idx(self) -> Optional[int]:
        """Get the modality index for the currently displayed image."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return None
        
        # Find modality for current primary image
        for modality in manager.get_all_modalities():
            if modality.image_id == self.primary_image.id:
                return modality.idx
        
        return None

    def _restore_zoom(self, data_shape: Tuple[int, int]) -> None:
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if not axes:
            return
        if self.link_zoom:
            if self._last_zoom_linked is None:
                self._last_zoom_linked = (
                    (0.0, float(data_shape[1])),
                    (float(data_shape[0]), 0.0),
                )
            for ax in axes:
                scale = self._axis_scale(ax)
                default_xlim = (0, data_shape[1] / scale)
                default_ylim = (data_shape[0] / scale, 0)
                xlim_full, ylim_full = self._last_zoom_linked
                xlim = (xlim_full[0] / scale, xlim_full[1] / scale)
                ylim = (ylim_full[0] / scale, ylim_full[1] / scale)
                ax.set_xlim(xlim if self._valid_zoom(xlim_full, ylim_full) else default_xlim)
                ax.set_ylim(ylim if self._valid_zoom(xlim_full, ylim_full) else default_ylim)
        else:
            for ax in axes:
                scale = self._axis_scale(ax)
                default_xlim = (0, data_shape[1] / scale)
                default_ylim = (data_shape[0] / scale, 0)
                if ax.get_xlim() == (0.0, 1.0) or ax.get_ylim() == (0.0, 1.0):
                    ax.set_xlim(default_xlim)
                    ax.set_ylim(default_ylim)

    def _capture_zoom_state(self) -> None:
        axes = []
        if getattr(self, "renderer", None) is not None:
            axes = [ax for ax in self.renderer.axes.values() if ax is not None]
        if not axes:
            return
        ax = axes[0]
        scale = self._axis_scale(ax)
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        xlim_full = (xlim[0] * scale, xlim[1] * scale)
        ylim_full = (ylim[0] * scale, ylim[1] * scale)
        if self._valid_zoom(xlim_full, ylim_full):
            self._last_zoom_linked = (xlim_full, ylim_full)

    @staticmethod
    def _valid_zoom(xlim: Tuple[float, float], ylim: Tuple[float, float]) -> bool:
        if xlim[0] == xlim[1] or ylim[0] == ylim[1]:
            return False
        if any(np.isnan(xlim)) or any(np.isnan(ylim)):
            return False
        return True
