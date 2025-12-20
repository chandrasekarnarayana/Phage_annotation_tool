"""Matplotlib ROI interactor for rectangle and circle ROIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import matplotlib.pyplot as plt


@dataclass
class RectROI:
    x: float
    y: float
    w: float
    h: float


@dataclass
class CircleROI:
    cx: float
    cy: float
    r: float


@dataclass
class CoordinateMapper:
    """Coordinate mapper between display and full-image space."""

    scale: float = 1.0
    offset: Tuple[float, float] = (0.0, 0.0)

    def to_full(self, x: float, y: float) -> Tuple[float, float]:
        return (x * self.scale + self.offset[0], y * self.scale + self.offset[1])

    def to_display(self, x: float, y: float) -> Tuple[float, float]:
        return ((x - self.offset[0]) / self.scale, (y - self.offset[1]) / self.scale)


class RoiInteractor:
    """Interactive ROI editor for a Matplotlib Axes."""

    def __init__(
        self,
        ax,
        on_change: Callable[[str, Optional[RectROI], Optional[CircleROI]], None],
        min_size_px: float = 3.0,
        handle_size_px: float = 10.0,
    ) -> None:
        self.ax = ax
        self.canvas = ax.figure.canvas
        self.on_change = on_change
        self.min_size_px = min_size_px
        self.handle_size_px = handle_size_px
        self.mapper = CoordinateMapper()
        self.mode = "idle"
        self._rect: Optional[RectROI] = None
        self._circle: Optional[CircleROI] = None
        self._drag_start: Optional[Tuple[float, float]] = None
        self._drag_mode: Optional[str] = None
        self._show_handles = True
        self._rect_patch = None
        self._circle_patch = None
        self._handles = []
        self._connect()

    def _connect(self) -> None:
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

    def set_tool(self, mode: str) -> None:
        self.mode = mode

    def set_mapper(self, scale: float, offset: Tuple[float, float]) -> None:
        self.mapper = CoordinateMapper(scale=scale, offset=offset)
        self._refresh_artists()

    def set_show_handles(self, show: bool) -> None:
        self._show_handles = show
        self._refresh_handles()

    def set_rect_roi(self, roi: RectROI, *, emit: bool = False) -> None:
        self._rect = roi
        self._circle = None
        self._refresh_artists()
        if emit:
            self.on_change("box", self._rect, None)

    def set_circle_roi(self, roi: CircleROI, *, emit: bool = False) -> None:
        self._circle = roi
        self._rect = None
        self._refresh_artists()
        if emit:
            self.on_change("circle", None, self._circle)

    def clear_roi(self, *, emit: bool = False) -> None:
        self._rect = None
        self._circle = None
        self._remove_artists()
        if emit:
            self.on_change("none", None, None)

    def get_roi(self) -> Tuple[str, Optional[RectROI], Optional[CircleROI]]:
        if self._rect is not None:
            return ("box", self._rect, None)
        if self._circle is not None:
            return ("circle", None, self._circle)
        return ("none", None, None)

    def _on_press(self, event) -> None:
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
        if self._drag_start is None or self._drag_mode is None:
            return
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            return
        fx, fy = self.mapper.to_full(event.xdata, event.ydata)
        if self._drag_mode == "draw_rect" and self._rect is not None:
            x0, y0 = self._drag_start
            x = min(x0, fx)
            y = min(y0, fy)
            w = abs(fx - x0)
            h = abs(fy - y0)
            self._rect = RectROI(x, y, w, h)
            self._emit_change()
        elif self._drag_mode == "draw_circle" and self._circle is not None:
            cx, cy = self._drag_start
            r = ((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5
            self._circle = CircleROI(cx, cy, r)
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
            r = ((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5
            self._circle = CircleROI(cx, cy, max(r, self.min_size_px))
            self._emit_change()

    def _on_release(self, event) -> None:
        if self._drag_start is None:
            return
        self._drag_start = None
        self._drag_mode = None

    def _emit_change(self) -> None:
        self._refresh_artists()
        roi_type, rect, circle = self.get_roi()
        if rect and (rect.w < self.min_size_px or rect.h < self.min_size_px):
            return
        if circle and circle.r < self.min_size_px:
            return
        self.on_change(roi_type, rect, circle)

    def _hit_test(self, fx: float, fy: float) -> str:
        if self._rect is not None:
            handle = self._hit_rect_handle(fx, fy)
            if handle:
                return handle
            if self._point_in_rect(fx, fy, self._rect):
                return "move"
        if self._circle is not None:
            if self._point_in_circle(fx, fy, self._circle):
                return "move_circle"
            if self._hit_circle_radius(fx, fy, self._circle):
                return "radius"
        return "none"

    def _hit_rect_handle(self, fx: float, fy: float) -> Optional[str]:
        rect = self._rect
        if rect is None:
            return None
        corners = {
            "resize_nw": (rect.x, rect.y),
            "resize_ne": (rect.x + rect.w, rect.y),
            "resize_sw": (rect.x, rect.y + rect.h),
            "resize_se": (rect.x + rect.w, rect.y + rect.h),
        }
        for key, (x, y) in corners.items():
            if abs(fx - x) <= self.handle_size_px and abs(fy - y) <= self.handle_size_px:
                return key
        return None

    def _hit_circle_radius(self, fx: float, fy: float, circle: CircleROI) -> bool:
        r = circle.r
        dist = ((fx - circle.cx) ** 2 + (fy - circle.cy) ** 2) ** 0.5
        return abs(dist - r) <= self.handle_size_px

    def _point_in_rect(self, fx: float, fy: float, rect: RectROI) -> bool:
        return rect.x <= fx <= rect.x + rect.w and rect.y <= fy <= rect.y + rect.h

    def _point_in_circle(self, fx: float, fy: float, circle: CircleROI) -> bool:
        return (fx - circle.cx) ** 2 + (fy - circle.cy) ** 2 <= circle.r**2

    def _resize_rect(self, fx: float, fy: float, handle: str) -> None:
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
