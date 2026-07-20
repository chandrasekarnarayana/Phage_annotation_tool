"""Extracted method group 1 for RoiInteractor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import matplotlib.pyplot as plt

from phage_annotator.roi.interactor_types import CircleROI, CoordinateMapper, RectROI


class RoiModelMixin:
    """Method group 1 extracted from RoiInteractor."""

    def __init__(
        self,
        ax,
        on_change: Callable[[str, Optional[RectROI], Optional[CircleROI]], None],
        min_size_px: float = 3.0,
        handle_size_px: float = 10.0,
    ) -> None:
        """Initialize the object and prepare its runtime state."""
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
        """Connect connect for the current workflow."""
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
    def set_tool(self, mode: str) -> None:
        """Set tool for the current workflow."""
        self.mode = mode
    def set_mapper(self, scale: float, offset: Tuple[float, float]) -> None:
        """Set mapper for the current workflow."""
        self.mapper = CoordinateMapper(scale=scale, offset=offset)
        self._refresh_artists()
    def set_show_handles(self, show: bool) -> None:
        """Set show handles for the current workflow."""
        self._show_handles = show
        self._refresh_handles()
    def set_rect_roi(self, roi: RectROI, *, emit: bool = False) -> None:
        """Set rect roi for the current workflow."""
        self._rect = roi
        self._circle = None
        self._refresh_artists()
        if emit:
            self.on_change("box", self._rect, None)
    def set_circle_roi(self, roi: CircleROI, *, emit: bool = False) -> None:
        """Set circle roi for the current workflow."""
        self._circle = roi
        self._rect = None
        self._refresh_artists()
        if emit:
            self.on_change("circle", None, self._circle)
    def clear_roi(self, *, emit: bool = False) -> None:
        """Clear roi for the current workflow."""
        self._rect = None
        self._circle = None
        self._remove_artists()
        if emit:
            self.on_change("none", None, None)
    def get_roi(self) -> Tuple[str, Optional[RectROI], Optional[CircleROI]]:
        """Return roi for the current workflow."""
        if self._rect is not None:
            return ("box", self._rect, None)
        if self._circle is not None:
            return ("circle", None, self._circle)
        return ("none", None, None)
    def _on_press(self, event) -> None:
        """Handle the on press helper flow."""
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
        """Handle the on motion helper flow."""
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
        """Handle the on release helper flow."""
        if self._drag_start is None:
            return
        self._drag_start = None
        self._drag_mode = None
    def _emit_change(self) -> None:
        """Emit change for the current workflow."""
        self._refresh_artists()
        roi_type, rect, circle = self.get_roi()
        if rect and (rect.w < self.min_size_px or rect.h < self.min_size_px):
            return
        if circle and circle.r < self.min_size_px:
            return
        self.on_change(roi_type, rect, circle)
    def _hit_test(self, fx: float, fy: float) -> str:
        """Handle the hit test helper flow."""
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
        """Handle the hit rect handle helper flow."""
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
        """Handle the hit circle radius helper flow."""
        r = circle.r
        dist = ((fx - circle.cx) ** 2 + (fy - circle.cy) ** 2) ** 0.5
        return abs(dist - r) <= self.handle_size_px
    def _point_in_rect(self, fx: float, fy: float, rect: RectROI) -> bool:
        """Handle the point in rect helper flow."""
        return rect.x <= fx <= rect.x + rect.w and rect.y <= fy <= rect.y + rect.h
