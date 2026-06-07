"""Rendering pipeline - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.rendering.renderer_overlays import RenderingOverlayMixin
from phage_annotator.ui_qt.rendering.renderer_frame import RenderingFrameMixin
from phage_annotator.ui_qt.rendering.renderer_refresh import RenderingRefreshMixin
from phage_annotator.ui_qt.rendering.renderer_hist import RenderingHistMixin
from phage_annotator.ui_qt.rendering.renderer_view import RenderingViewMixin


class RenderingMixin(
    RenderingOverlayMixin,
    RenderingFrameMixin,
    RenderingRefreshMixin,
    RenderingHistMixin,
    RenderingViewMixin,
):
    """Aggregated mixin for the full rendering pipeline."""
    pass
