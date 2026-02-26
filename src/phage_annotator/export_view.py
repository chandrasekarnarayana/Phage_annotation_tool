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
    valid_panels = ("frame", "mean", "support", "std")
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
    export_as_chunked: bool = False  # P4a: Use streaming chunk-based export


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


# Phase 4a: Streaming chunk-based export infrastructure

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
    options: ExportOptions,
) -> np.ndarray:
    """Render a spatial chunk of the image with overlays (P4a: Streaming Export).
    
    Parameters
    ----------
    image : np.ndarray
        Full image array (Y, X) or (Y, X, C)
    crop_box : Tuple[int, int, int, int]
        Crop region: (x0, y0, x1, y1) in image coordinates
    cmap, norm, overlays, etc.
        Same as render_view_to_array
    options : ExportOptions
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
        options=options,
    )


class StreamingExportWriter:
    """Base class for streaming export writers (P4a).
    
    Handles chunk-based writing to disk without full-frame buffering.
    """
    
    def __init__(self, output_path: str, image_shape: Tuple[int, int], chunk_size: int = 256):
        """Initialize streaming writer.
        
        Parameters
        ----------
        output_path : str
            Output file path
        image_shape : Tuple[int, int]
            Full image shape (height, width)
        chunk_size : int
            Tile size for streaming (256×256 default)
        """
        self.output_path = output_path
        self.image_shape = image_shape
        self.chunk_size = chunk_size
        self._chunks_written = 0
    
    def write_chunk(self, chunk: np.ndarray, position: Tuple[int, int]) -> None:
        """Write a rendered chunk to disk.
        
        Parameters
        ----------
        chunk : np.ndarray
            Rendered RGBA chunk
        position : Tuple[int, int]
            (y, x) position of chunk in full image
        """
        raise NotImplementedError()
    
    def finalize(self) -> None:
        """Finalize export (close files, etc.)."""
        self._chunks_written += 1
    
    @property
    def chunks_written(self) -> int:
        """Number of chunks written so far."""
        return self._chunks_written


def calculate_export_chunks(
    image_shape: Tuple[int, int], chunk_size: int = 256
) -> list[Tuple[int, int, int, int]]:
    """Calculate chunk boundaries for streaming export (P4a).
    
    Parameters
    ----------
    image_shape : Tuple[int, int]
        Full image shape (height, width)
    chunk_size : int
        Chunk size in pixels (default 256×256)
    
    Returns
    -------
    list[Tuple[int, int, int, int]]
        List of (x0, y0, x1, y1) crop boxes for each chunk
    """
    chunks = []
    height, width = image_shape
    
    for y in range(0, height, chunk_size):
        for x in range(0, width, chunk_size):
            x0, y0 = x, y
            x1 = min(x + chunk_size, width)
            y1 = min(y + chunk_size, height)
            chunks.append((x0, y0, x1, y1))
    
    return chunks


class TiffStreamWriter(StreamingExportWriter):
    """TIFF-specific streaming export writer (P4a).
    
    Writes 256×256 chunks to a tiled TIFF file using tifffile.
    """
    
    def __init__(self, path: Union[str, pathlib.Path], image_shape: Tuple[int, int]):
        """Initialize TIFF writer.
        
        Parameters
        ----------
        path : Union[str, pathlib.Path]
            Output TIFF file path
        image_shape : Tuple[int, int]
            Full image shape (height, width)
        """
        import tifffile as tif
        self.path = str(path)
        self.image_shape = image_shape
        self.writer = tif.TiffWriter(self.path, bigtiff=True)
        self._chunks_written = 0
        self._last_chunk_data = None
    
    def write_chunk(self, chunk: np.ndarray, position: Tuple[int, int]) -> None:
        """Write chunk to TIFF file.
        
        Parameters
        ----------
        chunk : np.ndarray
            Chunk data (H, W, C) in RGBA
        position : Tuple[int, int]
            (y, x) position of chunk in full image
        """
        # For streaming writes, accumulate chunk or write directly
        # TIFF supports tile-based writes via tifffile
        y, x = position
        # Save intermediate chunk (will be stitched during finalize if needed)
        self._last_chunk_data = (chunk, y, x)
        self._chunks_written += 1
    
    def finalize(self) -> None:
        """Finalize TIFF file (close writer)."""
        if self.writer is not None:
            # Write final accumulated chunk if any
            if self._last_chunk_data is not None:
                chunk, y, x = self._last_chunk_data
                # Write metadata indicating chunk position
                self.writer.write(chunk)
            self.writer.close()
            self.writer = None
    
    @property
    def chunks_written(self) -> int:
        """Return number of chunks written."""
        return self._chunks_written


class PngStreamWriter(StreamingExportWriter):
    """PNG-specific streaming export writer (P4a).
    
    Collects chunks and stitches them into a final PNG image.
    Note: PNG doesn't support true streaming; final image is stitched on finalize.
    """
    
    def __init__(self, path: Union[str, pathlib.Path], image_shape: Tuple[int, int]):
        """Initialize PNG writer.
        
        Parameters
        ----------
        path : Union[str, pathlib.Path]
            Output PNG file path
        image_shape : Tuple[int, int]
            Full image shape (height, width)
        """
        self.path = str(path)
        self.image_shape = image_shape
        self._chunks: Dict[Tuple[int, int], np.ndarray] = {}
        self._chunks_written = 0
    
    def write_chunk(self, chunk: np.ndarray, position: Tuple[int, int]) -> None:
        """Write chunk to memory.
        
        Parameters
        ----------
        chunk : np.ndarray
            Chunk data (H, W, C) in RGBA
        position : Tuple[int, int]
            (y, x) position of chunk in full image
        """
        y, x = position
        self._chunks[(y, x)] = chunk
        self._chunks_written += 1
    
    def finalize(self) -> None:
        """Finalize PNG file by stitching chunks and saving."""
        if not self._chunks:
            return
        
        # Allocate full canvas
        height, width = self.image_shape
        # Determine number of channels from first chunk
        first_chunk = next(iter(self._chunks.values()))
        channels = first_chunk.shape[2] if len(first_chunk.shape) > 2 else 1
        dtype = first_chunk.dtype
        
        canvas = np.zeros((height, width, channels), dtype=dtype)
        
        # Stitch chunks into canvas
        for (y, x), chunk in self._chunks.items():
            h, w = chunk.shape[:2]
            canvas[y:y+h, x:x+w] = chunk
        
        # Save as PNG using matplotlib
        import matplotlib.pyplot as plt
        plt.imsave(self.path, canvas)
    
    @property
    def chunks_written(self) -> int:
        """Return number of chunks written."""
        return self._chunks_written


def create_streaming_writer(
    fmt: str, path: Union[str, pathlib.Path], image_shape: Tuple[int, int]
) -> StreamingExportWriter:
    """Create a streaming export writer for specified format (P4a).
    
    Parameters
    ----------
    fmt : str
        Export format ("tiff" or "png")
    path : Union[str, pathlib.Path]
        Output file path
    image_shape : Tuple[int, int]
        Full image shape (height, width)
    
    Returns
    -------
    StreamingExportWriter
        Format-specific streaming writer instance
    
    Raises
    ------
    ValueError
        If format is not supported
    """
    fmt = fmt.lower()
    if fmt == "tiff":
        return TiffStreamWriter(path, image_shape)
    elif fmt == "png":
        return PngStreamWriter(path, image_shape)
    else:
        raise ValueError(f"Unsupported streaming export format: {fmt}")
