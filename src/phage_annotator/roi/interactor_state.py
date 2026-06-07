"""ROI interactor state: dataclasses, coordinate mapper, and tool state management."""

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
        """Convert display coords to full-image coords."""
        return (x * self.scale + self.offset[0], y * self.scale + self.offset[1])

    def to_display(self, x: float, y: float) -> Tuple[float, float]:
        """Convert full-image coords to display coords."""
        return ((x - self.offset[0]) / self.scale, (y - self.offset[1]) / self.scale)


class RoiInteractorState:
    """Base class managing state and artist lifecycle for ROI interaction."""

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
        """Connect matplotlib event callbacks."""
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
        """Return current ROI state."""
        if self._rect is not None:
            return ("box", self._rect, None)
        if self._circle is not None:
            return ("circle", None, self._circle)
        return ("none", None, None)

    def _refresh_artists(self) -> None:
        """Refresh matplotlib patches for the current ROI."""
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
        """Refresh resize handle markers."""
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
        """Remove all matplotlib artists."""
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
