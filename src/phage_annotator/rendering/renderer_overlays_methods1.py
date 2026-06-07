"""Method group 1 split from renderer_overlays.py."""

from __future__ import annotations

# Unified logging through service framework
try:
    from phage_annotator.framework import get_log_service
    _logger = get_log_service().get_logger(__name__)
except (ImportError, RuntimeError, AttributeError):
    import logging
    _logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from phage_annotator.roi.interactor import CircleROI, RectROI
from phage_annotator.rendering.mpl_canvas import RenderContext
from phage_annotator.rendering.mpl_utils import _clear_overlays


class _RendererOverlaysMixinMethods1:
    """Methods split from RendererOverlaysMixin."""

    def update_overlays(self, ctx: RenderContext) -> None:
        """Update annotations, ROI outlines, and overlay text."""
        _clear_overlays(self.axes, self.image_artists)
        primary_panel = (
            ctx.primary_panel if ctx.primary_panel in self.axes else next(iter(self.axes.keys()), None)
        )
        for panel, overlays in ctx.roi_overlays.items():
            ax = self.axes.get(panel)
            if ax is None:
                continue
            for shape, data, color in overlays:
                if shape == "box":
                    x, y, w, h = data
                    ax.add_patch(
                        plt.Rectangle(
                            (x, y),
                            w,
                            h,
                            color=color,
                            fill=False,
                            linewidth=1.5,
                            alpha=0.9,
                        )
                    )
                elif shape == "circle":
                    x, y, w, h = data
                    cx, cy = x + w / 2, y + h / 2
                    r = min(w, h) / 2
                    ax.add_patch(
                        plt.Circle(
                            (cx, cy),
                            r,
                            color=color,
                            fill=False,
                            linewidth=1.5,
                            alpha=0.9,
                        )
                    )
                elif shape == "polygon":
                    ax.add_patch(
                        plt.Polygon(
                            data,
                            closed=True,
                            fill=False,
                            color=color,
                            linewidth=1.5,
                            alpha=0.9,
                        )
                    )
                elif shape == "polyline":
                    xs = [p[0] for p in data]
                    ys = [p[1] for p in data]
                    ax.plot(xs, ys, color=color, linewidth=1.5, alpha=0.9)
        for panel, points in ctx.panel_annotations.items():
            ax = self.axes.get(panel)
            if ax is None or not points:
                continue
            marker = str(getattr(ctx, "marker_shape", "o") or "o")
            filled_points = [p for p in points if len(p) < 5 or bool(p[4])]
            hollow_points = [p for p in points if len(p) >= 5 and not bool(p[4])]
            if hollow_points:
                xs = [p[0] for p in hollow_points]
                ys = [p[1] for p in hollow_points]
                selected = [bool(p[3]) for p in hollow_points]
                colors = ["#ff2d95" if sel else p[2] for p, sel in zip(hollow_points, selected)]
                sizes = [ctx.marker_size * (1.4 if sel else 1.1) for sel in selected]
                ax.scatter(
                    xs,
                    ys,
                    s=sizes,
                    marker="o",
                    facecolors="none",
                    edgecolors=colors,
                    linewidths=[1.8 if sel else 1.4 for sel in selected],
                )
            if filled_points:
                xs = [p[0] for p in filled_points]
                ys = [p[1] for p in filled_points]
                selected = [bool(p[3]) for p in filled_points]
                colors = ["#ff2d95" if sel else p[2] for p, sel in zip(filled_points, selected)]
                sizes = [ctx.marker_size * (1.3 if sel else 1.0) for sel in selected]
                ax.scatter(xs, ys, c=colors, s=sizes, marker=marker, edgecolors="k")
        for panel, labels in ctx.suggestion_staleness_labels.items():
            ax = self.axes.get(panel)
            if ax is None or not labels:
                continue
            for x, y, text in labels:
                ax.text(
                    x + 4.0,
                    y - 4.0,
                    text,
                    fontsize=7,
                    color="#eceff1",
                    bbox=dict(
                        boxstyle="round,pad=0.15",
                        facecolor="#263238",
                        alpha=0.45,
                        edgecolor="none",
                    ),
                    zorder=15,
                )
        if ctx.particle_overlays:
            ax = self.axes.get(primary_panel) if primary_panel is not None else None
            if ax is not None:
                for shape, data, color, selected in ctx.particle_overlays:
                    lw = 2.2 if selected else 1.3
                    if shape == "box":
                        x, y, w, h = data
                        ax.add_patch(
                            plt.Rectangle(
                                (x, y),
                                w,
                                h,
                                color=color,
                                fill=False,
                                linewidth=lw,
                                alpha=0.9,
                            )
                        )
                    elif shape == "outline":
                        xs = [p[0] for p in data]
                        ys = [p[1] for p in data]
                        ax.plot(xs, ys, color=color, linewidth=lw, alpha=0.9)
                    elif shape == "ellipse":
                        x, y, w, h = data
                        ax.add_patch(
                            plt.Ellipse(
                                (x + w / 2, y + h / 2),
                                w,
                                h,
                                fill=False,
                                color=color,
                                linewidth=lw,
                            )
                        )
        if ctx.particle_labels:
            ax = self.axes.get(primary_panel) if primary_panel is not None else None
            if ax is not None:
                for x, y, text in ctx.particle_labels:
                    ax.text(x, y, text, fontsize=8, color="yellow")
        if ctx.localization_visible and ctx.localization_points:
            ax = self.axes.get(primary_panel) if primary_panel is not None else None
            if ax is not None:
                xs = [p[0] for p in ctx.localization_points]
                ys = [p[1] for p in ctx.localization_points]
                vals = [p[2] for p in ctx.localization_points]
                ax.scatter(xs, ys, c=vals, s=18, cmap="viridis", edgecolors="none", alpha=0.75)
        if ctx.density_contours and ctx.overlay_frame is not None:
            ax = self.axes.get(primary_panel) if primary_panel is not None else None
            if ax is not None:
                try:
                    ax.contour(ctx.overlay_frame, colors="white", linewidths=0.6, alpha=0.6)
                except Exception:
                    pass
        self._update_roi_interactor(ctx)
        if ctx.view.overlay_enabled and ctx.overlay_text:
            ax = self.axes.get(primary_panel) or next(iter(self.axes.values()), None)
            if ax is not None:
                if self.overlay_text is None:
                    self.overlay_text = ax.text(
                        0.01,
                        0.99,
                        "",
                        transform=ax.transAxes,
                        ha="left",
                        va="top",
                        fontsize=9,
                        color="white",
                        bbox=dict(
                            boxstyle="round,pad=0.3",
                            facecolor="black",
                            alpha=0.4,
                            edgecolor="none",
                        ),
                    )
                self.overlay_text.set_text(ctx.overlay_text)
                self.overlay_text.set_visible(True)
        elif self.overlay_text is not None:
            self.overlay_text.set_visible(False)
        if ctx.canvas_header_text:
            ax = self.axes.get(primary_panel) or next(iter(self.axes.values()), None)
            if ax is not None:
                if self.canvas_header_text is None:
                    self.canvas_header_text = ax.text(
                        0.5,
                        1.01,
                        "",
                        transform=ax.transAxes,
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        color="#111111",
                        bbox=dict(
                            boxstyle="round,pad=0.25",
                            facecolor="#f5f5f5",
                            alpha=0.95,
                            edgecolor="#d0d0d0",
                        ),
                        clip_on=False,
                        zorder=20,
                    )
                self.canvas_header_text.set_text(ctx.canvas_header_text)
                self.canvas_header_text.set_visible(True)
        elif self.canvas_header_text is not None:
            self.canvas_header_text.set_visible(False)
        self._update_scalebar(ctx)
        self._flush()

    def _update_roi_interactor(self, ctx: RenderContext) -> None:
        """Update roi interactor for the current workflow."""
        if self.roi_interactor is None:
            return
        self.roi_interactor.set_mapper(ctx.roi_scale, ctx.roi_offset)
        self.roi_interactor.set_show_handles(ctx.roi_show_handles)
        if ctx.roi_type == "box" and ctx.roi_rect:
            x, y, w, h = ctx.roi_rect
            self.roi_interactor.set_rect_roi(RectROI(x, y, w, h), emit=False)
        elif ctx.roi_type == "circle" and ctx.roi_rect:
            x, y, w, h = ctx.roi_rect
            cx, cy = x + w / 2, y + h / 2
            r = min(w, h) / 2
            self.roi_interactor.set_circle_roi(CircleROI(cx, cy, r), emit=False)
        else:
            self.roi_interactor.clear_roi(emit=False)
