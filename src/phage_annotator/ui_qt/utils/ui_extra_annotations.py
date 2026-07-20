"""Annotation-view helpers for the main window."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.source_protocols import SourceProtocolsMixin

logger = logging.getLogger(__name__)


class _LogicalVisibilityLabel(QtWidgets.QLabel):
    """QLabel that reports logical visibility even when parent containers are hidden."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logical_visible = True

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self._logical_visible = bool(visible)
        super().setVisible(bool(visible))

    def isVisible(self) -> bool:  # noqa: N802
        if not self._logical_visible:
            return False
        return not self.isHidden()


class UiAnnotationViewsMixin(SourceProtocolsMixin):
    """Mixin for lazy-loader-backed annotation view controls."""

    def _available_annotation_views(self) -> dict[str, bool]:
        """Return currently available canvas views for annotation visibility controls."""
        table = getattr(self, "lazy_modality_table", None)
        availability: dict[str, bool] = {}
        panel_visibility = {
            str(key): bool(value)
            for key, value in dict(getattr(self, "_panel_visibility", {}) or {}).items()
        }
        if table is not None and table.rowCount() > 0:
            for row in range(table.rowCount()):
                name_item = table.item(row, 2)
                if name_item is None:
                    continue
                role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
                panel_key = ""
                if isinstance(role_data, str):
                    role_text = str(role_data)
                    if role_text.startswith("builtin:"):
                        panel_key = role_text.split(":", 1)[1]
                    elif role_text.startswith("modality_"):
                        panel_key = role_text
                else:
                    try:
                        panel_key = self._panel_key_for_modality_idx(int(role_data))
                    except Exception:
                        panel_key = ""
                if not panel_key:
                    continue
                if str(panel_key) in panel_visibility:
                    availability[str(panel_key)] = bool(panel_visibility.get(str(panel_key), False))
                    continue
                visible_chk = (
                    self._lazy_checkbox_from_cell(table.cellWidget(row, 0))
                    if hasattr(self, "_lazy_checkbox_from_cell")
                    else table.cellWidget(row, 0)
                )
                availability[str(panel_key)] = bool(
                    isinstance(visible_chk, QtWidgets.QCheckBox) and visible_chk.isChecked()
                )
            if availability:
                return availability
        availability = {"frame": bool(panel_visibility.get("frame", True))}
        for key, visible in panel_visibility.items():
            k = str(key)
            if k in {"mean", "support", "std"} or k.startswith("modality_"):
                availability[k] = bool(visible)
        return availability

    def _set_lazy_row_visible_state(self, panel_key: str, checked: bool) -> None:
        """Mirror panel visibility changes back into lazy modality table checkboxes."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        panel_key = str(panel_key)
        for row in range(table.rowCount()):
            name_item = table.item(row, 2)
            if name_item is None:
                continue
            role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
            row_key = ""
            if isinstance(role_data, str):
                role_text = str(role_data)
                if role_text.startswith("builtin:"):
                    row_key = role_text.split(":", 1)[1]
                elif role_text.startswith("modality_"):
                    row_key = role_text
            else:
                try:
                    row_key = self._panel_key_for_modality_idx(int(role_data))
                except Exception:
                    row_key = ""
            if row_key != panel_key:
                continue
            chk = (
                self._lazy_checkbox_from_cell(table.cellWidget(row, 0))
                if hasattr(self, "_lazy_checkbox_from_cell")
                else table.cellWidget(row, 0)
            )
            if isinstance(chk, QtWidgets.QCheckBox) and chk.isChecked() != bool(checked):
                chk.blockSignals(True)
                chk.setChecked(bool(checked))
                chk.blockSignals(False)
            break

    def _set_lazy_row_points_state(self, panel_key: str, checked: bool) -> None:
        """Mirror annotation point visibility changes into lazy-table Pts checkboxes."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        panel_key = str(panel_key)
        for row in range(table.rowCount()):
            name_item = table.item(row, 2)
            if name_item is None:
                continue
            role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
            row_key = ""
            if isinstance(role_data, str):
                role_text = str(role_data)
                if role_text.startswith("builtin:"):
                    row_key = role_text.split(":", 1)[1]
                elif role_text.startswith("modality_"):
                    row_key = role_text
            else:
                try:
                    row_key = self._panel_key_for_modality_idx(int(role_data))
                except Exception:
                    row_key = ""
            if row_key != panel_key:
                continue
            chk = (
                self._lazy_checkbox_from_cell(table.cellWidget(row, 1))
                if hasattr(self, "_lazy_checkbox_from_cell")
                else table.cellWidget(row, 1)
            )
            if isinstance(chk, QtWidgets.QCheckBox) and chk.isChecked() != bool(checked):
                chk.blockSignals(True)
                chk.setChecked(bool(checked))
                chk.blockSignals(False)
            break

    def _lazy_annotation_rows(self) -> list[tuple[str, str]]:
        """Return (panel_key, display_name) rows from lazy table in exact visible order."""
        table = getattr(self, "lazy_modality_table", None)
        rows: list[tuple[str, str]] = []
        if table is None:
            return rows
        for row in range(table.rowCount()):
            name_item = table.item(row, 2)
            if name_item is None:
                continue
            role_data = name_item.data(QtCore.Qt.ItemDataRole.UserRole)
            panel_key = ""
            if isinstance(role_data, str):
                role_text = str(role_data)
                if role_text.startswith("builtin:"):
                    panel_key = role_text.split(":", 1)[1]
                elif role_text.startswith("modality_"):
                    panel_key = role_text
            else:
                try:
                    panel_key = self._panel_key_for_modality_idx(int(role_data))
                except Exception:
                    panel_key = ""
            if not panel_key:
                continue
            display_name = str(name_item.text()).strip() or str(panel_key)
            rows.append((str(panel_key), display_name))
        return rows

    def _refresh_annotation_view_controls(self) -> None:
        """Sync dynamic visible-view checklist and target constraints."""
        availability = self._available_annotation_views()
        layout = getattr(self, "_annotation_view_rows_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        checkboxes: dict[str, QtWidgets.QCheckBox] = {}
        ordered_rows = self._lazy_annotation_rows()
        if not ordered_rows:
            labels = self._annotation_view_labels()
            ordered_rows = [
                (k, labels.get(k, k))
                for k in ("frame", "support", "mean", "std")
                if k in availability
            ]
        for key, label in ordered_rows:
            if not bool(availability.get(str(key), False)):
                continue
            chk = QtWidgets.QCheckBox(str(label))
            chk.toggled.connect(
                lambda checked, k=str(key): self._on_annotation_panel_toggle(k, bool(checked))
            )
            layout.addWidget(chk)
            checkboxes[str(key)] = chk
        self._annotation_view_checkboxes = checkboxes
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        for key, chk in checkboxes.items():
            available = bool(availability.get(str(key), False))
            chk.setVisible(bool(available))
            chk.blockSignals(True)
            chk.setChecked(bool(point_vis.get(str(key), True)))
            chk.blockSignals(False)
        self.show_frame_chk = self._annotation_view_checkboxes.get("frame")
        self.show_mean_chk = self._annotation_view_checkboxes.get("mean")
        self.show_support_chk = self._annotation_view_checkboxes.get("support")
        self._refresh_annotation_target_constraints()
