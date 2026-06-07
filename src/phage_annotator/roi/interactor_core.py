"""Core state and public setters for the ROI interactor."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from phage_annotator.roi.interactor_types import CircleROI, CoordinateMapper, RectROI


class RoiInteractorCoreMixin:
    """Initialize ROI interactor state and expose public state setters."""

    def __init__(
        self,
        ax,
        on_change: Callable[[str, Optional[RectROI], Optional[CircleROI]], None],
        min_size_px: float = 3.0,
        handle_size_px: float = 10.0,
    ) -> None:
        """Create an interactive ROI editor bound to a matplotlib axes."""
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
        """Connect matplotlib mouse callbacks to the interactor handlers."""
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

    def set_tool(self, mode: str) -> None:
        """Set the active ROI tool mode."""
        self.mode = mode

    def set_mapper(self, scale: float, offset: Tuple[float, float]) -> None:
        """Update coordinate mapping and redraw current ROI artists."""
        self.mapper = CoordinateMapper(scale=scale, offset=offset)
        self._refresh_artists()

    def set_show_handles(self, show: bool) -> None:
        """Toggle ROI resize/move handles."""
        self._show_handles = show
        self._refresh_handles()

    def set_rect_roi(self, roi: RectROI, *, emit: bool = False) -> None:
        """Set the active rectangle ROI."""
        self._rect = roi
        self._circle = None
        self._refresh_artists()
        if emit:
            self.on_change("box", self._rect, None)

    def set_circle_roi(self, roi: CircleROI, *, emit: bool = False) -> None:
        """Set the active circle ROI."""
        self._circle = roi
        self._rect = None
        self._refresh_artists()
        if emit:
            self.on_change("circle", None, self._circle)

    def clear_roi(self, *, emit: bool = False) -> None:
        """Clear all active ROI state and artists."""
        self._rect = None
        self._circle = None
        self._remove_artists()
        if emit:
            self.on_change("none", None, None)

    def get_roi(self) -> Tuple[str, Optional[RectROI], Optional[CircleROI]]:
        """Return the active ROI type and object."""
        if self._rect is not None:
            return ("box", self._rect, None)
        if self._circle is not None:
            return ("circle", None, self._circle)
        return ("none", None, None)
