"""Tool routing for interactive canvas behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Set, Tuple


class Tool(Enum):
    """Interactive tool modes for the canvas."""

    PAN_ZOOM = "PAN_ZOOM"
    ANNOTATE_POINT = "ANNOTATE_POINT"
    ROI_BOX = "ROI_BOX"
    ROI_CIRCLE = "ROI_CIRCLE"
    ROI_EDIT = "ROI_EDIT"
    PROFILE_LINE = "PROFILE_LINE"
    ERASER = "ERASER"


@dataclass
class ToolCallbacks:
    """Callback interface for ToolRouter to interact with the GUI."""

    get_target_ax: Callable[[], object]
    get_image_axes: Callable[[], Set[object]]
    get_tz: Callable[[], Tuple[int, int]]
    get_primary_image_id: Callable[[], int]
    get_label: Callable[[], str]
    get_scope: Callable[[], str]
    map_to_fullres: Callable[[object, float, float], Tuple[float, float]]
    point_in_roi: Callable[[float, float], bool]
    add_point: Callable[[int, int, int, float, float, str, str], None]
    remove_near: Callable[[object, int, int, float, float], bool]
    set_roi_rect: Callable[[Tuple[float, float, float, float]], None]
    set_roi_shape: Callable[[str], None]
    set_profile_line: Callable[[Tuple[Tuple[float, float], Tuple[float, float]]], None]
    set_profile_mode: Callable[[bool], None]
    refresh: Callable[[], None]
    set_status: Callable[[str], None]


class ToolRouter:
    """Route Matplotlib mouse events to the active tool behavior."""

    def __init__(self, callbacks: ToolCallbacks) -> None:
        self._cb = callbacks
        self.tool = Tool.ANNOTATE_POINT
        self._drag_start: Optional[Tuple[float, float]] = None

    def set_tool(self, tool: Tool) -> None:
        """Set the active tool and reset drag state."""
        self.tool = tool
        self._drag_start = None
        if tool == Tool.PROFILE_LINE:
            self._cb.set_profile_mode(True)
        else:
            self._cb.set_profile_mode(False)

    def on_click(self, event) -> None:
        """Handle click actions for annotate/erase tools."""
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return
        if self.tool == Tool.PAN_ZOOM:
            return
        if self.tool in (Tool.ANNOTATE_POINT, Tool.ERASER):
            target_ax = self._cb.get_target_ax()
            if event.inaxes is not target_ax:
                return
            fx, fy = self._cb.map_to_fullres(target_ax, event.xdata, event.ydata)
            if not self._cb.point_in_roi(fx, fy):
                self._cb.set_status("Click outside ROI ignored")
                return
            t, z = self._cb.get_tz()
            if self.tool == Tool.ERASER:
                if self._cb.remove_near(target_ax, t, z, fx, fy):
                    self._cb.refresh()
                return
            if self._cb.remove_near(target_ax, t, z, fx, fy):
                self._cb.refresh()
                return
            self._cb.add_point(
                self._cb.get_primary_image_id(),
                t,
                z,
                fy,
                fx,
                self._cb.get_label(),
                self._cb.get_scope(),
            )
            self._cb.refresh()
            return

    def on_press(self, event) -> None:
        """Handle press events that start ROI/profile drags."""
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return
        if event.inaxes not in self._cb.get_image_axes():
            return
        if self.tool in (Tool.ROI_BOX, Tool.ROI_CIRCLE, Tool.ROI_EDIT):
            return
        if self.tool == Tool.PROFILE_LINE:
            fx, fy = self._cb.map_to_fullres(event.inaxes, event.xdata, event.ydata)
            self._drag_start = (fx, fy)
            if self.tool == Tool.PROFILE_LINE:
                self._cb.set_profile_line(((fy, fx), (fy, fx)))
                self._cb.refresh()

    def on_motion(self, event) -> None:
        """Handle drag motion for ROI/profile updates."""
        if self._drag_start is None or event.xdata is None or event.ydata is None:
            return
        if self.tool in (Tool.ROI_BOX, Tool.ROI_CIRCLE, Tool.ROI_EDIT):
            return
        x0, y0 = self._drag_start
        fx, fy = self._cb.map_to_fullres(event.inaxes, event.xdata, event.ydata)
        if self.tool == Tool.PROFILE_LINE:
            self._cb.set_profile_line(((y0, x0), (fy, fx)))
            self._cb.refresh()

    def on_release(self, event) -> None:
        """Handle drag release to finalize ROI/profile selection."""
        if self._drag_start is None:
            return
        if self.tool == Tool.PROFILE_LINE:
            self._drag_start = None
