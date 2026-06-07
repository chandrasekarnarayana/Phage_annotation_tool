"""Panel frame collection and display downsampling helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass
class PanelFrameBundle:
    """Frames, source images, and projection state for visible render panels."""

    primary_panel: str
    panel_images_raw: Dict[str, np.ndarray]
    panel_images: Dict[str, np.ndarray]
    panel_sources: Dict[str, object]
    panel_projections: Dict[str, str]
    panel_projection_ready: Dict[str, bool]
    frame_ax: object | None
    level: int


def sync_slice_sliders(owner: object, prim: object, has_time: bool, has_z: bool) -> None:
    """Synchronize T/Z slider bounds and labels with the active image."""
    t_max = max(0, int(prim.array.shape[0]) - 1)
    z_max = max(0, int(prim.array.shape[1]) - 1)
    if not has_time and has_z:
        t_max = z_max
    _sync_slider(getattr(owner, "t_slider", None), bool(has_time or has_z), t_max)
    _sync_slider(getattr(owner, "z_slider", None), bool(has_z and has_time), z_max)
    if getattr(owner, "t_slider_label", None) is not None:
        owner.t_slider_label.setText(f"T: {int(owner.t_slider.value()) + 1}/{int(max(0, t_max)) + 1}")
    if getattr(owner, "z_slider_label", None) is not None:
        owner.z_slider_label.setText(f"Z: {int(owner.z_slider.value()) + 1}/{int(max(0, z_max)) + 1}")


def collect_panel_frame_bundle(
    owner: object,
    prim: object,
    visible_order: list[str],
    primary_panel: str,
    panel_specs: dict[str, object],
    t_idx: int,
    z_idx: int,
) -> PanelFrameBundle | None:
    """Collect raw and display frames for every visible render panel."""
    panel_images_raw: Dict[str, np.ndarray] = {}
    panel_sources: Dict[str, object] = {}
    panel_projections: Dict[str, str] = {}
    panel_projection_ready: Dict[str, bool] = {}
    for panel_key in visible_order:
        img = _panel_image(owner, prim, panel_key, panel_specs)
        owner._ensure_loaded(int(getattr(img, "id", owner.current_image_idx)))
        if getattr(img, "array", None) is None:
            continue
        data, ready, projection_key = _panel_data(owner, img, panel_key, primary_panel, panel_specs, t_idx, z_idx)
        if owner.crop_rect:
            data = owner._apply_crop_rect(data, owner.crop_rect, (data.shape[0], data.shape[1]))
        panel_sources[panel_key] = img
        panel_projections[panel_key] = projection_key
        panel_images_raw[panel_key] = data
        panel_projection_ready[panel_key] = bool(ready)
    _apply_binary_view(owner, primary_panel, panel_images_raw)
    if primary_panel not in panel_images_raw:
        primary_panel = next(iter(panel_images_raw.keys()), primary_panel)
    if not panel_images_raw:
        return None
    owner._last_display_shape = panel_images_raw[primary_panel].shape
    frame_ax, level = _select_downsample_level(owner, primary_panel, panel_images_raw)
    panel_images = _downsample_frames(owner, panel_images_raw, panel_sources, panel_projections, t_idx, z_idx, level)
    return PanelFrameBundle(
        primary_panel=primary_panel,
        panel_images_raw=panel_images_raw,
        panel_images=panel_images,
        panel_sources=panel_sources,
        panel_projections=panel_projections,
        panel_projection_ready=panel_projection_ready,
        frame_ax=frame_ax,
        level=level,
    )


def panel_projection_key(owner: object, panel_key: str, panel_specs: dict[str, object], default_projection: str = "raw") -> str:
    """Resolve the projection key for a panel spec or built-in lazy view."""
    spec = panel_specs.get(panel_key)
    if spec is None:
        builtin_views = dict(getattr(owner, "_lazy_builtin_views", {}) or {})
        if str(panel_key) in builtin_views:
            builtin_cfg = dict(builtin_views.get(str(panel_key), {}) or {})
            builtin_proj = str(builtin_cfg.get("projection", str(panel_key))).strip().lower()
            if builtin_proj not in {"mean", "std", "support"}:
                return builtin_proj
            return builtin_proj if builtin_proj != "support" else str(default_projection).strip().lower()
        return str(default_projection).strip().lower()
    projection = getattr(spec, "projection_type", default_projection)
    return str(getattr(projection, "value", projection)).strip().lower()


def _sync_slider(slider: object | None, enabled: bool, maximum: int) -> None:
    """Update one slider while blocking signal feedback."""
    if slider is None:
        return
    slider.blockSignals(True)
    slider.setEnabled(enabled)
    slider.setMaximum(int(max(0, maximum)))
    if slider.value() > maximum:
        slider.setValue(int(maximum))
    slider.blockSignals(False)


def _panel_image(owner: object, prim: object, panel_key: str, panel_specs: dict[str, object]) -> object:
    """Resolve which image object backs a visible panel."""
    spec = panel_specs.get(panel_key)
    default_img = owner.support_image if str(panel_key) == "modality_1" else prim
    if spec is None:
        builtin_views = dict(getattr(owner, "_lazy_builtin_views", {}) or {})
        if str(panel_key) in builtin_views:
            image_id = int(dict(builtin_views.get(str(panel_key), {}) or {}).get("image_id", getattr(default_img, "id", -1)))
            return next((cand for cand in owner.images if int(getattr(cand, "id", -1)) == image_id), default_img)
        return default_img
    image_id = int(getattr(spec, "image_id", getattr(default_img, "id", -1)))
    return next((cand for cand in owner.images if int(getattr(cand, "id", -1)) == image_id), default_img)


def _panel_data(owner: object, img: object, panel_key: str, primary_panel: str, panel_specs: dict[str, object], t_idx: int, z_idx: int) -> tuple[np.ndarray, bool, str]:
    """Load raw or projected frame data for one panel."""
    projection_key = panel_projection_key(owner, panel_key, panel_specs, "raw")
    if projection_key == "raw":
        data = owner._slice_data(img)
        if panel_key == primary_panel:
            composite_frame = owner._build_multichannel_frame(img, t_idx, z_idx)
            if composite_frame is not None:
                data = composite_frame
        return data, True, projection_key
    spec = panel_specs.get(panel_key)
    axis_override = getattr(getattr(spec, "display_settings", None), "projection_axis", None) if spec is not None else None
    modality_idx = int(getattr(spec, "idx", -1)) if spec is not None else None
    data, ready = owner._get_projection(img, projection_key, axis_override=axis_override, modality_idx=modality_idx)
    return (data if data is not None else owner._slice_data(img)), bool(ready), projection_key


def _apply_binary_view(owner: object, primary_panel: str, panel_images_raw: Dict[str, np.ndarray]) -> None:
    """Replace the primary frame with the binary mask when binary view is active."""
    if primary_panel not in panel_images_raw or not owner._binary_view_enabled or owner._binary_view_mask is None:
        return
    mask = owner._binary_view_mask
    if owner.crop_rect:
        mask = owner._apply_crop_rect(mask, owner.crop_rect, mask.shape)
    panel_images_raw[primary_panel] = mask.astype(np.float32, copy=False)


def _select_downsample_level(owner: object, primary_panel: str, panel_images_raw: Dict[str, np.ndarray]) -> tuple[object | None, int]:
    """Choose an interactive pyramid level and update render scale metadata."""
    frame_ax = None
    if getattr(owner, "renderer", None) is not None:
        frame_ax = owner.renderer.axes.get(primary_panel) or next(iter(owner.renderer.axes.values()), None)
    level = owner._select_pyramid_level(frame_ax, panel_images_raw[primary_panel].shape) if owner._interactive else 0
    scale = 2**level if owner._interactive and level > 0 else 1.0
    owner._render_scales = {ax: scale for ax in owner.renderer.axes.values()}
    return frame_ax, level


def _downsample_frames(owner: object, panel_images_raw: Dict[str, np.ndarray], panel_sources: dict[str, object], panel_projections: dict[str, str], t_idx: int, z_idx: int, level: int) -> Dict[str, np.ndarray]:
    """Create display frames from raw frames, using pyramid cache when possible."""
    panel_images: Dict[str, np.ndarray] = {}
    for panel_key, data in panel_images_raw.items():
        if not (owner._interactive and level > 0):
            panel_images[panel_key] = data
            continue
        scale = 2**level
        img = panel_sources.get(panel_key)
        if data.ndim == 3 or img is None:
            panel_images[panel_key] = owner._downsample(data, scale)
            continue
        projection_key = panel_projections.get(panel_key, "raw")
        panel_images[panel_key] = owner._get_pyramid_display(
            int(getattr(img, "id", -1)),
            f"{panel_key}:{projection_key}",
            data,
            t_idx if projection_key == "raw" else -1,
            z_idx if projection_key == "raw" else -1,
            owner.crop_rect or (0, 0, 0, 0),
            level,
        )
    return panel_images
