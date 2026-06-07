"""Mouse event handling for the ROI interactor."""

from __future__ import annotations

from phage_annotator.roi.interactor_types import CircleROI, RectROI


class RoiInteractorEventMixin:
    """Translate matplotlib mouse events into ROI edits."""

    def _on_press(self, event) -> None:
        """Start drawing, moving, or resizing based on the active mode."""
        if event.inaxes is not self.ax or event.button != 1:
            return
        if event.xdata is None or event.ydata is None:
            return
        fx, fy = self.mapper.to_full(event.xdata, event.ydata)
        self._drag_start = (fx, fy)
        if self.mode == "draw_rect":
            self._rect = RectROI(fx, fy, 0.0, 0.0)
            self._circle = None
            self._drag_mode = "draw_rect"
        elif self.mode == "draw_circle":
            self._circle = CircleROI(fx, fy, 0.0)
            self._rect = None
            self._drag_mode = "draw_circle"
        elif self.mode == "edit":
            self._drag_mode = self._hit_test(fx, fy)
        else:
            self._drag_mode = None

    def _on_motion(self, event) -> None:
        """Update the active ROI while the mouse is dragged."""
        if self._drag_start is None or self._drag_mode is None:
            return
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            return
        fx, fy = self.mapper.to_full(event.xdata, event.ydata)
        if self._drag_mode == "draw_rect" and self._rect is not None:
            x0, y0 = self._drag_start
            self._rect = RectROI(min(x0, fx), min(y0, fy), abs(fx - x0), abs(fy - y0))
            self._emit_change()
        elif self._drag_mode == "draw_circle" and self._circle is not None:
            cx, cy = self._drag_start
            self._circle = CircleROI(cx, cy, ((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5)
            self._emit_change()
        elif self._drag_mode == "move" and self._rect is not None:
            dx = fx - self._drag_start[0]
            dy = fy - self._drag_start[1]
            self._rect = RectROI(self._rect.x + dx, self._rect.y + dy, self._rect.w, self._rect.h)
            self._drag_start = (fx, fy)
            self._emit_change()
        elif self._drag_mode == "move_circle" and self._circle is not None:
            dx = fx - self._drag_start[0]
            dy = fy - self._drag_start[1]
            self._circle = CircleROI(self._circle.cx + dx, self._circle.cy + dy, self._circle.r)
            self._drag_start = (fx, fy)
            self._emit_change()
        elif self._drag_mode.startswith("resize") and self._rect is not None:
            self._resize_rect(fx, fy, self._drag_mode)
            self._emit_change()
        elif self._drag_mode == "radius" and self._circle is not None:
            cx, cy = self._circle.cx, self._circle.cy
            self._circle = CircleROI(cx, cy, max(((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5, self.min_size_px))
            self._emit_change()

    def _on_release(self, event) -> None:
        """Finish the current drag operation."""
        if self._drag_start is None:
            return
        self._drag_start = None
        self._drag_mode = None

    def _emit_change(self) -> None:
        """Redraw and emit a validated ROI change."""
        self._refresh_artists()
        roi_type, rect, circle = self.get_roi()
        if rect and (rect.w < self.min_size_px or rect.h < self.min_size_px):
            return
        if circle and circle.r < self.min_size_px:
            return
        self.on_change(roi_type, rect, circle)
