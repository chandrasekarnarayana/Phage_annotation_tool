"""Extracted method group 3 for DisplayControlsMixin."""

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



class PlaybackControlsTimerMixin:
    """Method group 3 extracted from DisplayControlsMixin."""

    def _on_play_tick(self) -> None:
        """Handle the on play tick helper flow."""
        if self._playback_mode:
            return
        if hasattr(self, "controller") and self.controller is not None:
            self.controller.set_t(int(self.t_slider.value()))
            self.controller.set_z(int(self.z_slider.value()))
        if bool(getattr(self, "auto_follow_table_chk", None) and self.auto_follow_table_chk.isChecked()):
            self._refresh_table()
        if hasattr(self, "_refresh_review_queue_panel"):
            self._refresh_review_queue_panel()
        self._request_ui_refresh("display-controls")
    def _on_loop_change(self) -> None:
        """Handle the on loop change helper flow."""
        self.loop_playback = self.loop_chk.isChecked()
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[GUI] Loop playback {'enabled' if self.loop_playback else 'disabled'}",
                category="GUI",
            )
        if getattr(self, "_playback_mode", False):
            try:
                self._playback_ring.reset()
                self._playback_cursor = int(self.t_slider.value())
                if hasattr(self, "_restart_playback_prefetch"):
                    self._restart_playback_prefetch(self._playback_cursor)
                if hasattr(self, "_append_log"):
                    self._append_log(
                        f"[GUI] Playback prefetch reconfigured loop={bool(self.loop_playback)} t={int(self._playback_cursor)}",
                        category="GUI",
                    )
            except Exception:
                pass
        if hasattr(getattr(self, "recorder", None), "record"):
            try:
                self.recorder.record("gui_loop_toggle", {"enabled": bool(self.loop_playback)})
            except Exception:
                pass
    def _on_speed_change(self, value: int) -> None:
        """Handle the on speed change helper flow."""
        if getattr(self, "fps_label", None) is not None:
            self.fps_label.setText(f"FPS: {value}")
        # Keep legacy timer path bounded if it gets toggled by old shortcuts.
        timer = getattr(self, "play_timer", None)
        if timer is not None:
            fps = max(1, int(value))
            timer.setInterval(max(16, int(1000 / fps)))
        if hasattr(self, "_append_log"):
            self._append_log(f"[GUI] Playback speed set fps={int(value)}", category="GUI")
        if hasattr(getattr(self, "recorder", None), "record"):
            try:
                self.recorder.record("gui_playback_speed", {"fps": int(value)})
            except Exception:
                pass
    def _on_axis_mode_change(self, mode: str) -> None:
        """Handle the on axis mode change helper flow."""
        old_mode = getattr(self.controller.view_state, "axis_interpretation", None)
        logger = get_panel_logger("prepare")
        self.stop_playback_t()
        self.controller.set_axis_interpretation(self.primary_image.id, mode)
        logger.log_action(
            "axis_mode_change",
            image_id=int(self.primary_image.id),
            image_name=str(self.primary_image.name),
            old_mode=old_mode,
            new_mode=mode,
        )
        # Force reload for current primary to honor new interpretation.
        self._evict_image_cache(self.primary_image)
        self.proj_cache.invalidate_image(self.primary_image.id)
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
        self.recorder.record(
            "set_axis_interpretation", {"image": self.primary_image.name, "mode": mode}
        )
    def _on_projection_axis_change(self, text: str) -> None:
        """Handle projection axis change from combo box for backward compat."""
        axis = text.lower()
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return
        updated = False
        for modality in manager.get_all_modalities():
            if modality.image_id == self.primary_image.id:
                if modality.display_settings.projection_axis != axis:
                    modality.display_settings.projection_axis = axis
                    updated = True
                break
        if updated:
            self.proj_cache.invalidate_image(self.primary_image.id)
            self._request_ui_refresh("display-controls")
            if hasattr(self, "_append_assist_change_log"):
                self._append_assist_change_log(
                    "projection_changed",
                    projection_type="current_panel_axis_only",
                    projection_axis=str(axis),
                )
            if hasattr(self, "_maybe_emit_assist_context_delta"):
                self._maybe_emit_assist_context_delta("projection")
        self._request_ui_refresh("display-controls", table=True)
    def _on_projection_changed(self, projection_type: str, projection_axis: str) -> None:
        """Handle projection type and axis change from ProjectionSelectorWidget."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return
        
        # Import ProjectionType enum
        from phage_annotator.session.modality import ProjectionType
        
        updated = False
        for modality in manager.get_all_modalities():
            if modality.image_id == self.primary_image.id:
                # Update projection type if changed
                try:
                    proj_type = ProjectionType(projection_type.lower())
                    if modality.projection_type != proj_type:
                        modality.projection_type = proj_type
                        updated = True
                except ValueError:
                    pass
                
                # Update projection axis if changed
                if modality.display_settings.projection_axis != projection_axis:
                    modality.display_settings.projection_axis = projection_axis
                    updated = True
                break
        
        if updated:
            self.proj_cache.invalidate_image(self.primary_image.id)
            self._request_ui_refresh("display-controls")
    def _on_vminmax_change(self) -> None:
        """Handle the on vminmax change helper flow."""
        if self.vmin_slider.value() > self.vmax_slider.value():
            self.vmax_slider.setValue(self.vmin_slider.value())
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        data = prim.array
        if self._interactive:
            stride = max(1, self.downsample_factor)
            data = data[::stride, ::stride, ::stride, ::stride]
        vmin = float(np.percentile(data, self.vmin_slider.value()))
        vmax = float(np.percentile(data, self.vmax_slider.value()))
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        mapping.set_window(vmin, vmax)
        self._sync_modality_display_settings(panel_key, mapping)
        self._sync_contrast_from_frame()
        if self._interactive:
            self._contrast_drag_active = True
            self.recorder.record(
                "set_minmax",
                {
                    "vmin": f"{self._last_vmin:.4f}",
                    "vmax": f"{self._last_vmax:.4f}",
                },
            )
            self._schedule_refresh()
        else:
            self._request_ui_refresh("display-controls")
    def _apply_display_mapping(self) -> None:
        """Destructively apply the current display mapping to pixel data."""
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        # P1.4: Confirmation with "Don't show again" toggle stored in settings
        if self._settings.value("confirmApplyDisplayMapping", True, type=bool):
            mbox = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Warning,
                "Apply display mapping",
                (
                    "This will permanently rescale pixel values for the current image.\n"
                    "This cannot be undone. Proceed?"
                ),
                parent=self,
            )
            mbox.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
            )
            dont = QtWidgets.QCheckBox("Don't show again")
            mbox.setCheckBox(dont)
            resp = mbox.exec()
            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            if dont.isChecked():
                self._settings.setValue("confirmApplyDisplayMapping", False)
        data = prim.array.astype(np.float32, copy=True)
        if mapping.max_val == mapping.min_val:
            return
        data = (data - mapping.min_val) / (mapping.max_val - mapping.min_val)
        data = np.clip(data, 0.0, 1.0)
        prim.array = data
        mapping.reset_to_full_range(float(data.min()), float(data.max()))
        self._sync_modality_display_settings(panel_key, mapping)
        self._request_ui_refresh("display-controls")
    def _current_vmin_vmax(self) -> Tuple[float, float]:
        """Handle the current vmin vmax helper flow."""
        panel_key = self._display_source_panel_key()
        prim = self._display_source_image()
        if prim.array is None:
            return 0.0, 1.0
        mapping = self._get_display_mapping(prim.id, panel_key, prim.array)
        vmin, vmax = mapping.min_val, mapping.max_val
        if vmin > vmax:
            vmin, vmax = vmax, vmin
            mapping.set_window(vmin, vmax)
            self._sync_modality_display_settings(panel_key, mapping)
            self.vmin_label.setText(f"vmin: {vmin:.3f}")
            self.vmax_label.setText(f"vmax: {vmax:.3f}")
        # PHASE 2D FIX: Always return vmin, vmax (was missing return statement)
        return vmin, vmax
