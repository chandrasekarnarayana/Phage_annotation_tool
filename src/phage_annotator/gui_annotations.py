"""Annotation interaction helpers."""

from __future__ import annotations

from typing import Tuple

import numpy as np


class AnnotationsMixin:
    """Mixin for annotation add/remove and profile line edits."""

    def _on_click(self, event) -> None:
        if event.inaxes == self.ax_frame and event.xdata is not None and event.ydata is not None:
            fx, fy = self._to_full_coords(self.ax_frame, event.xdata, event.ydata)
            self._set_cursor_xy(fx, fy, refresh=False)
        if self.tool_router is not None:
            self.tool_router.on_click(event)

    def _add_annotation(self, image_id: int, t: int, z: int, y: float, x: float, label: str, scope: str) -> None:
        """Append a new annotation in full-resolution coordinates.

        Coordinates are stored in image space regardless of crop or downsample.
        """
        self.controller.add_annotation(
            image_id=image_id,
            image_name=self.primary_image.name,
            t=t,
            z=z,
            y=y,
            x=x,
            label=label,
            scope=scope,
        )
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._update_status()
        self._mark_dirty()

    def _set_roi_rect(self, rect: Tuple[float, float, float, float]) -> None:
        self.roi_rect = rect
        self.roi_x_spin.blockSignals(True)
        self.roi_y_spin.blockSignals(True)
        self.roi_w_spin.blockSignals(True)
        self.roi_h_spin.blockSignals(True)
        self.roi_x_spin.setValue(rect[0])
        self.roi_y_spin.setValue(rect[1])
        self.roi_w_spin.setValue(rect[2])
        self.roi_h_spin.setValue(rect[3])
        self.roi_x_spin.blockSignals(False)
        self.roi_y_spin.blockSignals(False)
        self.roi_w_spin.blockSignals(False)
        self.roi_h_spin.blockSignals(False)

    def _set_profile_line(self, line: Tuple[Tuple[float, float], Tuple[float, float]]) -> None:
        self.profile_line = line

    def _set_profile_mode(self, enabled: bool) -> None:
        self.profile_mode_chk.blockSignals(True)
        self.profile_mode_chk.setChecked(enabled)
        self.profile_mode_chk.blockSignals(False)

    def _remove_annotation_near(self, ax, t: int, z: int, x: float, y: float) -> bool:
        """Remove the nearest point within the click radius (display pixels)."""
        pts = self._current_keypoints()
        if not pts:
            return False
        disp_x, disp_y = self._to_display_coords(ax, x, y)
        click_disp = ax.transData.transform((disp_x, disp_y))
        for idx, kp in enumerate(list(pts)):
            if kp.t not in (t, -1) or kp.z not in (z, -1):
                continue
            kp_dx, kp_dy = self._to_display_coords(ax, kp.x, kp.y)
            kp_disp = ax.transData.transform((kp_dx, kp_dy))
            dist = np.hypot(kp_disp[0] - click_disp[0], kp_disp[1] - click_disp[1])
            if dist <= self.click_radius_px:
                removed = pts[idx]
                self.controller.delete_annotations(removed.image_id, [removed])
                self.undo_act.setEnabled(self.controller.can_undo())
                self.redo_act.setEnabled(self.controller.can_redo())
                self._update_status()
                return True
        return False

    def undo_last_action(self) -> None:
        if not self.controller.can_undo():
            return
        if not self.controller.undo():
            return
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._refresh_image()
        self._update_status()

    def redo_last_action(self) -> None:
        if not self.controller.can_redo():
            return
        if not self.controller.redo():
            return
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._refresh_image()
        self._update_status()

    def _handle_profile_click(self, event) -> None:
        if self.profile_line is None or event.inaxes != self.ax_line:
            return
        if event.xdata is None or event.ydata is None:
            return
        (y1, x1), (y2, x2) = self.profile_line
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) > abs(dy):
            self.profile_line = ((y1, event.xdata), (y2, event.xdata))
        else:
            self.profile_line = ((event.ydata, x1), (event.ydata, x2))
        self._refresh_image()
