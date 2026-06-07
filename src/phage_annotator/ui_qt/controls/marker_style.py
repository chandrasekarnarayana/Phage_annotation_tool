"""Extracted method group 5 for DisplayControlsMixin."""

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



class MarkerStyleMixin:
    """Method group 5 extracted from DisplayControlsMixin."""

    def _on_marker_size_change(self, val: int) -> None:
        """Handle the on marker size change helper flow."""
        self.marker_size = float(val)
        self._settings.setValue("markerSize", int(val))
        for attr in ("marker_size_spin", "annotate_marker_size_spin"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            if int(widget.value()) == int(val):
                continue
            widget.blockSignals(True)
            widget.setValue(int(val))
            widget.blockSignals(False)
        self._request_ui_refresh("display-controls")
    def _on_marker_shape_change(self, _index: int = -1) -> None:
        """Handle the on marker shape change helper flow."""
        combo = getattr(self, "annotate_marker_shape_combo", None)
        if combo is None or combo.count() <= 0:
            return
        marker = str(combo.currentData() or "o").strip() or "o"
        self.marker_shape = marker
        self._settings.setValue("markerShape", marker)
        self._request_ui_refresh("display-controls")
    def _on_click_radius_change(self, val: float) -> None:
        """Handle the on click radius change helper flow."""
        self.click_radius_px = float(val)
        self._settings.setValue("clickRadiusPx", float(val))
    def _on_profile_mode(self) -> None:
        """Handle the on profile mode helper flow."""
        self.profile_enabled = self.profile_mode_chk.isChecked()
    def _on_profile_chk_changed(self) -> None:
        """Handle the on profile chk changed helper flow."""
        self._set_panel_visibility("profile", self.profile_chk.isChecked())
        self.profile_enabled = bool(self.profile_chk.isChecked())
        self._request_ui_refresh("display-controls")
    def _on_hist_chk_changed(self) -> None:
        """Handle the on hist chk changed helper flow."""
        self._set_panel_visibility("hist", self.hist_chk.isChecked())
        self.hist_enabled = bool(self.hist_chk.isChecked())
        self._request_ui_refresh("display-controls")
    def _clear_profile(self) -> None:
        """Clear profile for the current workflow."""
        self.profile_line = None
        self._request_ui_refresh("display-controls")
    def _on_hist_region(self) -> None:
        """Handle the on hist region helper flow."""
        widget = self._hist_region_widget()
        if widget is None:
            return
        text = widget.currentText()
        if text == "ROI":
            self.hist_region = "roi"
        elif text == "Crop area":
            self.hist_region = "crop"
        else:
            self.hist_region = "full"
        self._request_ui_refresh("display-controls")
    def _on_hist_scope_change(self) -> None:
        """Handle the on hist scope change helper flow."""
        widget = self._hist_scope_widget()
        if widget is None:
            return
        self._hist_scope_mode = widget.currentText()
        self._hist_cache = None
        self._hist_cache_key = None
        if self._hist_job_id is not None:
            self.jobs.cancel(self._hist_job_id)
            self._hist_job_id = None
            self._request_ui_refresh("display-controls")
    def _on_contrast_slider_pressed(self) -> None:
        """Handle the on contrast slider pressed helper flow."""
        self._contrast_drag_active = True
        self._start_interaction()
    def _on_contrast_slider_released(self) -> None:
        """Handle the on contrast slider released helper flow."""
        self._end_interaction()
        if not self._contrast_drag_active:
            return
        self._contrast_drag_active = False
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        vmin = float(np.percentile(prim.array, self.vmin_slider.value()))
        vmax = float(np.percentile(prim.array, self.vmax_slider.value()))
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        mapping.set_window(vmin, vmax)
        self._sync_modality_display_settings(panel_key, mapping)
        self._sync_contrast_from_frame()
        if hasattr(self, "_schedule_refresh"):
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")
    def _auto_set_dialog(self) -> None:
        """Handle the auto set dialog helper flow."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Set Auto Contrast")
        layout = QtWidgets.QFormLayout(dlg)
        low_spin = QtWidgets.QDoubleSpinBox()
        high_spin = QtWidgets.QDoubleSpinBox()
        low_spin.setRange(0.0, 100.0)
        high_spin.setRange(0.0, 100.0)
        low_spin.setDecimals(2)
        high_spin.setDecimals(2)
        low_spin.setValue(float(self._settings.value("autoLowPct", 0.35)))
        high_spin.setValue(float(self._settings.value("autoHighPct", 99.65)))
        layout.addRow("Low percentile (%)", low_spin)
        layout.addRow("High percentile (%)", high_spin)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            """Apply apply for the current workflow."""
            low = float(low_spin.value())
            high = float(high_spin.value())
            if high <= low:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid range", "High percentile must be greater than low."
                )
                return
            self._settings.setValue("autoLowPct", low)
            self._settings.setValue("autoHighPct", high)
            if self.auto_pct_label is not None:
                self.auto_pct_label.setText(f"{low:.2f}% / {high:.2f}%")
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()
    def _open_contrast_dialog(self) -> None:
        """Open contrast dialog for the current workflow."""
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        from phage_annotator.ui_qt.widgets.contrast_dialog import ContrastDialog

        data = self._slice_data(prim)
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)

        def _apply(vmin: float, vmax: float) -> None:
            """Apply apply for the current workflow."""
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings(panel_key, mapping)
            if self.vmin_label is not None:
                self.vmin_label.setText(f"vmin: {vmin:.3f}")
            if self.vmax_label is not None:
                self.vmax_label.setText(f"vmax: {vmax:.3f}")
            self._bc_set_controls(vmin, vmax)
            if hasattr(self, "_schedule_refresh"):
                self._schedule_refresh()
            else:
                self._request_ui_refresh("display-controls")

        dlg = ContrastDialog(self, data, mapping.min_val, mapping.max_val, _apply)
        dlg.exec()
