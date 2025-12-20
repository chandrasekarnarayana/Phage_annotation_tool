"""Matplotlib rendering helpers decoupled from the main window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from phage_annotator.session_state import ViewState
from phage_annotator.export_view import ExportOptions, render_view_to_array
from phage_annotator.scalebar import ScaleBarSpec
from phage_annotator.roi_interactor_mpl import RoiInteractor, RectROI, CircleROI


@dataclass(frozen=True)
class RenderContext:
    """Render inputs for image panels and overlays.

    Parameters
    ----------
    image_frame : np.ndarray
        Primary image frame (2D array) in display resolution.
    support_frame : np.ndarray or None
        Support image frame (2D array) in display resolution.
    projections : dict[str, np.ndarray]
        Precomputed projections keyed by name ("mean", "std", "composite").
    view : ViewState
        View state (T/Z, crop/ROI, overlay toggle).
    annotations : Sequence[object]
        Filtered annotations for the current view scope.
    panel_visibility : dict[str, bool]
        Panel visibility map keyed by panel id.
    titles : dict[str, str]
        Panel titles keyed by panel id.
    extents : dict[str, tuple[float, float, float, float]]
        Axis extents per panel in display coordinates.
    std_range : tuple[float, float]
        vmin/vmax for the std panel.
    norms : dict[str, matplotlib.colors.Normalize]
        Per-panel normalization objects derived from display mappings.
    panel_cmaps : dict[str, matplotlib.colors.Colormap]
        Per-panel colormaps.
    panel_ranges : dict[str, tuple[float, float]]
        Per-panel vmin/vmax ranges used as a fallback.
    panel_annotations : dict[str, list[tuple[float, float, str, bool]]]
        Per-panel display coordinates for annotations:
        (x, y, color, selected).
    roi_overlays : dict[str, list[tuple[str, object, str]]]
        Per-panel ROI overlays: (shape, data, color).
    overlay_text : str or None
        Overlay text to display in the active panel.
    marker_size : float
        Marker size for scatter annotations.
    localization_points : list[tuple[float, float, float]]
        Optional localization overlays as (x, y, value).
    localization_visible : bool
        Whether to render localization overlays.
    threshold_mask : np.ndarray or None
        Optional threshold mask overlay in display coordinates.
    threshold_extent : tuple[float, float, float, float] or None
        Extent for the threshold overlay.
    threshold_visible : bool
        Whether to render the threshold overlay.
    particle_overlays : list[tuple[str, object, str, bool]]
        Particle overlays as (shape, data, color, selected).
    particle_labels : list[tuple[float, float, str]]
        Label overlays as (x, y, text).
    overlay_frame : np.ndarray or None
        Optional overlay image for the main frame panel.
    overlay_extent : tuple[float, float, float, float] or None
        Extent for the overlay image in display coordinates.
    overlay_alpha : float
        Alpha to apply to the overlay image.
    overlay_norm : matplotlib.colors.Normalize or None
        Optional normalization for the overlay.
    overlay_cmap : matplotlib.colors.Colormap or None
        Optional colormap for the overlay.
    scale_bar : dict or None
        Scale bar geometry and text settings for the frame panel.
    scale_bar_warning : str or None
        Warning text when calibration is missing.
    density_contours : bool
        Whether to draw density contours for the overlay layer.
    roi_scale : float
        Display-to-full coordinate scale for ROI interaction.
    roi_offset : tuple[float, float]
        Display-to-full coordinate offset for ROI interaction.
    roi_show_handles : bool
        Whether to show ROI handles on the frame axis.
    roi_type : str
        ROI type ("box", "circle", "none").
    roi_rect : tuple[float, float, float, float] or None
        ROI rectangle in full-image coordinates.
    """

    image_frame: np.ndarray
    support_frame: Optional[np.ndarray]
    projections: Dict[str, np.ndarray]
    view: ViewState
    annotations: Sequence[object]
    panel_visibility: Dict[str, bool]
    titles: Dict[str, str]
    extents: Dict[str, Tuple[float, float, float, float]]
    std_range: Tuple[float, float]
    panel_annotations: Dict[str, List[Tuple[float, float, str, bool]]]
    roi_overlays: Dict[str, List[Tuple[str, object, str]]]
    overlay_text: Optional[str]
    marker_size: float
    norms: Dict[str, matplotlib.colors.Normalize]
    panel_cmaps: Dict[str, matplotlib.colors.Colormap]
    panel_ranges: Dict[str, Tuple[float, float]]
    localization_points: List[Tuple[float, float, float]]
    localization_visible: bool
    threshold_mask: Optional[np.ndarray]
    threshold_extent: Optional[Tuple[float, float, float, float]]
    threshold_visible: bool
    particle_overlays: List[Tuple[str, object, str, bool]]
    particle_labels: List[Tuple[float, float, str]]
    overlay_frame: Optional[np.ndarray]
    overlay_extent: Optional[Tuple[float, float, float, float]]
    overlay_alpha: float
    overlay_norm: Optional[matplotlib.colors.Normalize]
    overlay_cmap: Optional[matplotlib.colors.Colormap]
    density_contours: bool
    scale_bar: Optional[Dict[str, object]]
    scale_bar_warning: Optional[str]
    roi_scale: float
    roi_offset: Tuple[float, float]
    roi_show_handles: bool
    roi_type: str
    roi_rect: Optional[Tuple[float, float, float, float]]


class Renderer:
    """Renderer responsible for figure layout and artist updates."""

    def __init__(self, figure: matplotlib.figure.Figure, canvas, colormaps: Sequence[matplotlib.colors.Colormap]) -> None:
        self.figure = figure
        self.canvas = canvas
        self.colormaps = list(colormaps)
        self.axes: Dict[str, matplotlib.axes.Axes] = {}
        self.image_artists: Dict[str, Optional[matplotlib.image.AxesImage]] = {
            "frame": None,
            "mean": None,
            "composite": None,
            "support": None,
            "std": None,
            "frame_overlay": None,
            "threshold_overlay": None,
        }
        self.overlay_text = None
        self.scale_bar_patch = None
        self.scale_bar_text = None
        self.scale_bar_warning = None
        self.roi_interactor: Optional[RoiInteractor] = None
        self._roi_callback: Optional[Callable[[str, Optional[RectROI], Optional[CircleROI]], None]] = None
        self._layout_key: Tuple[str, ...] = ()

    def request_layout_rebuild(self, layout_spec: Dict[str, object]) -> bool:
        """Return True if layout requires rebuilding based on panel visibility."""
        order = layout_spec.get("order", [])
        visible = tuple([key for key in order if layout_spec.get("panel_visibility", {}).get(key, False)])
        return visible != self._layout_key

    def init_figure(self, layout_spec: Dict[str, object]) -> Dict[str, matplotlib.axes.Axes]:
        """Build image panel axes according to the layout spec."""
        order = layout_spec.get("order", [])
        panel_visibility = layout_spec.get("panel_visibility", {})
        visible = [key for key in order if panel_visibility.get(key, False)]
        if not visible:
            return {}
        self._layout_key = tuple(visible)
        self.figure.clear()
        self.figure.set_constrained_layout(True)
        gs = self.figure.add_gridspec(1, len(visible))
        axes = {}
        base_ax = None
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
        if "frame" in axes:
            self.roi_interactor = RoiInteractor(axes["frame"], self._on_roi_change)
            if self._roi_callback is not None:
                self.roi_interactor.on_change = self._roi_callback
        self.canvas.draw_idle()
        return axes

    def update_images(self, ctx: RenderContext) -> None:
        """Update image artists in-place for all visible panels."""
        titles = ctx.titles
        if "frame" in self.axes:
            self.axes["frame"].set_title(titles.get("frame", ""))
        if "mean" in self.axes:
            self.axes["mean"].set_title(titles.get("mean", ""))
        if "composite" in self.axes:
            self.axes["composite"].set_title(titles.get("composite", ""))
        if "support" in self.axes:
            self.axes["support"].set_title(titles.get("support", ""))
        if "std" in self.axes:
            self.axes["std"].set_title(titles.get("std", ""))

        frame_norm = ctx.norms.get("frame")
        std_norm = ctx.norms.get("std")
        mean_norm = ctx.norms.get("mean")
        comp_norm = ctx.norms.get("composite")
        support_norm = ctx.norms.get("support")
        frame_range = ctx.panel_ranges.get("frame", ctx.std_range)
        mean_range = ctx.panel_ranges.get("mean", ctx.std_range)
        comp_range = ctx.panel_ranges.get("composite", ctx.std_range)
        support_range = ctx.panel_ranges.get("support", ctx.std_range)
        std_range = ctx.panel_ranges.get("std", ctx.std_range)
        if "frame" in self.axes:
            self.image_artists["frame"] = _update_or_create(
                self.axes["frame"],
                self.image_artists["frame"],
                ctx.image_frame,
                ctx.panel_cmaps.get("frame", self.colormaps[0]),
                frame_range[0],
                frame_range[1],
                ctx.extents.get("frame"),
                norm=frame_norm,
            )
            overlay = ctx.overlay_frame
            if overlay is not None:
                self.image_artists["frame_overlay"] = _update_or_create(
                    self.axes["frame"],
                    self.image_artists["frame_overlay"],
                    overlay,
                    ctx.overlay_cmap or plt.get_cmap("magma"),
                    0.0,
                    float(np.max(overlay)) if np.max(overlay) > 0 else 1.0,
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
                self.image_artists["threshold_overlay"] = _update_or_create(
                    self.axes["frame"],
                    self.image_artists["threshold_overlay"],
                    ctx.threshold_mask.astype(float, copy=False),
                    plt.get_cmap("Reds"),
                    0.0,
                    1.0,
                    ctx.threshold_extent,
                    norm=None,
                )
                if self.image_artists["threshold_overlay"] is not None:
                    self.image_artists["threshold_overlay"].set_alpha(0.35)
                    self.image_artists["threshold_overlay"].set_zorder(2.5)
                    self.image_artists["threshold_overlay"].set_visible(True)
            elif self.image_artists.get("threshold_overlay") is not None:
                self.image_artists["threshold_overlay"].set_visible(False)
        if "mean" in self.axes:
            self.image_artists["mean"] = _update_or_create(
                self.axes["mean"],
                self.image_artists["mean"],
                ctx.projections.get("mean"),
                ctx.panel_cmaps.get("mean", self.colormaps[0]),
                mean_range[0],
                mean_range[1],
                ctx.extents.get("mean"),
                norm=mean_norm,
            )
        if "composite" in self.axes:
            self.image_artists["composite"] = _update_or_create(
                self.axes["composite"],
                self.image_artists["composite"],
                ctx.projections.get("composite"),
                ctx.panel_cmaps.get("composite", self.colormaps[0]),
                comp_range[0],
                comp_range[1],
                ctx.extents.get("composite"),
                norm=comp_norm,
            )
        if "support" in self.axes and ctx.support_frame is not None:
            self.image_artists["support"] = _update_or_create(
                self.axes["support"],
                self.image_artists["support"],
                ctx.support_frame,
                ctx.panel_cmaps.get("support", self.colormaps[0]),
                support_range[0],
                support_range[1],
                ctx.extents.get("support"),
                norm=support_norm,
            )
        if "std" in self.axes:
            self.image_artists["std"] = _update_or_create(
                self.axes["std"],
                self.image_artists["std"],
                ctx.projections.get("std"),
                ctx.panel_cmaps.get("std", self.colormaps[0]),
                std_range[0],
                std_range[1],
                ctx.extents.get("std"),
                norm=std_norm,
            )
        self._flush()

    def update_overlays(self, ctx: RenderContext) -> None:
        """Update annotations, ROI outlines, and overlay text."""
        _clear_overlays(self.axes, self.image_artists)
        for panel, overlays in ctx.roi_overlays.items():
            ax = self.axes.get(panel)
            if ax is None:
                continue
            for shape, data, color in overlays:
                if shape == "box":
                    x, y, w, h = data
                    ax.add_patch(plt.Rectangle((x, y), w, h, color=color, fill=False, linewidth=1.5, alpha=0.9))
                elif shape == "circle":
                    x, y, w, h = data
                    cx, cy = x + w / 2, y + h / 2
                    r = min(w, h) / 2
                    ax.add_patch(plt.Circle((cx, cy), r, color=color, fill=False, linewidth=1.5, alpha=0.9))
                elif shape == "polygon":
                    ax.add_patch(plt.Polygon(data, closed=True, fill=False, color=color, linewidth=1.5, alpha=0.9))
                elif shape == "polyline":
                    xs = [p[0] for p in data]
                    ys = [p[1] for p in data]
                    ax.plot(xs, ys, color=color, linewidth=1.5, alpha=0.9)
        for panel, points in ctx.panel_annotations.items():
            ax = self.axes.get(panel)
            if ax is None or not points:
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            colors = [p[2] for p in points]
            selected = [p[3] for p in points]
            sizes = [ctx.marker_size * (1.3 if sel else 1.0) for sel in selected]
            ax.scatter(xs, ys, c=colors, s=sizes, marker="o", edgecolors="k")
        if ctx.particle_overlays:
            ax = self.axes.get("frame")
            if ax is not None:
                for shape, data, color, selected in ctx.particle_overlays:
                    lw = 2.2 if selected else 1.3
                    if shape == "box":
                        x, y, w, h = data
                        ax.add_patch(plt.Rectangle((x, y), w, h, color=color, fill=False, linewidth=lw, alpha=0.9))
                    elif shape == "outline":
                        xs = [p[0] for p in data]
                        ys = [p[1] for p in data]
                        ax.plot(xs, ys, color=color, linewidth=lw, alpha=0.9)
                    elif shape == "ellipse":
                        x, y, w, h = data
                        ax.add_patch(plt.Ellipse((x + w / 2, y + h / 2), w, h, fill=False, color=color, linewidth=lw))
        if ctx.particle_labels:
            ax = self.axes.get("frame")
            if ax is not None:
                for x, y, text in ctx.particle_labels:
                    ax.text(x, y, text, fontsize=8, color="yellow")
        if ctx.localization_visible and ctx.localization_points:
            ax = self.axes.get("frame")
            if ax is not None:
                xs = [p[0] for p in ctx.localization_points]
                ys = [p[1] for p in ctx.localization_points]
                vals = [p[2] for p in ctx.localization_points]
                ax.scatter(xs, ys, c=vals, s=18, cmap="viridis", edgecolors="none", alpha=0.75)
        if ctx.density_contours and ctx.overlay_frame is not None:
            ax = self.axes.get("frame")
            if ax is not None:
                try:
                    ax.contour(ctx.overlay_frame, colors="white", linewidths=0.6, alpha=0.6)
                except Exception:
                    pass
        self._update_roi_interactor(ctx)
        if ctx.view.overlay_enabled and ctx.overlay_text:
            ax = self.axes.get("frame") or next(iter(self.axes.values()), None)
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
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.4, edgecolor="none"),
                    )
                self.overlay_text.set_text(ctx.overlay_text)
                self.overlay_text.set_visible(True)
        elif self.overlay_text is not None:
            self.overlay_text.set_visible(False)
        self._update_scalebar(ctx)
        self._flush()

    def _update_roi_interactor(self, ctx: RenderContext) -> None:
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

    def _on_roi_change(self, roi_type: str, rect: Optional[RectROI], circle: Optional[CircleROI]) -> None:
        return

    def set_roi_callback(self, fn: Callable[[str, Optional[RectROI], Optional[CircleROI]], None]) -> None:
        self._roi_callback = fn
        if self.roi_interactor is not None:
            self.roi_interactor.on_change = fn

    def render_to_image(self, ctx: RenderContext, options: ExportOptions) -> np.ndarray:
        """Render a view to an RGBA image for export."""
        panel = options.panel
        if panel == "support":
            image = ctx.support_frame
        elif panel in ("mean", "std", "composite"):
            image = ctx.projections.get(panel)
        else:
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
        particle_overlays = ctx.particle_overlays if panel == "frame" else []
        overlay_text = ctx.overlay_text if options.include_overlay_text else None
        scalebar_spec = None
        if ctx.scale_bar and options.include_scalebar:
            scalebar_spec = ScaleBarSpec(
                enabled=True,
                length_um=0.0,
                thickness_px=int(ctx.scale_bar["rect"][3]) if ctx.scale_bar.get("rect") else 4,
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

    def _update_scalebar(self, ctx: RenderContext) -> None:
        ax = self.axes.get("frame")
        if ax is None:
            return
        if ctx.scale_bar_warning:
            if self.scale_bar_warning is None:
                self.scale_bar_warning = ax.text(
                    0.01,
                    0.02,
                    "",
                    transform=ax.transAxes,
                    ha="left",
                    va="bottom",
                    fontsize=8,
                    color="white",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.35, edgecolor="none"),
                )
                self.scale_bar_warning.set_gid("scalebar")
            self.scale_bar_warning.set_text(ctx.scale_bar_warning)
            self.scale_bar_warning.set_visible(True)
        elif self.scale_bar_warning is not None:
            self.scale_bar_warning.set_visible(False)
        if not ctx.scale_bar:
            if self.scale_bar_patch is not None:
                self.scale_bar_patch.set_visible(False)
            if self.scale_bar_text is not None:
                self.scale_bar_text.set_visible(False)
            return
        rect = ctx.scale_bar.get("rect")
        text = ctx.scale_bar.get("text")
        text_pos = ctx.scale_bar.get("text_pos")
        background = ctx.scale_bar.get("background_box", True)
        if rect:
            if self.scale_bar_patch is None:
                self.scale_bar_patch = plt.Rectangle(
                    (rect[0], rect[1]),
                    rect[2],
                    rect[3],
                    color="white",
                    linewidth=0,
                    alpha=0.9,
                )
                self.scale_bar_patch.set_gid("scalebar")
                ax.add_patch(self.scale_bar_patch)
            else:
                self.scale_bar_patch.set_xy((rect[0], rect[1]))
                self.scale_bar_patch.set_width(rect[2])
                self.scale_bar_patch.set_height(rect[3])
            self.scale_bar_patch.set_visible(True)
        if text and text_pos:
            if self.scale_bar_text is None:
                self.scale_bar_text = ax.text(
                    text_pos[0],
                    text_pos[1],
                    text,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="white",
                )
                self.scale_bar_text.set_gid("scalebar")
            else:
                self.scale_bar_text.set_position(text_pos)
                self.scale_bar_text.set_text(text)
            if background:
                self.scale_bar_text.set_bbox(dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.35, edgecolor="none"))
            else:
                self.scale_bar_text.set_bbox(None)
            self.scale_bar_text.set_visible(True)

    def _flush(self) -> None:
        if getattr(self.canvas, "supports_blit", False):
            try:
                self.canvas.blit(self.figure.bbox)
                return
            except Exception:
                pass
        self.canvas.draw_idle()


def _update_or_create(
    ax: matplotlib.axes.Axes,
    artist: Optional[matplotlib.image.AxesImage],
    data: Optional[np.ndarray],
    cmap: str,
    vmin: float,
    vmax: float,
    extent: Optional[Tuple[float, float, float, float]] = None,
    norm: Optional[matplotlib.colors.Normalize] = None,
) -> Optional[matplotlib.image.AxesImage]:
    if data is None:
        return artist
    if artist is None:
        artist = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, extent=extent, norm=norm)
    else:
        artist.set_data(data)
        artist.set_cmap(cmap)
        if norm is not None:
            artist.set_norm(norm)
        else:
            artist.set_clim(vmin, vmax)
        if extent is None:
            extent = (0, data.shape[1], data.shape[0], 0)
        artist.set_extent(extent)
    return artist


def _clear_overlays(
    axes: Dict[str, matplotlib.axes.Axes],
    image_artists: Dict[str, Optional[matplotlib.image.AxesImage]],
) -> None:
    for ax in axes.values():
        for artist in list(ax.patches):
            if artist.get_gid() in ("scalebar", "roi_interactor"):
                continue
            artist.remove()
        for artist in list(ax.lines):
            if artist.get_gid() in ("scalebar", "roi_interactor"):
                continue
            artist.remove()
        for artist in list(ax.texts):
            if artist.get_gid() in ("scalebar", "roi_interactor"):
                continue
            artist.remove()
        for artist in list(ax.collections):
            if artist in image_artists.values() or artist.get_gid() == "roi_interactor":
                continue
            artist.remove()
