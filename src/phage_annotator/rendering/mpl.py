"""Matplotlib rendering helpers decoupled from the main window.

This module provides pure, testable rendering functions for displaying microscopy
data in matplotlib figures. Key responsibilities:

1. Projection rendering: Mean/std projections over (T, Z) axes
2. Coordinate transforms: Full image <-> display (cropped/downsampled)
3. Overlay rendering: Annotations, ROI, particles, density maps, SMLM results
4. Color mapping: Apply LUT, invert, gamma correction, log scaling

Architecture
------------
- All functions are Qt-free and thread-safe
- Coordinate conventions follow numpy (y, x) ordering
- Downsampling uses mean pooling (fast, non-anti-aliased)
- Overlay coordinates must be in display space (after crop/downsample)

Key Functions
-------------
- render_2d_image(): Render single frame with all overlays
- render_projection(): Render mean/std projections
- draw_*(): Low-level overlay drawing (annotations, ROI, particles)
- coordinate_full_to_display(): Transform full-res coords to display space
- coordinate_display_to_full(): Inverse transform

Conventions
-----------
- All internal coordinates use (y, x) to match numpy
- Display coords are post-crop, post-downsample
- Overlays must be provided in display-space coordinates
- Canvas/axes coords use matplotlib conventions (may be inverted)
"""

from __future__ import annotations

from phage_annotator.rendering.mpl_canvas import RenderContext
from phage_annotator.rendering.mpl_utils import (
    _update_or_create,
    _normalize_overlay_to_uint8,
    _clear_overlays,
)
from phage_annotator.rendering.renderer_base import RendererBase
from phage_annotator.rendering.renderer_overlays import RendererOverlaysMixin
from phage_annotator.rendering.renderer_export import RendererExportMixin


class Renderer(RendererBase, RendererOverlaysMixin, RendererExportMixin):
    """Renderer responsible for figure layout and artist updates."""

    pass
