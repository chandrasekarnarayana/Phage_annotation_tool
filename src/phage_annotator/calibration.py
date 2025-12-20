"""Calibration helpers for pixel size and unit conversions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class CalibrationState:
    """Resolved calibration state for an image."""

    pixel_size_um_per_px: Optional[float]
    source: str


def resolve_calibration(
    summary: Dict[str, object],
    user_value_um_per_px: Optional[float],
    project_default_um_per_px: Optional[float],
) -> CalibrationState:
    """Resolve pixel size in um/px using metadata, user, or project defaults."""
    pixel_size = _pixel_size_from_summary(summary)
    if pixel_size is not None:
        return CalibrationState(pixel_size_um_per_px=pixel_size, source="metadata")
    if user_value_um_per_px:
        return CalibrationState(pixel_size_um_per_px=float(user_value_um_per_px), source="user")
    if project_default_um_per_px:
        return CalibrationState(pixel_size_um_per_px=float(project_default_um_per_px), source="project_default")
    return CalibrationState(pixel_size_um_per_px=None, source="unknown")


def _pixel_size_from_summary(summary: Dict[str, object]) -> Optional[float]:
    value = summary.get("pixel_size_um")
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, dict):
        for key in ("x", "y"):
            if key in value and value[key] is not None:
                try:
                    return float(value[key])
                except (TypeError, ValueError):
                    continue
    return None
