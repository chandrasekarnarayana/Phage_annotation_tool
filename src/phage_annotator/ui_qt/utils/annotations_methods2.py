"""Method group 2 split from annotations.py."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.tools.router import Tool
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


class _AnnotationsMixinMethods2:
    """Methods split from AnnotationsMixin."""

    def _remove_annotation_near(self, ax, t: int, z: int, x: float, y: float) -> bool:
        """Remove the nearest point within the click radius (P3.3: confirmation added)."""
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
                # Confirmation for click deletion (P3.3) - only for multi-select delete via table
                # Single clicks typically don't need confirmation for better UX
                logger = get_panel_logger("annotate")
                self.controller.delete_annotations(removed.image_id, [removed])
                logger.log_action(
                    "delete_annotation_near",
                    image_id=int(removed.image_id),
                    t=int(removed.t),
                    z=int(removed.z),
                    y=round(float(removed.y), 2),
                    x=round(float(removed.x), 2),
                    label=removed.label,
                    click_x=round(float(x), 2),
                    click_y=round(float(y), 2),
                )
                self.undo_act.setEnabled(self.controller.can_undo())
                self.redo_act.setEnabled(self.controller.can_redo())
                self._update_status()
                return True
        return False

    def undo_last_action(self) -> None:
        """Undo last action for the current workflow."""
        if not self.controller.can_undo():
            return
        if not self.controller.undo():
            return
        if hasattr(self, "t_slider"):
            target_t = int(getattr(self.controller.view_state, "t", self.t_slider.value()))
            if self.t_slider.value() != target_t:
                self.t_slider.setValue(target_t)
        if hasattr(self, "z_slider"):
            target_z = int(getattr(self.controller.view_state, "z", self.z_slider.value()))
            if self.z_slider.value() != target_z:
                self.z_slider.setValue(target_z)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._request_ui_refresh("annotations-mixin", table=True)
        self._update_status()

    def redo_last_action(self) -> None:
        """Run the redo last action workflow."""
        if not self.controller.can_redo():
            return
        if not self.controller.redo():
            return
        if hasattr(self, "t_slider"):
            target_t = int(getattr(self.controller.view_state, "t", self.t_slider.value()))
            if self.t_slider.value() != target_t:
                self.t_slider.setValue(target_t)
        if hasattr(self, "z_slider"):
            target_z = int(getattr(self.controller.view_state, "z", self.z_slider.value()))
            if self.z_slider.value() != target_z:
                self.z_slider.setValue(target_z)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._request_ui_refresh("annotations-mixin", table=True)
        self._update_status()

    def _handle_profile_click(self, event) -> None:
        """Handle profile click for the current workflow."""
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
        self._request_ui_refresh("annotations-mixin")
