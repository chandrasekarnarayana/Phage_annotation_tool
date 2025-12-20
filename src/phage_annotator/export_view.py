"""Export current view with overlays as PNG/TIFF."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from phage_annotator.scalebar import ScaleBarSpec, compute_scalebar


@dataclass
class ExportValidationResult:
    """P4.2: Validation result for export preflight checks."""
    
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, msg: str) -> None:
        """Add validation error."""
        self.errors.append(msg)
        self.is_valid = False
    
    def add_warning(self, msg: str) -> None:
        """Add validation warning (non-blocking)."""
        self.warnings.append(msg)


def validate_export_preflight(
    options: ExportOptions,
    has_support_image: bool = False,
    has_roi: bool = False,
    image_shape: Optional[Tuple[int, ...]] = None,
) -> ExportValidationResult:
    """P4.2: Validate export options before execution.
    
    Preflight checks:
    - scope: full requires support image, roi requires active ROI
    - panels: at least one must be selected
    - overlays: validate consistency
    - format: PNG/TIFF supported
    - dpi: 72-600 range
    
    Parameters
    ----------
    options : ExportOptions
        Export configuration
    has_support_image : bool
        Whether a support image is available
    has_roi : bool
        Whether an ROI is defined
    image_shape : Optional[Tuple[int, ...]]
        Shape of primary image for bounds checking
        
    Returns
    -------
    ExportValidationResult
        Validation result with errors and warnings
    """
    result = ExportValidationResult(is_valid=True)
    
    # Check region validity
    region = options.region.lower()
    if region in ("roi bounds", "roi mask-clipped"):
        if not has_roi:
            result.add_error("ROI-based export requires an active ROI")
    
    # Check format
    fmt = options.fmt.lower()
    if fmt not in ("png", "tiff"):
        result.add_error(f"Unsupported format: {fmt} (PNG or TIFF required)")
    
    # Check DPI
    if not (72 <= options.dpi <= 600):
        result.add_error(f"DPI must be 72-600, got {options.dpi}")
    
    # Check marker size
    if not (1.0 <= options.marker_size <= 200.0):
        result.add_error(f"Marker size must be 1.0-200.0, got {options.marker_size}")
    
    # Check ROI line width
    if not (0.5 <= options.roi_line_width <= 6.0):
        result.add_error(f"ROI line width must be 0.5-6.0, got {options.roi_line_width}")
    
    # Check panel validity
    panel = options.panel.lower()
    valid_panels = ("frame", "mean", "composite", "support", "std")
    if panel not in valid_panels:
        result.add_error(f"Invalid panel: {panel} (must be one of {valid_panels})")
    
    # Check region validity
    valid_regions = ("full view", "crop", "roi bounds", "roi mask-clipped")
    if region not in valid_regions:
        result.add_error(f"Invalid region: {region} (must be one of {valid_regions})")
    
    # Warn if overlay-only without overlays
    has_overlays = (
        options.include_annotations or
        options.include_roi_outline or
        options.include_roi_fill or
        options.include_particles or
        options.include_scalebar or
        options.include_overlay_text
    )
    if options.overlay_only and not has_overlays:
        result.add_warning("Overlay-only export selected but no overlays enabled")
    
    return result


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
    export_as_layers: bool = False  # P3.4: Export overlays as separate layer files


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
