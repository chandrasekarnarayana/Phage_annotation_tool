"""Renderer export methods: render view to image array for file export."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from phage_annotator.ui_qt.rendering.export_view import ExportOptions, render_view_to_array
from phage_annotator.rendering.mpl_canvas import RenderContext
from phage_annotator.rendering.scalebar import ScaleBarSpec


class RendererExportMixin:
    """Mixin providing export/save rendering to the Renderer."""

    def render_to_image(self, ctx: RenderContext, options: ExportOptions) -> np.ndarray:
        """Render a view to an RGBA image for export."""
        panel = options.panel
        image = ctx.panel_images.get(panel)
        if image is None:
            image = ctx.image_frame
        if image is None:
            return np.zeros((1, 1, 4), dtype=np.uint8)
        annotations = ctx.panel_annotations.get(panel, [])
        roi_overlays = list(ctx.roi_overlays.get(panel, []))
        if ctx.roi_rect and ctx.roi_type in ("box", "circle"):
            x, y, w, h = ctx.roi_rect
            off_x, off_y = ctx.roi_offset
            scale = ctx.roi_scale if ctx.roi_scale else 1.0
            rect = ((x - off_x) / scale, (y - off_y) / scale, w / scale, h / scale)
            roi_overlays.append((ctx.roi_type, rect, "#ffd166"))
        particle_overlays = ctx.particle_overlays if panel == ctx.primary_panel else []
        overlay_text = ctx.overlay_text if options.include_overlay_text else None
        scalebar_spec = None
        if ctx.scale_bar and options.include_scalebar:
            scalebar_spec = ScaleBarSpec(
                enabled=True,
                length_um=0.0,
                thickness_px=(int(ctx.scale_bar["rect"][3]) if ctx.scale_bar.get("rect") else 4),
                location="bottom_right",
                padding_px=12,
                show_text=bool(ctx.scale_bar.get("text")),
                text_offset_px=6,
                background_box=True,
            )
        return render_view_to_array(
            image,
            cmap=ctx.panel_cmaps.get(panel, self.colormaps[0]),
            norm=ctx.norms.get(panel),
            overlays=[],
            annotations=[(x, y, c) for x, y, c, _ in annotations],
            annotation_labels=[],
            roi_overlays=roi_overlays,
            particle_overlays=particle_overlays,
            overlay_text=overlay_text,
            scalebar_spec=scalebar_spec,
            pixel_size_um=None,
            options=options,
        )
