"""Display, playback, and general control handlers."""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_auto_window
from phage_annotator.session.signal_hub import emit_display_changed, emit_view_changed
from phage_annotator.session.modality import ProjectionType
from phage_annotator.session.multi_playback import PlaybackMode
from phage_annotator.ui_qt.controls.display_contrast import DisplayContrastMixin
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger

class DisplayControlsLutMixin:
    """Display setting handlers."""

    def _on_lut_change(self, idx: int) -> None:
        """Document the on_lut_change flow."""
        if idx < 0:
            return
        self.current_cmap_idx = idx
        self.recorder.record(
            "set_lut",
            {"index": idx, "name": lut_names()[idx] if idx < len(lut_names()) else idx},
        )
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        self._sync_modality_display_settings(panel_key, mapping)
        self._sync_contrast_from_frame()
        if self.lut_invert_chk is not None:
            invert_supported = True
            if 0 <= idx < len(LUTS):
                invert_supported = LUTS[idx].invert_supported
                self.lut_invert_chk.setEnabled(invert_supported)
                if not invert_supported:
                    self.lut_invert_chk.setChecked(False)
                    self._request_ui_refresh("display-controls")

    def _on_lut_invert(self) -> None:
        """Document the on_lut_invert flow."""
        self.controller.set_invert(self.lut_invert_chk.isChecked())
        self.recorder.record(
            "set_lut_invert", {"invert": self.lut_invert_chk.isChecked()}
        )
        self._sync_contrast_from_frame()
        self._request_ui_refresh("display-controls")

    def _on_gamma_change(self, value: int) -> None:
        """Document the on_gamma_change flow."""
        gamma = max(0.2, min(5.0, value / 10.0))
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        mapping.gamma = gamma
        self._sync_modality_display_settings(panel_key, mapping)
        if self.gamma_label is not None:
            self.gamma_label.setText(f"{gamma:.2f}")
            self.recorder.record("set_gamma", {"gamma": f"{gamma:.2f}"})
            emit_display_changed(self.controller)
            self._sync_contrast_from_frame()
            self._request_ui_refresh("display-controls")

    def _on_log_toggle(self) -> None:
        """Document the on_log_toggle flow."""
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        mapping.mode = "log" if self.log_chk.isChecked() else "linear"
        self.recorder.record("set_log", {"enabled": self.log_chk.isChecked()})
        emit_display_changed(self.controller)
        self._request_ui_refresh("display-controls")

    def _copy_display_settings(self) -> None:
        """Copy LUT/min/max/gamma from primary to another target."""
        panel_key = self._display_source_panel_key()
        source_img = self._display_source_image()
        mapping = self.controller.display_mapping.mapping_for(source_img.id, panel_key)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Copy Display Settings")
        layout = QtWidgets.QFormLayout(dlg)
        target_combo = QtWidgets.QComboBox()
        target_combo.addItems(["Modality 2 image", "All images"])
        layout.addRow("Target", target_combo)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            """Document the apply flow."""
            choice = target_combo.currentText()
            panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
            if choice == "Modality 2 image":
                modality1 = panel_map.get("modality_1")
                if modality1 is not None:
                    self._apply_display_to_image(int(modality1.image_id), "modality_1", mapping)
            else:
                for img in self.images:
                    for key, modality in panel_map.items():
                        if int(getattr(modality, "image_id", -1)) == int(getattr(img, "id", -2)):
                            self._apply_display_to_image(img.id, str(key), mapping)
            self._request_ui_refresh("display-controls")
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def _apply_display_to_image(self, image_id: int, panel: str, mapping) -> None:
        """Document the apply_display_to_image flow."""
        copy = mapping.clone()
        copy.lut = mapping.lut
        copy.gamma = mapping.gamma
        copy.min_val = mapping.min_val
        copy.max_val = mapping.max_val
        copy.mode = mapping.mode
        copy.invert = mapping.invert
        self.controller.set_display_for_image(image_id, panel, copy)
        self._sync_modality_display_settings(panel, copy)

    def _on_label_change(self, button, checked: bool) -> None:
        """Document the on_label_change flow."""
        if checked:
            self.current_label = button.text()
            self._update_status()

    def _on_scope_change(self) -> None:
        """Document the on_scope_change flow."""
        old_scope = str(getattr(self, "annotation_scope", "current"))
        new_scope = "current" if self.scope_group.buttons()[0].isChecked() else "all"
        if old_scope == "current" and new_scope == "all":
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Stack Annotation Mode",
                "Switch to Stack Annotation Mode (All Z)?\n"
                "New annotations will apply globally across Z.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                self.scope_group.buttons()[0].setChecked(True)
                return
        self.annotation_scope = new_scope
        if hasattr(self, "controller") and hasattr(self.controller, "append_audit_event"):
            self.controller.append_audit_event(
                "annotation_scope_changed",
                image_id=self.primary_image.id if getattr(self, "primary_image", None) is not None else -1,
                old_scope=old_scope,
                new_scope=new_scope,
            )
        if hasattr(self, "_append_assist_change_log"):
            self._append_assist_change_log(
                "scope_changed",
                old_scope=str(old_scope),
                new_scope=str(new_scope),
            )
        if new_scope == "all":
            msg = "Switched to Stack Annotation Mode (All Z)"
            QtWidgets.QToolTip.showText(
                self.mapToGlobal(QtCore.QPoint(20, 20)),
                msg,
                self,
            )
        else:
            msg = "Switched to Slice Annotation Mode (Current Z)"
            QtWidgets.QToolTip.showText(
                self.mapToGlobal(QtCore.QPoint(20, 20)),
                msg,
                self,
            )
        # Auto-hide tooltip after 2 seconds to prevent it from lingering
        QtCore.QTimer.singleShot(2000, lambda: QtWidgets.QToolTip.hideText())
        self._update_status()
        self._request_ui_refresh("display-controls")
        if hasattr(self, "_maybe_emit_assist_context_delta"):
            self._maybe_emit_assist_context_delta("scope")

    def _on_target_change(self) -> None:
        """Document the on_target_change flow."""
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        old_target = str(getattr(self, "annotate_target", default_target))
        combo = getattr(self, "annotate_target_combo", None)
        if combo is not None and combo.count() > 0:
            selected = str(combo.currentData() or combo.currentText() or "").strip().lower()
            if selected:
                self.annotate_target = selected
        elif getattr(self, "target_group", None) is not None:
            target_buttons = dict(getattr(self, "_target_buttons", {}) or {})
            if target_buttons:
                selected = None
                for key, btn in target_buttons.items():
                    if btn is not None and btn.isChecked():
                        selected = key
                        break
                self.annotate_target = str(selected or default_target)
            else:
                buttons = self.target_group.buttons()
                if buttons and buttons[0].isChecked():
                    self.annotate_target = default_target
                else:
                    self.annotate_target = default_target
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        point_vis[str(getattr(self, "annotate_target", default_target))] = True
        self._annotation_panel_visibility = point_vis
        chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(
            str(getattr(self, "annotate_target", default_target))
        )
        if chk is not None and not chk.isChecked():
            chk.blockSignals(True)
            chk.setChecked(True)
            chk.blockSignals(False)
        if hasattr(self, "_set_lazy_row_points_state"):
            self._set_lazy_row_points_state(str(getattr(self, "annotate_target", default_target)), True)
        badge = getattr(self, "target_state_badge_lbl", None)
        combo = getattr(self, "annotate_target_combo", None)
        if badge is not None:
            if combo is not None and combo.count() > 0:
                badge.setText(f"Write target: {combo.currentText()}")
            else:
                badge.setText(f"Write target: {str(getattr(self, 'annotate_target', default_target))}")
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        if old_target != str(self.annotate_target) and hasattr(
            self, "_mark_annotation_context_changed"
        ):
            self._mark_annotation_context_changed(
                f"target panel changed ({old_target} -> {self.annotate_target})"
            )
        if old_target != str(self.annotate_target) and hasattr(self, "_append_assist_change_log"):
            self._append_assist_change_log(
                "target_changed",
                old_target=str(old_target),
                new_target=str(self.annotate_target),
            )
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
        self._update_status()
        self._request_ui_refresh("display-controls")
        if old_target != str(self.annotate_target) and hasattr(self, "_maybe_emit_assist_context_delta"):
            self._maybe_emit_assist_context_delta("target")
