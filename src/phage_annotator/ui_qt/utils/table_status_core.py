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

class TableStatusCoreMixin:
    """Annotation table row population, filtering, and payload construction."""

    def _annotation_table_truth_columns_enabled(self) -> bool:
        """Document the annotation_table_truth_columns_enabled flow."""
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
        """Document the annotation_table_mode flow."""
        combo = getattr(self, "annotation_table_mode_combo", None)
        return str(combo.currentData() or "truth") if combo is not None else "truth"

    def _table_filter_value(self, attr: str) -> str:
        """Document the table_filter_value flow."""
        combo = getattr(self, attr, None)
        return str(combo.currentData() or "all") if combo is not None else "all"

    def _suggestion_for_table_row(self, row: int):
        """Document the suggestion_for_table_row flow."""
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
        """Document the annotation_row_payload flow."""
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
        """Document the suggestion_row_payload flow."""
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
        """Document the apply_annotation_table_filters flow."""
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
        """Document the refresh_annotation_table_filters flow."""
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
        """Document the current_table_rows flow."""
        rows = [self._annotation_row_payload(kp) for kp in self._current_keypoints()]
        if self._annotation_table_mode() == "review":
            rows.extend(self._suggestion_row_payload(s) for s in self._suggestions_for_current_tz())
        self._refresh_annotation_table_filters(rows)
        return self._apply_annotation_table_filters(rows)

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
        """Document the style_suggestion_table_item flow."""
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
