"""Extracted method group 3 for RenderingMixin."""

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



class HistogramContrastAutosetMixin:
    """Method group 3 extracted from RenderingMixin."""

    def _refresh_orthoview(self, prim, t_idx: int, z_idx: int, norm, cmap) -> None:
        """Refresh orthoview for the current workflow."""
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
        """Handle the on orthoview xz click helper flow."""
        y = self._cursor_xy[1] if self._cursor_xy is not None else self._default_cursor()[1]
        self._set_cursor_xy(x, y, refresh=False)
        if self.z_slider is not None:
            self.z_slider.setValue(int(z))
    def _on_orthoview_yz_click(self, y: int, z: int) -> None:
        """Handle the on orthoview yz click helper flow."""
        x = self._cursor_xy[0] if self._cursor_xy is not None else self._default_cursor()[0]
        self._set_cursor_xy(x, y, refresh=False)
        if self.z_slider is not None:
            self.z_slider.setValue(int(z))
    def _default_cursor(self) -> Tuple[float, float]:
        """Handle the default cursor helper flow."""
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
        """Return display mapping for the current workflow."""
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
        """Toggle overlay for the current workflow."""
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
        """Handle the hist values helper flow."""
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
