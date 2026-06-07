"""Overlay payload preparation helpers for the renderer refresh pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from phage_annotator.rendering.scalebar import ScaleBarSpec, compute_scalebar


@dataclass
class OverlayPayload:
    """Computed overlay artifacts passed into RenderContext."""

    overlay_frame: object | None
    overlay_extent: tuple[float, float, float, float] | None
    localization_points: list[tuple[float, float, float]]
    scale_bar: object | None
    scale_bar_warning: str | None


def build_overlay_payload(owner: object, prim: object, primary_panel: str, panel_images: dict[str, object], frame_ax: object | None, extents: dict[str, tuple[int, int, int, int]]) -> OverlayPayload:
    """Prepare density, SMLM, Deep-STORM, and scale-bar overlays."""
    overlay_frame, overlay_extent = _overlay_frame(owner, prim)
    loc_points = _localization_points(owner, prim, frame_ax)
    scale_bar, warning = _scale_bar(owner, prim, primary_panel, panel_images, extents)
    return OverlayPayload(
        overlay_frame=overlay_frame,
        overlay_extent=overlay_extent,
        localization_points=loc_points,
        scale_bar=scale_bar,
        scale_bar_warning=warning,
    )


def _overlay_frame(owner: object, prim: object) -> tuple[object | None, tuple[float, float, float, float] | None]:
    """Select and crop the active raster overlay frame."""
    overlay_frame = None
    overlay_extent = None
    if owner.show_sr_overlay:
        overlay_frame = owner._sr_overlay if owner._sr_overlay is not None else owner._smlm_overlay
        overlay_extent = owner._sr_overlay_extent if owner._sr_overlay is not None else owner._smlm_overlay_extent
    if owner._density_overlay is not None and getattr(owner, "_density_image_id", None) == prim.id:
        density = owner._density_overlay
        if owner.crop_rect:
            x, y, w, h = owner.crop_rect
            x0 = int(max(0, x))
            y0 = int(max(0, y))
            x1 = int(min(density.shape[1], x + w))
            y1 = int(min(density.shape[0], y + h))
            density = density[y0:y1, x0:x1]
        overlay_frame = density
        overlay_extent = (0, density.shape[1], density.shape[0], 0)
    if overlay_frame is not None and owner._interactive and owner.downsample_images:
        stride = max(1, int(owner.downsample_factor))
        overlay_frame = overlay_frame[::stride, ::stride]
    return overlay_frame, overlay_extent


def _localization_points(owner: object, prim: object, frame_ax: object | None) -> list[tuple[float, float, float]]:
    """Convert localization results into display-space scatter points."""
    loc_points: list[tuple[float, float, float]] = []
    if not owner.show_smlm_points or frame_ax is None:
        return loc_points
    scale = owner._axis_scale(frame_ax)
    off_x = owner.crop_rect[0] if owner.crop_rect else 0.0
    off_y = owner.crop_rect[1] if owner.crop_rect else 0.0
    if owner._smlm_results and getattr(owner, "_smlm_image_id", None) == prim.id:
        color_mode = getattr(owner.smlm_panel, "thunder", None)
        color_field = "photons"
        if color_mode is not None and hasattr(color_mode, "color_mode_combo"):
            color_field = color_mode.color_mode_combo.currentText().lower()
        for loc in owner._smlm_results:
            val = loc.photons if color_field.startswith("phot") else loc.uncertainty_px
            loc_points.append(((loc.x_px - off_x) / scale, (loc.y_px - off_y) / scale, float(val)))
    elif owner._deepstorm_results and getattr(owner, "_deepstorm_image_id", None) == prim.id:
        for loc in owner._deepstorm_results:
            loc_points.append(((loc.x_px - off_x) / scale, (loc.y_px - off_y) / scale, float(loc.score)))
    return loc_points


def _scale_bar(owner: object, prim: object, primary_panel: str, panel_images: dict[str, object], extents: dict[str, tuple[int, int, int, int]]) -> tuple[object | None, str | None]:
    """Compute the current scale bar or a warning explaining why it is hidden."""
    if not owner.scale_bar_enabled:
        return None, None
    cal = owner._get_calibration_state(prim.id)
    if not cal.pixel_size_um_per_px:
        return None, "Scale bar requires calibration"
    spec = ScaleBarSpec(
        enabled=True,
        length_um=owner.scale_bar_length_um,
        thickness_px=owner.scale_bar_thickness_px,
        location=owner.scale_bar_location,
        padding_px=owner.scale_bar_padding_px,
        show_text=owner.scale_bar_show_text,
        text_offset_px=owner.scale_bar_text_offset_px,
        background_box=owner.scale_bar_background_box,
    )
    primary_shape = panel_images[primary_panel].shape
    extent = extents.get(primary_panel) or (0, primary_shape[1], primary_shape[0], 0)
    scale_bar = compute_scalebar(extent, cal.pixel_size_um_per_px, spec)
    if scale_bar is not None:
        scale_bar["background_box"] = owner.scale_bar_background_box
    return scale_bar, None
