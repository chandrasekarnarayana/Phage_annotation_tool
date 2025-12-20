"""Export current view with overlays as PNG/TIFF."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from phage_annotator.scalebar import ScaleBarSpec, compute_scalebar


@dataclass(frozen=True)
class ExportOptions:
    panel: str
    region: str
    include_roi_outline: bool
    include_roi_fill: bool
    include_annotations: bool
    include_annotation_labels: bool
    include_particles: bool
    include_scalebar: bool
    include_overlay_text: bool
    marker_size: float
    roi_line_width: float
    dpi: int
    fmt: str
    overlay_only: bool
    transparent_bg: bool
    roi_mask_clip: bool


def render_view_to_array(
    image: np.ndarray,
    *,
    cmap,
    norm,
    overlays: list[object],
    annotations: list[Tuple[float, float, str]],
    annotation_labels: list[Tuple[float, float, str]],
    roi_overlays: list[Tuple[str, object, str]],
    particle_overlays: list[Tuple[str, object, str, bool]],
    overlay_text: Optional[str],
    scalebar_spec: Optional[ScaleBarSpec],
    pixel_size_um: Optional[float],
    options: ExportOptions,
) -> np.ndarray:
    """Render a view with overlays into an RGBA array."""
    fig = plt.figure(figsize=(6, 6), dpi=options.dpi)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, image.shape[1])
    ax.set_ylim(image.shape[0], 0)
    if not options.overlay_only:
        ax.imshow(image, cmap=cmap, norm=norm, extent=(0, image.shape[1], image.shape[0], 0))
    if options.include_roi_fill:
        for shape, data, color in roi_overlays:
            if shape == "box":
                x, y, w, h = data
                ax.add_patch(plt.Rectangle((x, y), w, h, color=color, alpha=0.2, linewidth=0))
            elif shape == "circle":
                x, y, w, h = data
                cx, cy = x + w / 2, y + h / 2
                r = min(w, h) / 2
                ax.add_patch(plt.Circle((cx, cy), r, color=color, alpha=0.2, linewidth=0))
            elif shape == "polygon":
                ax.add_patch(
                    plt.Polygon(
                        data,
                        closed=True,
                        fill=True,
                        color=color,
                        alpha=0.2,
                        linewidth=0,
                    )
                )
    if options.include_roi_outline:
        for shape, data, color in roi_overlays:
            if shape == "box":
                x, y, w, h = data
                ax.add_patch(
                    plt.Rectangle(
                        (x, y),
                        w,
                        h,
                        color=color,
                        fill=False,
                        linewidth=options.roi_line_width,
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
                        linewidth=options.roi_line_width,
                    )
                )
            elif shape == "polygon":
                ax.add_patch(
                    plt.Polygon(
                        data,
                        closed=True,
                        fill=False,
                        color=color,
                        linewidth=options.roi_line_width,
                    )
                )
            elif shape == "polyline":
                xs = [p[0] for p in data]
                ys = [p[1] for p in data]
                ax.plot(xs, ys, color=color, linewidth=options.roi_line_width)
    if options.include_annotations and annotations:
        xs = [p[0] for p in annotations]
        ys = [p[1] for p in annotations]
        colors = [p[2] for p in annotations]
        ax.scatter(xs, ys, c=colors, s=options.marker_size, edgecolors="k")
    if options.include_annotation_labels and annotation_labels:
        for x, y, text in annotation_labels:
            ax.text(x, y, text, fontsize=8, color="white")
    if options.include_particles and particle_overlays:
        for shape, data, color, selected in particle_overlays:
            lw = 2.2 if selected else 1.3
            if shape == "box":
                x, y, w, h = data
                ax.add_patch(plt.Rectangle((x, y), w, h, color=color, fill=False, linewidth=lw))
            elif shape == "outline":
                xs = [p[0] for p in data]
                ys = [p[1] for p in data]
                ax.plot(xs, ys, color=color, linewidth=lw)
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
    if options.include_overlay_text and overlay_text:
        ax.text(
            0.01,
            0.99,
            overlay_text,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.4, edgecolor="none"),
        )
    if options.include_scalebar and scalebar_spec:
        geom = compute_scalebar(
            (0, image.shape[1], image.shape[0], 0), pixel_size_um, scalebar_spec
        )
        if geom:
            rect = geom.get("rect")
            text = geom.get("text")
            text_pos = geom.get("text_pos")
            if rect:
                ax.add_patch(
                    plt.Rectangle(
                        (rect[0], rect[1]),
                        rect[2],
                        rect[3],
                        color="white",
                        linewidth=0,
                        alpha=0.9,
                    )
                )
            if text and text_pos:
                ax.text(
                    text_pos[0],
                    text_pos[1],
                    text,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="white",
                    bbox=(
                        dict(
                            boxstyle="round,pad=0.2",
                            facecolor="black",
                            alpha=0.35,
                            edgecolor="none",
                        )
                        if scalebar_spec.background_box
                        else None
                    ),
                )
    canvas.draw()
    buf = np.asarray(canvas.buffer_rgba())
    plt.close(fig)
    if options.transparent_bg and options.overlay_only:
        return buf
    return buf
