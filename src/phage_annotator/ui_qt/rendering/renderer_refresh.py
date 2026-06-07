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

from matplotlib import colormaps

from phage_annotator.data.display_mapping import build_norm
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, cmap_for
from phage_annotator.ui_qt.rendering.renderer_control_sync import sync_render_controls
from phage_annotator.ui_qt.rendering.renderer_overlay_payload import build_overlay_payload
from phage_annotator.ui_qt.rendering.renderer_panel_frames import (
    collect_panel_frame_bundle,
    panel_projection_key,
    sync_slice_sliders,
)
from phage_annotator.rendering.mpl import RenderContext

class RenderingRefreshMixin:
    """Main image refresh pipeline combining projection, overlays, and display mapping."""

    def _refresh_image(self) -> None:
        """Refresh the image display using current state."""
        if not self.images:
            return
        prim = self.primary_image
        self._ensure_loaded(self.current_image_idx)
        if prim.array is None:
            return
        has_time, has_z = self._effective_axes(prim)
        sync_slice_sliders(self, prim, has_time, has_z)
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
        bundle = collect_panel_frame_bundle(
            self,
            prim,
            visible_order,
            primary_panel,
            panel_specs,
            t_idx,
            z_idx,
        )
        if bundle is None:
            self._update_axes_info()
            self._update_axis_warning()
            self._update_status()
            return
        primary_panel = bundle.primary_panel
        panel_images_raw = bundle.panel_images_raw
        panel_images = bundle.panel_images
        panel_sources = bundle.panel_sources
        panel_projections = bundle.panel_projections
        panel_projection_ready = bundle.panel_projection_ready
        frame_ax = bundle.frame_ax
        level = bundle.level

        vmin, vmax = self._current_vmin_vmax()
        def _panel_title(panel_key: str, fallback: str) -> str:
            """Document the panel_title flow."""
            spec = panel_specs.get(panel_key)
            base = str(getattr(spec, "display_name", fallback) if spec is not None else fallback)
            proj = panel_projection_key(self, panel_key, panel_specs, "raw")
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
            """Document the spec flow."""
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
        overlay_payload = build_overlay_payload(
            self,
            prim,
            primary_panel,
            panel_images,
            frame_ax,
            extents,
        )

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
            localization_points=overlay_payload.localization_points,
            localization_visible=bool(overlay_payload.localization_points),
            threshold_mask=(
                self._threshold_preview_mask if self._threshold_preview_mask is not None else None
            ),
            threshold_extent=self._threshold_preview_extent,
            threshold_visible=bool(self._threshold_preview_mask is not None),
            particle_overlays=self._particles_overlays,
            particle_labels=self._particle_labels(),
            overlay_frame=overlay_payload.overlay_frame,
            overlay_extent=overlay_payload.overlay_extent,
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
            scale_bar=overlay_payload.scale_bar,
            scale_bar_warning=overlay_payload.scale_bar_warning,
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
        sync_render_controls(self, primary_mapping, level)
        self._update_status()
        # Keep evidence-layer config normalized with current session defaults.
        self._refresh_modality_layers_panel()
