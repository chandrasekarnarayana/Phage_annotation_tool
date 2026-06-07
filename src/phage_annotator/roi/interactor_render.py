"""Matplotlib artist rendering for the ROI interactor."""

from __future__ import annotations

import matplotlib.pyplot as plt


class RoiInteractorRenderMixin:
    """Create, update, and remove ROI matplotlib artists."""

    def _refresh_artists(self) -> None:
        """Redraw rectangle or circle artists for the active ROI."""
        if self._rect is not None:
            x, y = self.mapper.to_display(self._rect.x, self._rect.y)
            w = self._rect.w / self.mapper.scale
            h = self._rect.h / self.mapper.scale
            if self._rect_patch is None:
                self._rect_patch = plt.Rectangle((x, y), w, h, fill=False, color="#00c0ff", linewidth=1.5)
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
                self._circle_patch = plt.Circle((cx, cy), r, fill=False, color="#00c0ff", linewidth=1.5)
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
        """Redraw resize handles for the active ROI."""
        for handle in self._handles:
            handle.remove()
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
                handle = self.ax.plot(dx, dy, marker="s", color="#00c0ff", markersize=6, linestyle="none")[0]
                handle.set_gid("roi_interactor")
                self._handles.append(handle)
        elif self._circle is not None:
            dx, dy = self.mapper.to_display(self._circle.cx + self._circle.r, self._circle.cy)
            handle = self.ax.plot(dx, dy, marker="s", color="#00c0ff", markersize=6, linestyle="none")[0]
            handle.set_gid("roi_interactor")
            self._handles.append(handle)
        self.canvas.draw_idle()

    def _remove_artists(self) -> None:
        """Remove ROI artists from the axes."""
        if self._rect_patch is not None:
            self._rect_patch.remove()
            self._rect_patch = None
        if self._circle_patch is not None:
            self._circle_patch.remove()
            self._circle_patch = None
        for handle in self._handles:
            handle.remove()
        self._handles = []
        self.canvas.draw_idle()
