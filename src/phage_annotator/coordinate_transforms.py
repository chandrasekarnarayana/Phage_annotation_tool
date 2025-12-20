"""Central, testable coordinate transformation utilities.

Single source of truth for all pixel/canvas/display coordinate conversions.
All functions are Qt-free and fully testable.

Conventions
-----------
- Full-resolution coords: (y, x) in full image array space
- Display coords: (y, x) in matplotlib canvas space after crop/downsample
- Canvas coords: (x, y) in matplotlib axis units (inverted x)
"""

from __future__ import annotations

from typing import Tuple

__all__ = [
    "full_to_display",
    "display_to_full",
    "crop_to_full",
    "full_to_crop",
    "canvas_to_display",
    "display_to_canvas",
    "crop_rect_intersection",
    "roi_rect_in_display_coords",
]


def crop_to_full(
    y_disp: float, x_disp: float, crop_rect: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Convert cropped display coordinates to full image coordinates.

    Parameters
    ----------
    y_disp, x_disp : float
        Coordinates in cropped image space.
    crop_rect : tuple[float, float, float, float]
        Crop region as (x_crop, y_crop, w_crop, h_crop) in full-resolution space.

    Returns
    -------
    y_full, x_full : tuple[float, float]
        Coordinates in full image space.
    """
    x_crop, y_crop, w_crop, h_crop = crop_rect
    x_full = x_disp + x_crop
    y_full = y_disp + y_crop
    return y_full, x_full


def full_to_crop(
    y_full: float, x_full: float, crop_rect: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Convert full image coordinates to cropped display coordinates.

    Parameters
    ----------
    y_full, x_full : float
        Coordinates in full image space.
    crop_rect : tuple[float, float, float, float]
        Crop region as (x_crop, y_crop, w_crop, h_crop) in full-resolution space.

    Returns
    -------
    y_disp, x_disp : tuple[float, float]
        Coordinates in cropped space (or NaN if outside crop region).
    """
    x_crop, y_crop, w_crop, h_crop = crop_rect
    x_disp = x_full - x_crop
    y_disp = y_full - y_crop
    return y_disp, x_disp


def full_to_display(
    y_full: float,
    x_full: float,
    crop_rect: Tuple[float, float, float, float],
    downsample: float = 1.0,
) -> Tuple[float, float]:
    """Convert full-resolution coordinates to display (downsampled) coordinates.

    Parameters
    ----------
    y_full, x_full : float
        Coordinates in full image space.
    crop_rect : tuple[float, float, float, float]
        Crop region as (x_crop, y_crop, w_crop, h_crop) in full-resolution space.
    downsample : float
        Downsampling factor (display_pixel_size / full_pixel_size).

    Returns
    -------
    y_disp, x_disp : tuple[float, float]
        Coordinates in display space.
    """
    y_crop, x_crop = full_to_crop(y_full, x_full, crop_rect)
    return y_crop / downsample, x_crop / downsample


def display_to_full(
    y_disp: float,
    x_disp: float,
    crop_rect: Tuple[float, float, float, float],
    downsample: float = 1.0,
) -> Tuple[float, float]:
    """Convert display (downsampled) coordinates to full-resolution coordinates.

    Parameters
    ----------
    y_disp, x_disp : float
        Coordinates in display space.
    crop_rect : tuple[float, float, float, float]
        Crop region as (x_crop, y_crop, w_crop, h_crop) in full-resolution space.
    downsample : float
        Downsampling factor (display_pixel_size / full_pixel_size).

    Returns
    -------
    y_full, x_full : tuple[float, float]
        Coordinates in full-resolution space.
    """
    y_crop = y_disp * downsample
    x_crop = x_disp * downsample
    return crop_to_full(y_crop, x_crop, crop_rect)


def canvas_to_display(x_canvas: float, y_canvas: float) -> Tuple[float, float]:
    """Convert matplotlib canvas coordinates to image display coordinates.

    Matplotlib axes use (x, y) with x horizontal and y inverted.
    Display uses (y, x) with origin at top-left.

    Parameters
    ----------
    x_canvas, y_canvas : float
        Coordinates in matplotlib axis space.

    Returns
    -------
    y_disp, x_disp : tuple[float, float]
        Coordinates in display space (row, col).
    """
    return y_canvas, x_canvas


def display_to_canvas(y_disp: float, x_disp: float) -> Tuple[float, float]:
    """Convert image display coordinates to matplotlib canvas coordinates.

    Parameters
    ----------
    y_disp, x_disp : float
        Coordinates in display space (row, col).

    Returns
    -------
    x_canvas, y_canvas : tuple[float, float]
        Coordinates in matplotlib axis space.
    """
    return x_disp, y_disp


def crop_rect_intersection(
    crop_rect: Tuple[float, float, float, float],
    image_shape_yx: Tuple[int, int],
) -> Tuple[float, float, float, float]:
    """Clip crop rectangle to image bounds.

    Parameters
    ----------
    crop_rect : tuple[float, float, float, float]
        (x_crop, y_crop, w_crop, h_crop) in full-resolution space.
    image_shape_yx : tuple[int, int]
        (height, width) of the full image.

    Returns
    -------
    clipped_rect : tuple[float, float, float, float]
        Clipped crop rectangle.
    """
    x_crop, y_crop, w_crop, h_crop = crop_rect
    img_h, img_w = image_shape_yx

    # Clamp origin
    x_crop = max(0.0, min(float(img_w - 1), x_crop))
    y_crop = max(0.0, min(float(img_h - 1), y_crop))

    # Clamp size to boundaries
    max_w = img_w - x_crop
    max_h = img_h - y_crop
    w_crop = max(1.0, min(float(max_w), w_crop))
    h_crop = max(1.0, min(float(max_h), h_crop))

    return x_crop, y_crop, w_crop, h_crop


def roi_rect_in_display_coords(
    roi_rect_full: Tuple[float, float, float, float],
    crop_rect: Tuple[float, float, float, float],
    downsample: float = 1.0,
) -> Tuple[float, float, float, float]:
    """Project ROI rectangle from full-resolution to display coordinates.

    Parameters
    ----------
    roi_rect_full : tuple[float, float, float, float]
        ROI as (x, y, w, h) in full-resolution space.
    crop_rect : tuple[float, float, float, float]
        Crop region as (x_crop, y_crop, w_crop, h_crop) in full-resolution space.
    downsample : float
        Downsampling factor.

    Returns
    -------
    roi_rect_disp : tuple[float, float, float, float]
        ROI as (x, y, w, h) in display space.
    """
    x_full, y_full, w_full, h_full = roi_rect_full

    # Convert top-left corner
    y_disp_tl, x_disp_tl = full_to_display(y_full, x_full, crop_rect, downsample)

    # Convert dimensions
    y_disp_br, x_disp_br = full_to_display(y_full + h_full, x_full + w_full, crop_rect, downsample)

    w_disp = x_disp_br - x_disp_tl
    h_disp = y_disp_br - y_disp_tl

    return x_disp_tl, y_disp_tl, w_disp, h_disp
