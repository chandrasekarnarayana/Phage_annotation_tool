"""Annotation-view helpers for the main window."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtWidgets


logger = logging.getLogger(__name__)


class _LogicalVisibilityLabel(QtWidgets.QLabel):
    """QLabel that reports logical visibility even when parent containers are hidden."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logical_visible = True

    def setVisible(self, visible: bool) -> None:  # noqa: N802 - Qt API
        self._logical_visible = bool(visible)
        super().setVisible(bool(visible))

    def isVisible(self) -> bool:  # noqa: N802 - Qt API
        if not self._logical_visible:
            return False
        return not self.isHidden()


class UiAnnotationViewsMixin:
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

    def _annotation_view_labels(self) -> dict[str, str]:
        """Return dynamic labels for annotation views."""
        labels = {
            "frame": "Frame",
            "mean": "Mean Projection",
            "support": "Modality 2",
            "std": "Std Projection",
        }
        manager = None
        if getattr(self, "controller", None) is not None:
            manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is not None:
            try:
                frame_modality = manager.get_modality(0)
                support_modality = manager.get_modality(1)
                if frame_modality is not None:
                    labels["frame"] = str(frame_modality.display_name or "Frame")
                if support_modality is not None:
                    labels["support"] = str(support_modality.display_name or "Modality 2")
            except Exception:
                logger.debug("Failed to read modality labels while refreshing annotation views", exc_info=True)
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        for key, modality in panel_map.items():
            if str(key).startswith("modality_"):
                labels[str(key)] = str(getattr(modality, "display_name", key))
        for key in ("mean", "std"):
            cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get(key, {}) or {})
            if cfg.get("name"):
                labels[key] = str(cfg.get("name"))
        support_cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get("support", {}) or {})
        if support_cfg.get("name"):
            labels["support"] = str(support_cfg.get("name"))
        images = list(getattr(self, "images", []) or [])
        idx = int(getattr(self, "support_image_idx", 0))
        if 0 <= idx < len(images):
            labels["support"] = f"Modality 2 ({getattr(images[idx], 'name', f'Image {idx}')})"
        return labels

    def _refresh_annotation_target_constraints(self) -> None:
        """Enable target choices based on currently available visible views."""
        availability = self._available_annotation_views()
        combo = getattr(self, "annotate_target_combo", None)
        labels = self._annotation_view_labels()
        if combo is None:
            return
        current_target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        combo.blockSignals(True)
        combo.clear()
        for key, label in self._lazy_annotation_rows():
            if not bool(availability.get(str(key), False)):
                continue
            context = (
                self.controller.ensure_annotation_context_for_panel(str(key), writable=True)
                if getattr(self, "controller", None) is not None
                and hasattr(self.controller, "ensure_annotation_context_for_panel")
                else {}
            )
            if not bool(context.get("writable", True)):
                continue
            mode = str(context.get("mode", "independent"))
            suffix = " [shared]" if mode == "shared_source" else ""
            combo.addItem(f"{labels.get(str(key), str(label))}{suffix}", str(key))
        combo.blockSignals(False)
        if combo.count() <= 0:
            combo.setEnabled(False)
            hint = getattr(self, "target_unavailable_hint_lbl", None)
            if hint is not None:
                hint.setText("No visible target view. Enable at least one view in Lazy Loading.")
                hint.setVisible(True)
            badge = getattr(self, "target_state_badge_lbl", None)
            if badge is not None:
                badge.setText("Write target: -")
            return
        combo.setEnabled(True)
        idx = combo.findData(current_target)
        if idx < 0:
            idx = 0
            self.annotate_target = str(combo.itemData(0))
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        badge = getattr(self, "target_state_badge_lbl", None)
        if badge is not None:
            badge.setText(f"Write target: {combo.currentText()}")
        hint = getattr(self, "target_unavailable_hint_lbl", None)
        if hint is not None:
            hint.setVisible(False)

    def _on_annotation_panel_toggle(self, panel_key: str, checked: bool) -> None:
        """Toggle whether annotations are rendered on a specific visible panel."""
        key = str(panel_key or "").strip()
        if not key:
            return
        current_target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        if key == current_target and not bool(checked):
            chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(key)
            if chk is not None:
                chk.blockSignals(True)
                chk.setChecked(True)
                chk.blockSignals(False)
            self._status_warning(
                "Target view must show points while annotating.",
                timeout_ms=3000,
                source="annotation_view.toggle",
            )
            return
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        point_vis[key] = bool(checked)
        self._annotation_panel_visibility = point_vis
        if hasattr(self, "_set_lazy_row_points_state"):
            self._set_lazy_row_points_state(key, bool(checked))
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        self._request_ui_refresh("ui-extra")
