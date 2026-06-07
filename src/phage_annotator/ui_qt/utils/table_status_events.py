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

class TableStatusEventsMixin:
    """Table selection events, item editing, and annotation delete handlers."""

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

    def _set_annotation_table_actions(self, row_idx: int, row: dict) -> None:
        """Document the set_annotation_table_actions flow."""
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
        """Document the on_table_selection flow."""
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
        """Document the on_table_item_changed flow."""
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

    def _point_in_roi(self, x: float, y: float) -> bool:
        """Document the point_in_roi flow."""
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
        """Document the current_keypoints flow."""
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
