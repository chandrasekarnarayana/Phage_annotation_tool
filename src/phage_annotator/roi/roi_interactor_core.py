"""Extracted method group 2 for RoiInteractor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import matplotlib.pyplot as plt




class RoiInteractorCoreMixin:
    """Method group 2 extracted from RoiInteractor."""

    def _point_in_circle(self, fx: float, fy: float, circle: CircleROI) -> bool:
        """Handle the point in circle helper flow."""
        return (fx - circle.cx) ** 2 + (fy - circle.cy) ** 2 <= circle.r**2
    def _resize_rect(self, fx: float, fy: float, handle: str) -> None:
        """Resize rect for the current workflow."""
        rect = self._rect
        if rect is None:
            return
        x0, y0, w, h = rect.x, rect.y, rect.w, rect.h
        x1, y1 = x0 + w, y0 + h
        if handle == "resize_nw":
            x0, y0 = fx, fy
        elif handle == "resize_ne":
            x1, y0 = fx, fy
        elif handle == "resize_sw":
            x0, y1 = fx, fy
        elif handle == "resize_se":
            x1, y1 = fx, fy
        x = min(x0, x1)
        y = min(y0, y1)
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        self._rect = RectROI(x, y, w, h)
    def _refresh_artists(self) -> None:
        """Refresh artists for the current workflow."""
        if self._rect is not None:
            x, y = self.mapper.to_display(self._rect.x, self._rect.y)
            w = self._rect.w / self.mapper.scale
            h = self._rect.h / self.mapper.scale
            if self._rect_patch is None:
                self._rect_patch = plt.Rectangle(
                    (x, y), w, h, fill=False, color="#00c0ff", linewidth=1.5
                )
                self._rect_patch.set_gid("roi_interactor")
                self.ax.add_patch(self._rect_patch)
            else:
                self._rect_patch.set_xy((x, y))
                self._rect_patch.set_width(w)
                self._rect_patch.set_height(h)
                self._rect_patch.set_visible(True)
            if self._circle_patch is not None:
                self._circle_patch.set_visible(False)
        elif self._circle is not None:
            cx, cy = self.mapper.to_display(self._circle.cx, self._circle.cy)
            r = self._circle.r / self.mapper.scale
            if self._circle_patch is None:
                self._circle_patch = plt.Circle(
                    (cx, cy), r, fill=False, color="#00c0ff", linewidth=1.5
                )
                self._circle_patch.set_gid("roi_interactor")
                self.ax.add_patch(self._circle_patch)
            else:
                self._circle_patch.center = (cx, cy)
                self._circle_patch.set_radius(r)
                self._circle_patch.set_visible(True)
            if self._rect_patch is not None:
                self._rect_patch.set_visible(False)
        self._refresh_handles()
        self.canvas.draw_idle()
    def _refresh_handles(self) -> None:
        """Refresh handles for the current workflow."""
        for h in self._handles:
            h.remove()
        self._handles = []
        if not self._show_handles:
            self.canvas.draw_idle()
            return
        if self._rect is not None:
            corners = [
                (self._rect.x, self._rect.y),
                (self._rect.x + self._rect.w, self._rect.y),
                (self._rect.x, self._rect.y + self._rect.h),
                (self._rect.x + self._rect.w, self._rect.y + self._rect.h),
            ]
            for cx, cy in corners:
                dx, dy = self.mapper.to_display(cx, cy)
                h = self.ax.plot(
                    dx, dy, marker="s", color="#00c0ff", markersize=6, linestyle="none"
                )[0]
                h.set_gid("roi_interactor")
                self._handles.append(h)
        elif self._circle is not None:
            cx, cy = self._circle.cx, self._circle.cy
            rx = cx + self._circle.r
            dx, dy = self.mapper.to_display(rx, cy)
            h = self.ax.plot(dx, dy, marker="s", color="#00c0ff", markersize=6, linestyle="none")[0]
            h.set_gid("roi_interactor")
            self._handles.append(h)
        self.canvas.draw_idle()
    def _remove_artists(self) -> None:
        """Remove artists for the current workflow."""
        if self._rect_patch is not None:
            self._rect_patch.remove()
            self._rect_patch = None
        if self._circle_patch is not None:
            self._circle_patch.remove()
            self._circle_patch = None
        for h in self._handles:
            h.remove()
        self._handles = []
        self.canvas.draw_idle()
