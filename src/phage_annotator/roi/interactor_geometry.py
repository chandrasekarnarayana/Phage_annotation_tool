"""Hit testing and geometry updates for the ROI interactor."""

from __future__ import annotations

from typing import Optional

from phage_annotator.roi.interactor_types import CircleROI, RectROI


class RoiInteractorGeometryMixin:
    """Provide ROI hit-testing and resize geometry helpers."""

    def _hit_test(self, fx: float, fy: float) -> str:
        """Return the edit operation under the cursor."""
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
        """Return the rectangle resize handle under the cursor."""
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
        """Check whether the cursor is on the circle radius handle."""
        dist = ((fx - circle.cx) ** 2 + (fy - circle.cy) ** 2) ** 0.5
        return abs(dist - circle.r) <= self.handle_size_px

    def _point_in_rect(self, fx: float, fy: float, rect: RectROI) -> bool:
        """Check whether a full-space point is inside a rectangle ROI."""
        return rect.x <= fx <= rect.x + rect.w and rect.y <= fy <= rect.y + rect.h

    def _point_in_circle(self, fx: float, fy: float, circle: CircleROI) -> bool:
        """Check whether a full-space point is inside a circle ROI."""
        return (fx - circle.cx) ** 2 + (fy - circle.cy) ** 2 <= circle.r**2

    def _resize_rect(self, fx: float, fy: float, handle: str) -> None:
        """Resize the active rectangle from one of its corner handles."""
        rect = self._rect
        if rect is None:
            return
        x0, y0, x1, y1 = rect.x, rect.y, rect.x + rect.w, rect.y + rect.h
        if handle == "resize_nw":
            x0, y0 = fx, fy
        elif handle == "resize_ne":
            x1, y0 = fx, fy
        elif handle == "resize_sw":
            x0, y1 = fx, fy
        elif handle == "resize_se":
            x1, y1 = fx, fy
        self._rect = RectROI(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
