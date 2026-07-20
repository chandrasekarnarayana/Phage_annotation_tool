"""Rendering export render impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from phage_annotator.rendering.scalebar import ScaleBarSpec, compute_scalebar
from phage_annotator.ui_qt.rendering.export_preflight import ExportOptions
from phage_annotator.ui_qt.rendering.export_render import render_view_to_array
from phage_annotator.ui_qt.rendering.command_base import CommandBaseMixin
from phage_annotator.ui_qt.rendering.histogram_contrast_orthoview import HistogramContrastAutosetMixin
from phage_annotator.ui_qt.rendering.histogram_contrast_hist import HistogramContrastHistMixin
from phage_annotator.ui_qt.rendering.histogram_contrast import HistogramContrastMixin
from phage_annotator.ui_qt.rendering.lazy_loader_modality import LazyLoaderModalityMixin
from phage_annotator.ui_qt.rendering.renderer import RenderingMixin
from phage_annotator.ui_qt.rendering.renderer_overlays import RenderingOverlayMixin
from phage_annotator.ui_qt.rendering.roi_crop_templates import RoiCropTemplatesMixin
from phage_annotator.ui_qt.rendering.roi_crop_display import RoiCropDisplayMixin
from phage_annotator.ui_qt.rendering.roi_crop import RoiCropMixin
from phage_annotator.ui_qt.rendering.renderer import RenderingMixin as RenderingMixin

def render_layer_to_array(
    image_shape: Tuple[int, int],
    *,
    layer_type: str,
    cmap=None,
    norm=None,
    image: Optional[np.ndarray] = None,
    annotations: list[Tuple[float, float, str]] = None,
    annotation_labels: list[Tuple[float, float, str]] = None,
    roi_overlays: list[Tuple[str, object, str]] = None,
    particle_overlays: list[Tuple[str, object, str, bool]] = None,
    overlay_text: Optional[str] = None,
    scalebar_spec: Optional[ScaleBarSpec] = None,
    pixel_size_um: Optional[float] = None,
    options: ExportOptions,
) -> np.ndarray:
    """Render a single layer (base, annotations, ROI, particles, or scalebar) with transparency.
    
    P3.4: Export individual layers as separate PNG files with alpha channel.
    
    Parameters
    ----------
    image_shape : tuple
        (height, width) of the base image
    layer_type : str
        One of: "base", "annotations", "roi", "particles", "scalebar", "text"
    
    Returns
    -------
    np.ndarray
        RGBA array with transparent background
    """
    fig = plt.figure(figsize=(6, 6), dpi=options.dpi)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, image_shape[1])
    ax.set_ylim(image_shape[0], 0)
    
    # Render specific layer
    if layer_type == "base" and image is not None and cmap is not None and norm is not None:
        ax.imshow(image, cmap=cmap, norm=norm, extent=(0, image_shape[1], image_shape[0], 0))
    
    elif layer_type == "annotations" and annotations:
        xs = [p[0] for p in annotations]
        ys = [p[1] for p in annotations]
        colors = [p[2] for p in annotations]
        ax.scatter(xs, ys, c=colors, s=options.marker_size, edgecolors="k")
        if annotation_labels:
            for x, y, text in annotation_labels:
                ax.text(x, y, text, fontsize=8, color="white")
    
    elif layer_type == "roi" and roi_overlays:
        for shape, data, color in roi_overlays:
            if shape == "box":
                x, y, w, h = data
                ax.add_patch(
                    plt.Rectangle(
                        (x, y),
                        w,
                        h,
                        color=color,
                        fill=options.include_roi_fill,
                        alpha=0.2 if options.include_roi_fill else 1.0,
                        linewidth=options.roi_line_width if options.include_roi_outline else 0,
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
                        fill=options.include_roi_fill,
                        alpha=0.2 if options.include_roi_fill else 1.0,
                        linewidth=options.roi_line_width if options.include_roi_outline else 0,
                    )
                )
            elif shape == "polygon":
                ax.add_patch(
                    plt.Polygon(
                        data,
                        closed=True,
                        fill=options.include_roi_fill,
                        color=color,
                        alpha=0.2 if options.include_roi_fill else 1.0,
                        linewidth=options.roi_line_width if options.include_roi_outline else 0,
                    )
                )
            elif shape == "polyline":
                xs = [p[0] for p in data]
                ys = [p[1] for p in data]
                ax.plot(xs, ys, color=color, linewidth=options.roi_line_width)
    
    elif layer_type == "particles" and particle_overlays:
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
    
    elif layer_type == "scalebar" and scalebar_spec:
        geom = compute_scalebar(
            (0, image_shape[1], image_shape[0], 0), pixel_size_um, scalebar_spec
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
    
    elif layer_type == "text" and overlay_text:
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
    
    canvas.draw()
    buf = np.asarray(canvas.buffer_rgba())
    plt.close(fig)
    return buf


def render_chunk_to_array(
    image: np.ndarray,
    crop_box: Tuple[int, int, int, int],
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
    options: "ExportOptions") -> np.ndarray:
    """Render a spatial chunk of the image with overlays (P4a: Streaming Export).
    
    Parameters
    ----------
    image : np.ndarray
        Full image array (Y, X) or (Y, X, C)
    crop_box : Tuple[int, int, int, int]
        Crop region: (x0, y0, x1, y1) in image coordinates
    cmap, norm, overlays, etc.
        Same as 
    options : 
        Export options including DPI
    
    Returns
    -------
    np.ndarray
        Rendered RGBA chunk
    """
    x0, y0, x1, y1 = crop_box
    chunk = image[y0:y1, x0:x1] if image.ndim == 2 else image[y0:y1, x0:x1, :]
    
    # Filter overlays to those intersecting this chunk
    filtered_roi = []
    for shape, data, color in roi_overlays:
        # Simple bounding box check (conservative)
        if shape == "box":
            bx, by, bw, bh = data
            if not (bx + bw < x0 or bx > x1 or by + bh < y0 or by > y1):
                filtered_roi.append((shape, data, color))
        else:
            # For complex shapes, include conservatively
            filtered_roi.append((shape, data, color))
    
    # Filter annotations to those in chunk
    filtered_annotations = [(x - x0, y - y0, c) for x, y, c in annotations
                            if x0 <= x < x1 and y0 <= y < y1]
    filtered_labels = [(x - x0, y - y0, t) for x, y, t in annotation_labels
                       if x0 <= x < x1 and y0 <= y < y1]
    
    # Filter particle overlays
    filtered_particles = []
    for shape, data, color, selected in particle_overlays:
        if shape == "box":
            bx, by, bw, bh = data
            if not (bx + bw < x0 or bx > x1 or by + bh < y0 or by > y1):
                # Offset to chunk coordinates
                filtered_particles.append((shape, (bx - x0, by - y0, bw, bh), color, selected))
        else:
            filtered_particles.append((shape, data, color, selected))
    
    # Render chunk with filtered overlays
    return render_view_to_array(
        chunk,
        cmap=cmap,
        norm=norm,
        overlays=overlays,
        annotations=filtered_annotations,
        annotation_labels=filtered_labels,
        roi_overlays=filtered_roi,
        particle_overlays=filtered_particles,
        overlay_text=overlay_text,
        scalebar_spec=scalebar_spec,
        pixel_size_um=pixel_size_um,
        options=options)
