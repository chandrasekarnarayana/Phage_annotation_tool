"""I/O-related data utilities."""

from phage_annotator.io.data.calibration import CalibrationState, resolve_calibration
from phage_annotator.io.data.transforms import (
    canvas_to_display,
    crop_rect_intersection,
    crop_to_full,
    display_to_canvas,
    display_to_full,
    full_to_crop,
    full_to_display,
    roi_rect_in_display_coords,
)

__all__ = [
    "CalibrationState",
    "resolve_calibration",
    "canvas_to_display",
    "crop_rect_intersection",
    "crop_to_full",
    "display_to_canvas",
    "display_to_full",
    "full_to_crop",
    "full_to_display",
    "roi_rect_in_display_coords",
]
