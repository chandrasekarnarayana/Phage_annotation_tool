"""Rendering pipeline helpers for the GUI.

This module orchestrates the display of microscopy data in matplotlib figures:
- Normalizes data (window/gamma/log transforms)
- Caches projections (mean/standard deviation)
- Applies color lookup tables (LUT) and inversion
- Manages overlay rendering (annotations, ROI, particles, SMLM results)
- Handles downsampling and coordinate transforms between full/display spaces

The rendering pipeline is fully asynchronous; results are cached and invalidated
when display settings or data bounds change. All rendering is Qt-free and can
be tested in isolation.

Key Classes
-----------
- RenderingMixin: Handles projection caching, LUT application, overlay rendering
- DisplayMapping: Stores brightness/contrast/gamma/LUT state per image/panel

Performance Considerations
--------------------------
- ProjectionCache stores (T, Z, Y, X) projections with LRU eviction
- Downsampling uses mean pooling for speed (not anti-aliased)
- Overlay rendering is deferred to separate pass for compositing
- Display window normalization uses matplotlib ColorNorm subclasses

Thread Safety
-------------
- Caching callbacks use stale-result guards (is_current_job) for race protection
- ProjectionCache is not thread-safe; only access from main thread
- Worker threads compute projections; results posted back to main thread
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from matplotlib import colormaps

from phage_annotator.data.channel_display import MultiChannelDisplaySettings
from phage_annotator.data.display_mapping import DisplayMapping, build_norm
from phage_annotator.ui_qt.rendering.blend_modes import composite_channels
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, cmap_for
from phage_annotator.ui_qt.rendering.renderer_overlays import RenderingOverlayMixin
from phage_annotator.ui_qt.utils.image_io import load_array
from phage_annotator.rendering.mpl import RenderContext
from phage_annotator.rendering.scalebar import ScaleBarSpec, compute_scalebar


class RenderingMixin(RenderingOverlayMixin):
    """Mixin for image rendering and overlay composition."""

    def _request_render_refresh(self, reason: str = "render", *, debounce: bool = False) -> None:
        """Queue an image refresh without hard-wiring callers to `_refresh_image`.

        Parameters
        ----------
        reason:
            Diagnostic reason string for the queued refresh.
        debounce:
            When ``True``, use the dedicated debounce timer. This is reserved for
            render/projection job completions where an immediate queued refresh
            could re-enter projection scheduling too aggressively.
        """
        if debounce and hasattr(self, "_debounce_timer"):
            try:
                self._debounce_timer.start()
                return
            except RuntimeError:
                return
        if hasattr(self, "_request_ui_refresh"):
            self._request_ui_refresh(str(reason), image=True, status=True)
            return
        self._refresh_image()

    def _suggestion_overlay_style(self, suggestion) -> tuple[str, str]:
        """Return (color, trust_state) for a suggestion overlay marker."""
        meta = dict(getattr(suggestion, "meta", {}) or {})
        candidate_class = str(meta.get("candidate_class", "new")).strip().lower()
        status = str(getattr(suggestion, "status", "proposed")).strip().lower()
        if status == "rejected":
            return "#b0bec5", "rejected"
        if status == "accepted":
            return "#1565c0", "accepted"
        if candidate_class == "conflict":
            return "#e53935", "conflict"
        if candidate_class == "near_existing":
            return "#fb8c00", "near_existing"
        confidence_available = bool(meta.get("confidence_available", False))
        if not confidence_available:
            return "#9e9e9e", "heuristic"
        p_accept = float(meta.get("p_accept", getattr(suggestion, "score", 0.0)))
        if p_accept >= 0.75:
            return "#43a047", "calibrated_high"
        if p_accept >= 0.5:
            return "#fdd835", "calibrated_mid"
        return "#e53935", "calibrated_low"

    def _get_channel_stack(self, img, channel_idx: int) -> Optional[np.ndarray]:
        """Load/cache standardized stack for a specific channel."""
        if channel_idx < 0 or channel_idx >= int(getattr(img, "channel_count", 1)):
            return None
        cache = getattr(img, "_channel_stack_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(img, "_channel_stack_cache", cache)
        if channel_idx in cache:
            return cache[channel_idx]
        current_idx = int(getattr(img, "channel_idx", 0))
        if img.array is not None and channel_idx == current_idx:
            cache[channel_idx] = img.array
            return img.array
        arr, _has_time, _has_z = load_array(
            img.path,
            interpret_3d_as=img.interpret_3d_as,
            ome_axes=img.ome_axes,
            channel_idx=channel_idx,
        )
        cache[channel_idx] = arr
        return arr

    def _normalize_channel_frame(self, frame: np.ndarray) -> np.ndarray:
        """Normalize a channel frame to [0, 1] for compositing."""
        data = np.asarray(frame, dtype=np.float32)
        if data.size == 0:
            return data
        finite = np.isfinite(data)
        if not finite.any():
            return np.zeros_like(data, dtype=np.float32)
        vals = data[finite]
        lo, hi = np.percentile(vals, [1.0, 99.0])
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo = float(np.min(vals))
            hi = float(np.max(vals))
            if hi <= lo:
                return np.zeros_like(data, dtype=np.float32)
        normalized = (data - lo) / (hi - lo)
        normalized = np.clip(normalized, 0.0, 1.0)
        normalized[~finite] = 0.0
        return normalized.astype(np.float32, copy=False)

    def _build_multichannel_frame(self, img, t_idx: int, z_idx: int) -> Optional[np.ndarray]:
        """Build an RGB frame using per-channel settings and blend mode."""
        if int(getattr(img, "channel_count", 1)) <= 1:
            return None
        settings_raw = getattr(self.controller.session_state, "channel_display_settings", None)
        if not isinstance(settings_raw, dict):
            return None
        try:
            settings = MultiChannelDisplaySettings.from_dict(settings_raw)
        except Exception:
            return None
        if settings.channel_count != int(getattr(img, "channel_count", 1)):
            return None
        layers: List[Tuple[np.ndarray, float]] = []
        for state in settings.channels:
            if not state.visible or state.opacity <= 0:
                continue
            stack = self._get_channel_stack(img, int(state.channel_idx))
            if stack is None or stack.ndim != 4:
                continue
            t_safe = max(0, min(int(t_idx), stack.shape[0] - 1))
            z_safe = max(0, min(int(z_idx), stack.shape[1] - 1))
            frame = stack[t_safe, z_safe, :, :]
            normalized = self._normalize_channel_frame(frame)
            lut_idx = max(0, min(int(state.lut), len(LUTS) - 1))
            cmap = cmap_for(LUTS[lut_idx], invert=False)
            rgb = cmap(normalized)[..., :3].astype(np.float32, copy=False)
            layers.append((rgb, float(state.opacity)))
        if not layers:
            return None
        return composite_channels(
            layers,
            blend_mode=settings.blend_mode,
            normalize_output=True,
        )

    def _clear_histogram_cache(self) -> None:
        try:
            if self._hist_job_id is not None:
                self.jobs.cancel(self._hist_job_id)
                self._hist_job_id = None
            self._hist_cache = None
            self._hist_cache_key = None
            self._status_success(
                "Histogram cache cleared.",
                timeout_ms=2500,
                source="renderer.histogram_cache",
            )
            # Redraw to reflect cleared cache; will recompute on demand
            self._request_render_refresh("histogram-cache-cleared")
        except Exception as exc:
            self._append_log(f"[Hist] Clear cache error: {exc}")

    def _refresh_image(self) -> None:
        """Refresh the image display using current state."""
        if not self.images:
            return
        prim = self.primary_image
        self._ensure_loaded(self.current_image_idx)
        if prim.array is None:
            return
        has_time, has_z = self._effective_axes(prim)
        t_max = max(0, int(prim.array.shape[0]) - 1)
        z_max = max(0, int(prim.array.shape[1]) - 1)
        if not has_time and has_z:
            t_max = z_max

        if getattr(self, "t_slider", None) is not None:
            self.t_slider.blockSignals(True)
            self.t_slider.setEnabled(bool(has_time or has_z))
            self.t_slider.setMaximum(int(max(0, t_max)))
            if self.t_slider.value() > t_max:
                self.t_slider.setValue(int(t_max))
            self.t_slider.blockSignals(False)

        if getattr(self, "z_slider", None) is not None:
            self.z_slider.blockSignals(True)
            self.z_slider.setEnabled(bool(has_z and has_time))
            self.z_slider.setMaximum(int(max(0, z_max)))
            if self.z_slider.value() > z_max:
                self.z_slider.setValue(int(z_max))
            self.z_slider.blockSignals(False)

        if getattr(self, "t_slider_label", None) is not None:
            self.t_slider_label.setText(
                f"T: {int(self.t_slider.value()) + 1}/{int(max(0, t_max)) + 1}"
            )
        if getattr(self, "z_slider_label", None) is not None:
            self.z_slider_label.setText(
                f"Z: {int(self.z_slider.value()) + 1}/{int(max(0, z_max)) + 1}"
            )

        layout_spec = self._current_layout_spec()
        self._rebuild_figure_layout(layout_spec)
        self._capture_zoom_state()
        visible_order = [
            k for k in layout_spec.get("order", [])
            if bool(layout_spec.get("panel_visibility", {}).get(k, False))
        ]
        primary_panel = str(visible_order[0]) if visible_order else (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        if not visible_order:
            self._update_axes_info()
            self._update_axis_warning()
            self._update_status()
            return
        t_idx, z_idx = self._slice_indices(prim)
        panel_specs = dict(getattr(self, "_panel_modality_map", {}) or {})

        def _panel_projection_key(panel_key: str, default_projection: str = "raw") -> str:
            spec = panel_specs.get(panel_key)
            if spec is None:
                # Check if this is a builtin view (mean, std, support)
                builtin_views = dict(getattr(self, "_lazy_builtin_views", {}) or {})
                if str(panel_key) in builtin_views:
                    builtin_cfg = dict(builtin_views.get(str(panel_key), {}) or {})
                    builtin_proj = str(builtin_cfg.get("projection", str(panel_key))).strip().lower()
                    if builtin_proj not in {"mean", "std", "support"}:
                        return builtin_proj
                    return builtin_proj if builtin_proj != "support" else str(default_projection).strip().lower()
                return str(default_projection).strip().lower()
            projection = getattr(spec, "projection_type", default_projection)
            return str(getattr(projection, "value", projection)).strip().lower()

        def _panel_image(panel_key: str):
            spec = panel_specs.get(panel_key)
            default_img = prim
            if str(panel_key) == "modality_1":
                default_img = self.support_image
            if spec is None:
                # Check if this is a builtin view with a configured source image
                builtin_views = dict(getattr(self, "_lazy_builtin_views", {}) or {})
                if str(panel_key) in builtin_views:
                    builtin_cfg = dict(builtin_views.get(str(panel_key), {}) or {})
                    builtin_image_id = int(builtin_cfg.get("image_id", getattr(default_img, "id", -1)))
                    img = next((cand for cand in self.images if int(getattr(cand, "id", -1)) == builtin_image_id), None)
                    return img if img is not None else default_img
                return default_img
            image_id = int(getattr(spec, "image_id", getattr(default_img, "id", -1)))
            img = next((cand for cand in self.images if int(getattr(cand, "id", -1)) == image_id), None)
            return img if img is not None else default_img

        panel_images_raw: Dict[str, np.ndarray] = {}
        panel_images: Dict[str, np.ndarray] = {}
        panel_sources: Dict[str, object] = {}
        panel_projections: Dict[str, str] = {}
        panel_projection_ready: Dict[str, bool] = {}
        crop_rect = self.crop_rect
        for panel_key in visible_order:
            img = _panel_image(panel_key)
            self._ensure_loaded(int(getattr(img, "id", self.current_image_idx)))
            if getattr(img, "array", None) is None:
                continue
            projection_key = _panel_projection_key(panel_key, "raw")
            panel_sources[panel_key] = img
            panel_projections[panel_key] = projection_key
            data = None
            ready = True
            if projection_key == "raw":
                data = self._slice_data(img)
                if panel_key == primary_panel:
                    composite_frame = self._build_multichannel_frame(img, t_idx, z_idx)
                    if composite_frame is not None:
                        data = composite_frame
            else:
                spec = panel_specs.get(panel_key)
                axis_override = (
                    getattr(getattr(spec, "display_settings", None), "projection_axis", None)
                    if spec is not None
                    else None
                )
                modality_idx = int(getattr(spec, "idx", -1)) if spec is not None else None
                data, ready = self._get_projection(
                    img,
                    projection_key,
                    axis_override=axis_override,
                    modality_idx=modality_idx,
                )
                if data is None:
                    data = self._slice_data(img)
            if crop_rect:
                data = self._apply_crop_rect(data, crop_rect, (data.shape[0], data.shape[1]))
            panel_images_raw[panel_key] = data
            panel_projection_ready[panel_key] = bool(ready)

        if primary_panel in panel_images_raw and self._binary_view_enabled and self._binary_view_mask is not None:
            mask = self._binary_view_mask
            if crop_rect:
                mask = self._apply_crop_rect(mask, crop_rect, mask.shape)
            panel_images_raw[primary_panel] = mask.astype(np.float32, copy=False)

        if primary_panel not in panel_images_raw:
            primary_panel = next(iter(panel_images_raw.keys()), primary_panel)
        if not panel_images_raw:
            self._update_axes_info()
            self._update_axis_warning()
            self._update_status()
            return
        self._last_display_shape = panel_images_raw[primary_panel].shape

        # Interactive downsampling (display-only).
        level = 0
        frame_ax = None
        if getattr(self, "renderer", None) is not None:
            frame_ax = self.renderer.axes.get(primary_panel)
            if frame_ax is None:
                frame_ax = next(iter(self.renderer.axes.values()), None)
        if self._interactive:
            level = self._select_pyramid_level(frame_ax, panel_images_raw[primary_panel].shape)
            if level > 0:
                scale = 2**level
                self._render_scales = {ax: scale for ax in self.renderer.axes.values()}
            else:
                self._render_scales = {ax: 1.0 for ax in self.renderer.axes.values()}
        else:
            self._render_scales = {ax: 1.0 for ax in self.renderer.axes.values()}
        for panel_key, data in panel_images_raw.items():
            if not (self._interactive and level > 0):
                panel_images[panel_key] = data
                continue
            if data.ndim == 3:
                panel_images[panel_key] = self._downsample(data, 2**level)
                continue
            img = panel_sources.get(panel_key)
            if img is None:
                panel_images[panel_key] = self._downsample(data, 2**level)
                continue
            projection_key = panel_projections.get(panel_key, "raw")
            cache_kind = f"{panel_key}:{projection_key}"
            if projection_key == "raw":
                panel_images[panel_key] = self._get_pyramid_display(
                    int(getattr(img, "id", -1)),
                    cache_kind,
                    data,
                    t_idx,
                    z_idx,
                    self.crop_rect or (0, 0, 0, 0),
                    level,
                )
            else:
                panel_images[panel_key] = self._get_pyramid_display(
                    int(getattr(img, "id", -1)),
                    cache_kind,
                    data,
                    -1,
                    -1,
                    self.crop_rect or (0, 0, 0, 0),
                    level,
                )

        vmin, vmax = self._current_vmin_vmax()
        def _panel_title(panel_key: str, fallback: str) -> str:
            spec = panel_specs.get(panel_key)
            base = str(getattr(spec, "display_name", fallback) if spec is not None else fallback)
            proj = _panel_projection_key(panel_key, "raw")
            if proj == "raw":
                return f"{base} (T={t_idx}, Z={z_idx})"
            return base

        titles = {}
        for panel_key in panel_images.keys():
            spec = panel_specs.get(panel_key)
            fallback = str(getattr(spec, "display_name", panel_key) if spec is not None else panel_key)
            titles[panel_key] = _panel_title(panel_key, fallback)
        extents = {}
        for key, data in list(panel_images.items()):
            if data is None:
                panel_images.pop(key, None)
                continue
            extents[key] = (0, data.shape[1], data.shape[0], 0)
        panel_annotations = self._build_panel_annotations()
        suggestion_staleness_labels = self._build_suggestion_staleness_labels()
        roi_overlays = self._build_roi_overlays()
        overlay_text = self._build_overlay_text()
        canvas_header_text = self._build_canvas_header_text()
        roi_spec = self.controller.view_state.roi_spec
        roi_rect = roi_spec.rect
        roi_type = roi_spec.shape
        if roi_type == "none" or roi_rect[2] <= 0 or roi_rect[3] <= 0:
            roi_type = "none"
            roi_rect = None
        roi_scale = self._axis_scale(frame_ax) if frame_ax is not None else 1.0
        roi_offset = (self.crop_rect[0], self.crop_rect[1]) if self.crop_rect else (0.0, 0.0)
        panel_mappings = {}
        for key, data in panel_images.items():
            img = panel_sources.get(key)
            if img is None or data is None:
                continue
            panel_mappings[key] = self._get_display_mapping(int(getattr(img, "id", -1)), key, data)
        primary_mapping = panel_mappings.get(primary_panel)
        if primary_mapping is None:
            first_key = next(iter(panel_mappings.keys()), None)
            if first_key is not None:
                primary_mapping = panel_mappings[first_key]
        if primary_mapping is None:
            return
        std_panel_key = next(
            (k for k, p in panel_projections.items() if str(p).strip().lower() == "std" and k in panel_mappings),
            primary_panel,
        )
        std_mapping = panel_mappings.get(std_panel_key, primary_mapping)
        std_vmin, std_vmax = std_mapping.min_val, std_mapping.max_val
        norms = {}
        for key, mapping in panel_mappings.items():
            if self._playback_mode:
                norms[key] = self._norm_cached(key, mapping)
            else:
                norms[key] = build_norm(mapping)
            if panel_images.get(key) is not None and panel_images[key].ndim == 3:
                norms[key] = None

        def _spec(idx: int):
            if idx < 0:
                return LUTS[0]
            if idx >= len(LUTS):
                return LUTS[-1]
            return LUTS[idx]

        panel_cmaps = {}
        panel_ranges = {}
        for key, mapping in panel_mappings.items():
            panel_cmaps[key] = cmap_for(_spec(mapping.lut), mapping.invert)
            panel_ranges[key] = (mapping.min_val, mapping.max_val)
        overlay_frame = None
        overlay_extent = None
        if self.show_sr_overlay:
            overlay_frame = self._sr_overlay if self._sr_overlay is not None else self._smlm_overlay
            overlay_extent = (
                self._sr_overlay_extent
                if self._sr_overlay is not None
                else self._smlm_overlay_extent
            )
        # Validate density overlay is for current image
        current_img_id = self.primary_image.id if hasattr(self, 'primary_image') else -1
        density_img_id = getattr(self, '_density_image_id', None)
        if self._density_overlay is not None and density_img_id == current_img_id:
            density = self._density_overlay
            if self.crop_rect:
                x, y, w, h = self.crop_rect
                x0 = int(max(0, x))
                y0 = int(max(0, y))
                x1 = int(min(density.shape[1], x + w))
                y1 = int(min(density.shape[0], y + h))
                density = density[y0:y1, x0:x1]
            overlay_frame = density
            overlay_extent = (0, density.shape[1], density.shape[0], 0)
        if overlay_frame is not None and self._interactive and self.downsample_images:
            stride = max(1, int(self.downsample_factor))
            overlay_frame = overlay_frame[::stride, ::stride]
        loc_points = []
        if self.show_smlm_points and frame_ax is not None:
            # Validate that results are for the current image
            current_img_id = self.primary_image.id if hasattr(self, 'primary_image') else -1
            smlm_img_id = getattr(self, '_smlm_image_id', None)
            deepstorm_img_id = getattr(self, '_deepstorm_image_id', None)
            
            scale = self._axis_scale(frame_ax)
            off_x = self.crop_rect[0] if self.crop_rect else 0.0
            off_y = self.crop_rect[1] if self.crop_rect else 0.0
            if self._smlm_results and smlm_img_id == current_img_id:
                color_mode = getattr(self.smlm_panel, "thunder", None)
                color_field = "photons"
                if color_mode is not None and hasattr(color_mode, "color_mode_combo"):
                    color_field = color_mode.color_mode_combo.currentText().lower()
                for loc in self._smlm_results:
                    val = loc.photons if color_field.startswith("phot") else loc.uncertainty_px
                    loc_points.append(
                        (
                            (loc.x_px - off_x) / scale,
                            (loc.y_px - off_y) / scale,
                            float(val),
                        )
                    )
            elif self._deepstorm_results and deepstorm_img_id == current_img_id:
                for loc in self._deepstorm_results:
                    loc_points.append(
                        (
                            (loc.x_px - off_x) / scale,
                            (loc.y_px - off_y) / scale,
                            float(loc.score),
                        )
                    )
        scale_bar = None
        scale_bar_warning = None
        if self.scale_bar_enabled:
            cal = self._get_calibration_state(prim.id)
            if cal.pixel_size_um_per_px:
                spec = ScaleBarSpec(
                    enabled=True,
                    length_um=self.scale_bar_length_um,
                    thickness_px=self.scale_bar_thickness_px,
                    location=self.scale_bar_location,
                    padding_px=self.scale_bar_padding_px,
                    show_text=self.scale_bar_show_text,
                    text_offset_px=self.scale_bar_text_offset_px,
                    background_box=self.scale_bar_background_box,
                )
                primary_shape = panel_images[primary_panel].shape
                extent = extents.get(primary_panel) or (
                    0,
                    primary_shape[1],
                    primary_shape[0],
                    0,
                )
                scale_bar = compute_scalebar(extent, cal.pixel_size_um_per_px, spec)
                if scale_bar is not None:
                    scale_bar["background_box"] = self.scale_bar_background_box
            else:
                scale_bar_warning = "Scale bar requires calibration"

        ctx = RenderContext(
            image_frame=panel_images.get(primary_panel),
            support_frame=panel_images.get("support"),
            projections={
                "mean": panel_images.get("mean"),
                "std": panel_images.get("std"),
            },
            panel_images=panel_images,
            primary_panel=primary_panel,
            view=self.controller.view_state,
            annotations=self._current_keypoints(),
            panel_visibility=layout_spec["panel_visibility"],
            titles=titles,
            extents=extents,
            std_range=(std_vmin, std_vmax),
            panel_annotations=panel_annotations,
            suggestion_staleness_labels=suggestion_staleness_labels,
            roi_overlays=roi_overlays,
            overlay_text=overlay_text,
            canvas_header_text=canvas_header_text,
            marker_size=self.marker_size,
            marker_shape=str(getattr(self, "marker_shape", "o") or "o"),
            norms=norms,
            panel_cmaps=panel_cmaps,
            panel_ranges=panel_ranges,
            localization_points=loc_points,
            localization_visible=bool(loc_points),
            threshold_mask=(
                self._threshold_preview_mask if self._threshold_preview_mask is not None else None
            ),
            threshold_extent=self._threshold_preview_extent,
            threshold_visible=bool(self._threshold_preview_mask is not None),
            particle_overlays=self._particles_overlays,
            particle_labels=self._particle_labels(),
            overlay_frame=overlay_frame,
            overlay_extent=overlay_extent,
            overlay_alpha=(
                float(self._density_overlay_alpha) if self._density_overlay is not None else 0.6
            ),
            overlay_norm=None,
            overlay_cmap=(
                colormaps.get_cmap(self._density_overlay_cmap)
                if self._density_overlay is not None
                else None
            ),
            density_contours=bool(self._density_contours),
            scale_bar=scale_bar,
            scale_bar_warning=scale_bar_warning,
            roi_scale=roi_scale,
            roi_offset=roi_offset,
            roi_show_handles=bool(self.show_roi_handles),
            roi_type=roi_type,
            roi_rect=roi_rect,
        )
        self.renderer.update_images(ctx)
        self.renderer.update_overlays(ctx)
        self.im_frame = self.renderer.image_artists.get(primary_panel)
        self.im_mean = self.renderer.image_artists.get("mean")
        self.im_support = self.renderer.image_artists.get("support")
        self.im_std = self.renderer.image_artists.get("std")
        self._refresh_orthoview(
            prim,
            t_idx,
            z_idx,
            norms.get(primary_panel),
            panel_cmaps.get(primary_panel, self.colormaps[0]),
        )
        mean_panel = next((k for k, p in panel_projections.items() if p == "mean"), None)
        std_panel = next((k for k, p in panel_projections.items() if p == "std"), None)
        mean_ax = (
            self.renderer.axes.get(mean_panel)
            if mean_panel is not None and getattr(self, "renderer", None) is not None
            else None
        )
        std_ax = (
            self.renderer.axes.get(std_panel)
            if std_panel is not None and getattr(self, "renderer", None) is not None
            else None
        )
        mean_ready = (
            panel_projection_ready.get(mean_panel, True)
            if mean_panel is not None
            else True
        )
        std_ready = (
            panel_projection_ready.get(std_panel, True)
            if std_panel is not None
            else True
        )
        if mean_ax is not None and not mean_ready:
            mean_ax.text(
                0.5,
                0.5,
                "Computing mean...",
                transform=mean_ax.transAxes,
                ha="center",
                va="center",
            )
        if std_ax is not None and not std_ready:
            std_ax.text(
                0.5,
                0.5,
                "Computing std...",
                transform=std_ax.transAxes,
                ha="center",
                va="center",
            )

        if frame_ax is not None:
            self._restore_zoom(panel_images[primary_panel].shape)
        self._draw_diagnostics(panel_images_raw[primary_panel], vmin, vmax)
        self._update_axes_info()
        self._update_axis_warning()
        if self.lut_combo is not None:
            if 0 <= primary_mapping.lut < self.lut_combo.count():
                self.lut_combo.blockSignals(True)
                self.lut_combo.setCurrentIndex(primary_mapping.lut)
                self.lut_combo.blockSignals(False)
        if self.lut_invert_chk is not None:
            invert_supported = True
            if 0 <= primary_mapping.lut < len(LUTS):
                invert_supported = LUTS[primary_mapping.lut].invert_supported
            self.lut_invert_chk.blockSignals(True)
            self.lut_invert_chk.setChecked(primary_mapping.invert)
            self.lut_invert_chk.setEnabled(invert_supported)
            self.lut_invert_chk.blockSignals(False)
        if self.gamma_slider is not None and self.gamma_label is not None:
            gamma_val = max(0.2, min(5.0, float(primary_mapping.gamma)))
            self.gamma_slider.blockSignals(True)
            self.gamma_slider.setValue(int(round(gamma_val * 10)))
            self.gamma_slider.blockSignals(False)
            self.gamma_label.setText(f"{gamma_val:.2f}")
        if self.log_chk is not None:
            self.log_chk.blockSignals(True)
            self.log_chk.setChecked(primary_mapping.mode == "log")
            self.log_chk.blockSignals(False)
        # Update projection selector (Phase γ UI wiring)
        if getattr(self, "projection_selector", None) is not None:
            manager = getattr(self.controller.session_state, "modality_manager", None)
            if manager is not None:
                for modality in manager.get_all_modalities():
                    if modality.image_id == self.primary_image.id:
                        self.projection_selector.blockSignals(True)
                        self.projection_selector.set_modality(modality)
                        self.projection_selector.blockSignals(False)
                        break
        elif getattr(self, "projection_axis_combo", None) is not None:
            # Backward compat for old axis-only combo
            axis = "t"
            manager = getattr(self.controller.session_state, "modality_manager", None)
            if manager is not None:
                for modality in manager.get_all_modalities():
                    if modality.image_id == self.primary_image.id:
                        axis = modality.display_settings.projection_axis
                        break
            self.projection_axis_combo.blockSignals(True)
            self.projection_axis_combo.setCurrentText(axis.upper())
            self.projection_axis_combo.blockSignals(False)
        if self.render_level_label is not None:
            self.render_level_label.setText(f"Render: L{level}")
        self._update_status()
        # Keep evidence-layer config normalized with current session defaults.
        self._refresh_modality_layers_panel()

    def _refresh_orthoview(self, prim, t_idx: int, z_idx: int, norm, cmap) -> None:
        if self.orthoview_widget is None:
            return
        if self.dock_orthoview is not None and not self.dock_orthoview.isVisible():
            return
        if prim.array is None or not prim.has_z:
            self.orthoview_widget.update_views(
                None,
                None,
                (0.0, 0.0),
                z_idx,
                (0, 0, 0),
                1,
                norm,
                cmap,
                message="No Z axis available.",
            )
            return
        stack = prim.array[t_idx]
        if stack is None or stack.ndim != 3:
            return
        z_dim, y_dim, x_dim = stack.shape
        if self._cursor_xy is None:
            self._cursor_xy = (x_dim / 2.0, y_dim / 2.0)
        x_full, y_full = self._cursor_xy
        x_idx = int(np.clip(round(x_full), 0, x_dim - 1))
        y_idx = int(np.clip(round(y_full), 0, y_dim - 1))
        xz = stack[:, y_idx, :]
        yz = stack[:, :, x_idx]
        downsample = 1
        if self._interactive and self.downsample_images:
            downsample = max(1, int(self.downsample_factor))
            if downsample > 1:
                xz = xz[::downsample, ::downsample]
                yz = yz[::downsample, ::downsample]
        throttle_ms = 500 if self._playback_mode else None
        self.orthoview_widget.update_views(
            xz,
            yz,
            (x_idx, y_idx),
            z_idx,
            (z_dim, y_dim, x_dim),
            downsample,
            norm,
            cmap,
            throttle_ms=throttle_ms,
        )

    def _set_cursor_xy(self, x: float, y: float, refresh: bool = True) -> None:
        """Update the crosshair position used by orthogonal views."""
        self._cursor_xy = (float(x), float(y))
        if refresh:
            self._request_render_refresh("cursor-updated")

    def _on_orthoview_xz_click(self, x: int, z: int) -> None:
        y = self._cursor_xy[1] if self._cursor_xy is not None else self._default_cursor()[1]
        self._set_cursor_xy(x, y, refresh=False)
        if self.z_slider is not None:
            self.z_slider.setValue(int(z))

    def _on_orthoview_yz_click(self, y: int, z: int) -> None:
        x = self._cursor_xy[0] if self._cursor_xy is not None else self._default_cursor()[0]
        self._set_cursor_xy(x, y, refresh=False)
        if self.z_slider is not None:
            self.z_slider.setValue(int(z))

    def _default_cursor(self) -> Tuple[float, float]:
        prim = self.primary_image
        if prim.array is None:
            return (0.0, 0.0)
        if prim.array.ndim == 4:
            _, _, y_dim, x_dim = prim.array.shape
        elif prim.array.ndim == 3:
            _, y_dim, x_dim = prim.array.shape
        else:
            return (0.0, 0.0)
        return (x_dim / 2.0, y_dim / 2.0)


    def _get_display_mapping(
        self, image_id: int, panel: str, data: Optional[np.ndarray]
    ) -> DisplayMapping:
        created = image_id not in self.controller.display_mapping.per_image
        mapping = self.controller.display_mapping.mapping_for(image_id, panel)
        panel_map = getattr(self, "_panel_modality_map", {})
        modality = panel_map.get(panel)
        if modality is not None:
            settings = modality.display_settings
            if created:
                if settings.vmax > settings.vmin:
                    mapping.set_window(settings.vmin, settings.vmax)
                    mapping.lut = settings.lut
                    mapping.gamma = settings.gamma
                elif data is not None:
                    mapping.reset_to_auto(data)
                    settings.vmin = mapping.min_val
                    settings.vmax = mapping.max_val
            if data is not None and mapping.min_val == mapping.max_val:
                mapping.reset_to_auto(data)
                settings.vmin = mapping.min_val
                settings.vmax = mapping.max_val
            return mapping
        if data is not None and (created or mapping.min_val == mapping.max_val):
            mapping.reset_to_auto(data)
        return mapping

    def _toggle_overlay(self, checked: bool) -> None:
        self.overlay_enabled = checked
        self._request_render_refresh("overlay-toggled")

    def _draw_diagnostics(self, slice_data: np.ndarray, vmin: float, vmax: float) -> None:
        """Update histogram and profile diagnostics."""
        profile_visible = self.dock_profile is None or self.dock_profile.isVisible()
        if (
            self.profile_enabled
            and self.profile_chk.isChecked()
            and profile_visible
            and self.ax_line is not None
        ):
            self.ax_line.clear()
            if self.profile_line:
                (y1, x1), (y2, x2) = self.profile_line
                yy, xx = np.linspace(y1, y2, 200), np.linspace(x1, x2, 200)
                vals = slice_data[
                    yy.astype(int).clip(0, slice_data.shape[0] - 1),
                    xx.astype(int).clip(0, slice_data.shape[1] - 1),
                ]
                self.ax_line.plot(vals)
                self.ax_line.set_title("Line profile (user)")
            else:
                y_center = slice_data.shape[0] // 2
                profile = slice_data[y_center, :]
                self.ax_line.plot(profile)
                self.ax_line.set_title("Line profile (center row)")
            self.ax_line.set_xlabel("X")
            self.ax_line.set_ylabel("Intensity")
            self.ax_line.axis("on")
        else:
            if self.ax_line is not None:
                self.ax_line.clear()
                self.ax_line.axis("off")
        if self.profile_canvas is not None:
            self.profile_canvas.draw_idle()

        hist_canvases = []
        primary_hist_visible = self.dock_hist is None or self.dock_hist.isVisible()
        if getattr(self, "ax_hist", None) is not None and getattr(self, "hist_canvas", None) is not None:
            hist_canvases.append((self.ax_hist, self.hist_canvas, bool(primary_hist_visible)))
        embedded_ax = getattr(self, "ax_contrast_hist", None)
        embedded_canvas = getattr(self, "contrast_hist_canvas", None)
        if embedded_ax is not None and embedded_canvas is not None:
            hist_canvases.append((embedded_ax, embedded_canvas, bool(embedded_canvas.isVisible())))

        hist_visible = any(visible for _ax, _canvas, visible in hist_canvases)
        hist_enabled = bool(getattr(self, "hist_enabled", True))
        hist_chk = getattr(self, "hist_chk", None)
        hist_checked = True if hist_chk is None else bool(hist_chk.isChecked())
        if hist_enabled and hist_checked and hist_visible and hist_canvases:
            if self._playback_mode and (time.monotonic() - self._hist_last_time) < 0.5:
                return
            self._hist_last_time = time.monotonic()
            vals = self._hist_values(slice_data)
            if vals is None:
                return
            bins_widget = getattr(self, "contrast_hist_bins_spin", None) or getattr(self, "hist_bins_spin", None)
            bins = int(bins_widget.value()) if bins_widget is not None else 64
            counts, edges = np.histogram(vals, bins=bins)
            centers = 0.5 * (edges[:-1] + edges[1:])
            stats = None
            if vals.size:
                mean = float(np.mean(vals))
                median = float(np.median(vals))
                std = float(np.std(vals))
                sat_low = int(np.sum(vals < vmin))
                sat_high = int(np.sum(vals > vmax))
                stats = (
                    f"Mean {mean:.3f} | Median {median:.3f} | Std {std:.3f} | "
                    f"Sat low {sat_low} | Sat high {sat_high}"
                )
            for axis, canvas, visible in hist_canvases:
                if not visible:
                    continue
                axis.clear()
                axis.plot(centers, counts, color="#5555aa")
                axis.axvline(vmin, color="#ff8800", linestyle="--", linewidth=1)
                axis.axvline(vmax, color="#ff8800", linestyle="--", linewidth=1)
                axis.set_title("Intensity histogram")
                axis.set_xlabel("Intensity")
                axis.set_ylabel("Count")
                if stats:
                    axis.text(
                        0.02,
                        0.95,
                        stats,
                        transform=axis.transAxes,
                        va="top",
                        fontsize=8,
                    )
                axis.axis("on")
                canvas.draw_idle()
            self._update_bc_controls(vals, vmin, vmax)
        else:
            for axis, canvas, _visible in hist_canvases:
                axis.clear()
                axis.axis("off")
                canvas.draw_idle()

    def _hist_values(self, slice_data: np.ndarray) -> Optional[np.ndarray]:
        region = self.hist_region
        scope = self._hist_scope_mode
        if scope == "Sampled stack":
            cache_key = (
                self.primary_image.id,
                region,
                self.crop_rect,
                self.roi_rect,
                self.roi_shape,
            )
            if self._hist_cache is not None and self._hist_cache_key == cache_key:
                return self._hist_cache
            if self._hist_job_id is not None and self._hist_cache_key != cache_key:
                self.jobs.cancel(self._hist_job_id)
                self._hist_job_id = None
            if self._hist_job_id is None:
                self._request_hist_job(cache_key)
            if self._interactive:
                return self._hist_values_current(slice_data)
            return None
        return self._hist_values_current(slice_data)

    def _hist_values_current(self, slice_data: np.ndarray) -> np.ndarray:
        if self.hist_region == "crop" and self.crop_rect is not None:
            data = self._apply_crop_rect(
                slice_data, self.crop_rect, (slice_data.shape[0], slice_data.shape[1])
            )
        else:
            data = slice_data
        if self.hist_region == "roi":
            mask = self._roi_mask(slice_data.shape)
            data = slice_data[mask]
        if self._interactive and self.downsample_hist:
            stride = max(1, self.downsample_factor)
            data = data[::stride, ::stride]
        return data.ravel()

    def _request_hist_job(self, cache_key) -> None:
        if self._hist_job_id is not None:
            return
        prim = self.primary_image
        if prim.array is None:
            return
        arr = prim.array
        region = self.hist_region
        crop_rect = self.crop_rect
        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        job_gen = self._job_generation

        def _job(progress, cancel_token):
            t_count, z_count = arr.shape[0], arr.shape[1]
            t_step = max(1, t_count // 16)
            z_step = max(1, z_count // 8)
            samples = []
            roi_mask = None
            roi_mask_shape = None
            for t in range(0, t_count, t_step):
                for z in range(0, z_count, z_step):
                    if cancel_token.is_cancelled():
                        return None
                    frame = arr[t, z, :, :]
                    if region == "crop" and crop_rect is not None:
                        frame = self._apply_crop_rect(
                            frame, crop_rect, (frame.shape[0], frame.shape[1])
                        )
                    if region == "roi":
                        frame_hw = frame.shape[:2]
                        if roi_mask is None or roi_mask_shape != frame_hw:
                            h, w = frame_hw
                            y = np.arange(h)[:, None]
                            x = np.arange(w)[None, :]
                            rx, ry, rw, rh = roi_rect
                            if roi_shape == "circle":
                                cx, cy = rx + rw / 2, ry + rh / 2
                                r = min(rw, rh) / 2
                                roi_mask = (x - cx) ** 2 + (y - cy) ** 2 <= r**2
                            else:
                                roi_mask = (rx <= x) & (x <= rx + rw) & (ry <= y) & (y <= ry + rh)
                            roi_mask_shape = frame_hw
                        samples.append(frame[roi_mask])
                    else:
                        samples.append(frame.ravel())
            if not samples:
                return None
            sample = np.concatenate(samples)
            if sample.size > 200000:
                # Deterministic sampling for reproducibility (P3.2)
                rng = np.random.default_rng(42)
                idx = rng.choice(sample.size, size=200000, replace=False)
                sample = sample[idx]
            return sample, job_gen, cache_key

        def _on_result(result) -> None:
            if result is None:
                return
            sample, gen, key = result
            if gen != self._job_generation:
                return
            self._hist_cache = sample
            self._hist_cache_key = key
            self._hist_job_id = None
            self._request_render_refresh("histogram-job-finished", debounce=True)

        def _on_error(err: str) -> None:
            self._hist_job_id = None
            self._append_log(f"[JOB] Histogram error\n{err}")

        handle = self.jobs.submit(
            _job,
            name="Histogram sample",
            on_result=_on_result,
            on_error=_on_error,
            priority="interactive",
            replace_key="histogram-sample",
        )
        self._hist_job_id = handle.job_id

    def _norm_cached(self, panel: str, mapping: DisplayMapping):
        key = (
            panel,
            float(mapping.min_val),
            float(mapping.max_val),
            float(mapping.gamma),
            mapping.mode,
        )
        cached = self._norm_cache.get(key)
        if cached is not None:
            return cached
        norm = build_norm(mapping)
        self._norm_cache[key] = norm
        return norm
