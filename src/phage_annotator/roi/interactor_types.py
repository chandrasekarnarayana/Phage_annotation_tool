"""Shared ROI interactor data structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class RectROI:
    """Rectangle ROI in full-image coordinates."""

    x: float
    y: float
    w: float
    h: float


@dataclass
class CircleROI:
    """Circle ROI in full-image coordinates."""

    cx: float
    cy: float
    r: float


@dataclass
class CoordinateMapper:
    """Coordinate mapper between display and full-image space."""

    scale: float = 1.0
    offset: Tuple[float, float] = (0.0, 0.0)

    def to_full(self, x: float, y: float) -> Tuple[float, float]:
        """Convert display coordinates into full-image coordinates."""
        return (x * self.scale + self.offset[0], y * self.scale + self.offset[1])

    def to_display(self, x: float, y: float) -> Tuple[float, float]:
        """Convert full-image coordinates into display coordinates."""
        return ((x - self.offset[0]) / self.scale, (y - self.offset[1]) / self.scale)
