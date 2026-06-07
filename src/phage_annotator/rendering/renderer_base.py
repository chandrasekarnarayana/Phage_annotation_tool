"""Renderer base: figure layout, axis management, and image artist updates."""

from __future__ import annotations

# Unified logging through service framework
try:
    from phage_annotator.framework import get_log_service
    _logger = get_log_service().get_logger(__name__)
except (ImportError, RuntimeError, AttributeError):
    import logging
    _logger = logging.getLogger(__name__)

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np

from phage_annotator.roi.interactor import CircleROI, RectROI, RoiInteractor
from phage_annotator.rendering.mpl_canvas import RenderContext
from phage_annotator.rendering.mpl_utils import (
    _clear_overlays,
    _normalize_overlay_to_uint8,
    _update_or_create,
)


class RendererBase:
    """Base renderer: figure layout, axis management, and image artist updates."""

    def __init__(
        self,
        figure: matplotlib.figure.Figure,
        canvas: Any,
        colormaps: Sequence[matplotlib.colors.Colormap],
    ) -> None:
        """Initialize the object and prepare its runtime state."""
        self.figure = figure
        self.canvas = canvas
        self.colormaps = list(colormaps)
        self.axes: Dict[str, matplotlib.axes.Axes] = {}
        self.image_artists: Dict[str, Optional[matplotlib.image.AxesImage]] = {
            "frame_overlay": None,
            "threshold_overlay": None,
        }
        self.overlay_text = None
        self.canvas_header_text = None
        self.scale_bar_patch = None
        self.scale_bar_text = None
        self.scale_bar_warning = None
        self.roi_interactor: Optional[RoiInteractor] = None
        self._roi_callback: Optional[
            Callable[[str, Optional[RectROI], Optional[CircleROI]], None]
        ] = None
        self._layout_key: Tuple[str, ...] = ()

    def request_layout_rebuild(self, layout_spec: Dict[str, object]) -> bool:
        """Return True if layout requires rebuilding based on panel visibility."""
        order: List[str] = layout_spec.get("order", [])
        visible: Tuple[str, ...] = tuple(
            [key for key in order if layout_spec.get("panel_visibility", {}).get(key, False)]
        )
        return visible != self._layout_key

    def init_figure(self, layout_spec: Dict[str, object]) -> Dict[str, matplotlib.axes.Axes]:
        """Build image panel axes according to the layout spec."""
        order: List[str] = layout_spec.get("order", [])
        panel_visibility: Dict[str, bool] = layout_spec.get("panel_visibility", {})
        visible: List[str] = [key for key in order if panel_visibility.get(key, False)]
        if not visible:
            return {}
        self._layout_key = tuple(visible)
        self.figure.clear()
        self.figure.set_constrained_layout(True)
        gs = self.figure.add_gridspec(1, len(visible))
        axes: Dict[str, matplotlib.axes.Axes] = {}
        base_ax: Optional[matplotlib.axes.Axes] = None
        for idx, panel in enumerate(visible):
            ax = self.figure.add_subplot(gs[0, idx], sharex=base_ax, sharey=base_ax)
            if base_ax is None:
                base_ax = ax
            ax.set_aspect("auto")
            axes[panel] = ax
        self.axes = axes
        for key in self.image_artists:
            self.image_artists[key] = None
        self.overlay_text = None
        self.canvas_header_text = None
        roi_ax = next(iter(axes.values()), None)
        if roi_ax is not None:
            self.roi_interactor = RoiInteractor(roi_ax, self._on_roi_change)
            if self._roi_callback is not None:
                self.roi_interactor.on_change = self._roi_callback
        self.canvas.draw_idle()
        return axes

    def get_axis(self, panel: str):
        """Return renderer-owned axis for panel key, if available."""
        return self.axes.get(str(panel))

    def init_external_axes(
        self,
        axes: Dict[str, matplotlib.axes.Axes],
        layout_key: Sequence[str],
    ) -> Dict[str, matplotlib.axes.Axes]:
        """Initialize renderer state using externally managed axes.

        Parameters
        ----------
        axes : dict[str, matplotlib.axes.Axes]
            Pre-built axes keyed by panel name.
        layout_key : Sequence[str]
            Visible panel order used for layout caching.
        """
        self._layout_key = tuple(layout_key)
        self.axes = axes
        for key in self.image_artists:
            self.image_artists[key] = None
        self.overlay_text = None
        self.canvas_header_text = None
        roi_ax = next(iter(axes.values()), None)
        if roi_ax is not None:
            self.roi_interactor = RoiInteractor(roi_ax, self._on_roi_change)
            if self._roi_callback is not None:
                self.roi_interactor.on_change = self._roi_callback
        self.canvas.draw_idle()
        return axes

    def update_images(self, ctx: RenderContext) -> None:
        """Update image artists in-place for all visible panels."""
        titles = ctx.titles
        for key, ax in self.axes.items():
            ax.set_title(titles.get(key, ""))
        for key in list(self.image_artists.keys()):
            if key in {"frame_overlay", "threshold_overlay"}:
                continue
            if key not in self.axes:
                self.image_artists.pop(key, None)
        for key, data in ctx.panel_images.items():
            if key not in self.axes or data is None:
                continue
            norm = ctx.norms.get(key)
            prange = ctx.panel_ranges.get(key, ctx.std_range)
            cmap = ctx.panel_cmaps.get(key, self.colormaps[0])
            self.image_artists[key] = _update_or_create(
                self.axes[key],
                self.image_artists.get(key),
                data,
                cmap,
                prange[0],
                prange[1],
                ctx.extents.get(key),
                norm=norm,
            )
        primary_ax = self.axes.get(ctx.primary_panel)
        if primary_ax is not None:
            overlay = ctx.overlay_frame
            if overlay is not None:
                overlay_uint8 = _normalize_overlay_to_uint8(overlay)
                self.image_artists["frame_overlay"] = _update_or_create(
                    primary_ax,
                    self.image_artists["frame_overlay"],
                    overlay_uint8,
                    ctx.overlay_cmap or colormaps.get_cmap("magma"),
                    0.0,
                    255.0,
                    ctx.overlay_extent,
                    norm=ctx.overlay_norm,
                )
                if self.image_artists["frame_overlay"] is not None:
                    self.image_artists["frame_overlay"].set_alpha(ctx.overlay_alpha)
                    self.image_artists["frame_overlay"].set_zorder(3)
                    self.image_artists["frame_overlay"].set_visible(True)
            elif self.image_artists.get("frame_overlay") is not None:
                self.image_artists["frame_overlay"].set_visible(False)
            if ctx.threshold_visible and ctx.threshold_mask is not None:
                threshold_data = _normalize_overlay_to_uint8(ctx.threshold_mask)
                self.image_artists["threshold_overlay"] = _update_or_create(
                    primary_ax,
                    self.image_artists["threshold_overlay"],
                    threshold_data,
                    colormaps.get_cmap("Reds"),
                    0.0,
                    255.0,
                    ctx.threshold_extent,
                    norm=None,
                )
                if self.image_artists["threshold_overlay"] is not None:
                    self.image_artists["threshold_overlay"].set_alpha(0.35)
                    self.image_artists["threshold_overlay"].set_zorder(2.5)
                    self.image_artists["threshold_overlay"].set_visible(True)
            elif self.image_artists.get("threshold_overlay") is not None:
                self.image_artists["threshold_overlay"].set_visible(False)
        self._flush()

    def _flush(self) -> None:
        """Flush canvas updates."""
        if getattr(self.canvas, "supports_blit", False):
            try:
                self.canvas.blit(self.figure.bbox)
                return
            except Exception:
                pass
        self.canvas.draw_idle()

    def _on_roi_change(
        self, roi_type: str, rect: Optional[RectROI], circle: Optional[CircleROI]
    ) -> None:
        """Handle the on roi change helper flow."""
        return

    def set_roi_callback(
        self, fn: Callable[[str, Optional[RectROI], Optional[CircleROI]], None]
    ) -> None:
        """Set roi callback for the current workflow."""
        self._roi_callback = fn
        if self.roi_interactor is not None:
            self.roi_interactor.on_change = fn
