"""Rendering pipeline helpers for the GUI.

This module orchestrates the display of microscopy data in matplotlib figures:
- Normalizes data (window/gamma/log transforms)
- Caches projections (mean/composite/standard deviation)
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
from matplotlib import pyplot as plt

from phage_annotator.display_mapping import DisplayMapping, build_norm
from phage_annotator.lut_manager import LUTS, cmap_for
from phage_annotator.render_mpl import RenderContext
from phage_annotator.scalebar import ScaleBarSpec, compute_scalebar


class RenderingMixin:
    """Mixin for image rendering and overlay composition."""

    def _clear_histogram_cache(self) -> None:
        try:
            if self._hist_job_id is not None:
                self.jobs.cancel(self._hist_job_id)
                self._hist_job_id = None
            self._hist_cache = None
            self._hist_cache_key = None
            if hasattr(self, "statusBar"):
                try:
                    self.statusBar().showMessage("Histogram cache cleared.", 2500)
                except Exception:
                    pass
            # Redraw to reflect cleared cache; will recompute on demand
            self._refresh_image()
        except Exception as exc:
            self._append_log(f"[Hist] Clear cache error: {exc}")

    def _refresh_image(self) -> None:
        """Refresh the image display using current state."""
        if not self.images:
            return
        prim = self.primary_image
        supp = self.support_image
        self._ensure_loaded(self.current_image_idx)
        self._ensure_loaded(self.support_image_idx)
        if prim.array is None:
            return
        self._capture_zoom_state()
        t_idx, z_idx = self._slice_indices(prim)
        slice_data = self._slice_data(prim)
        support_slice = self._slice_data(supp) if supp.array is not None else None
        crop_rect = self.crop_rect
        if crop_rect:
            slice_data = self._apply_crop_rect(
                slice_data, crop_rect, (slice_data.shape[0], slice_data.shape[1])
            )
            if support_slice is not None:
                support_slice = self._apply_crop_rect(
                    support_slice,
                    crop_rect,
                    (support_slice.shape[0], support_slice.shape[1]),
                )
        if self._binary_view_enabled and self._binary_view_mask is not None:
            mask = self._binary_view_mask
            if crop_rect:
                mask = self._apply_crop_rect(mask, crop_rect, mask.shape)
            slice_data = mask.astype(np.float32, copy=False)

        mean_data, mean_ready = self._get_projection(prim, "mean")
        std_data, std_ready = self._get_projection(prim, "std")
        comp_data, comp_ready = self._get_projection(prim, "composite")
        if mean_data is None:
            mean_data = np.zeros_like(slice_data)
        if std_data is None:
            std_data = np.zeros_like(slice_data)
        if comp_data is None:
            comp_data = np.zeros_like(slice_data)

        # Interactive downsampling (display-only).
        slice_display = slice_data
        support_display = support_slice
        mean_display = mean_data
        std_display = std_data
        comp_display = comp_data
        level = 0
        if self._interactive:
            level = self._select_pyramid_level(self.ax_frame, slice_data.shape)
            if level > 0:
                scale = 2**level
                self._render_scales = {ax: scale for ax in self.renderer.axes.values()}
                slice_display = self._get_pyramid_display(
                    prim.id,
                    "frame",
                    slice_data,
                    t_idx,
                    z_idx,
                    self.crop_rect or (0, 0, 0, 0),
                    level,
                )
                mean_display = self._get_pyramid_display(
                    prim.id,
                    "mean",
                    mean_data,
                    -1,
                    -1,
                    self.crop_rect or (0, 0, 0, 0),
                    level,
                )
                std_display = self._get_pyramid_display(
                    prim.id,
                    "std",
                    std_data,
                    -1,
                    -1,
                    self.crop_rect or (0, 0, 0, 0),
                    level,
                )
                comp_display = self._get_pyramid_display(
                    prim.id,
                    "composite",
                    comp_data,
                    -1,
                    -1,
                    self.crop_rect or (0, 0, 0, 0),
                    level,
                )
                if support_slice is not None:
                    support_display = self._get_pyramid_display(
                        supp.id,
                        "support",
                        support_slice,
                        t_idx,
                        z_idx,
                        self.crop_rect or (0, 0, 0, 0),
                        level,
                    )
            else:
                self._render_scales = {ax: 1.0 for ax in self.renderer.axes.values()}
        else:
            self._render_scales = {ax: 1.0 for ax in self.renderer.axes.values()}

        vmin, vmax = self._current_vmin_vmax()
        titles = {
            "frame": f"Frame (T={t_idx}, Z={z_idx})",
            "mean": "Mean Projection",
            "composite": "Composite",
            "support": f"Support (T={t_idx}, Z={z_idx})",
            "std": "Std Projection",
        }
        extents = {}
        for key, data in [
            ("frame", slice_display),
            ("mean", mean_display),
            ("composite", comp_display),
            ("support", support_display),
            ("std", std_display),
        ]:
            if data is None:
                continue
            extents[key] = (0, data.shape[1], data.shape[0], 0)
        panel_annotations = self._build_panel_annotations()
        roi_overlays = self._build_roi_overlays()
        overlay_text = self._build_overlay_text()
        roi_spec = self.controller.view_state.roi_spec
        roi_rect = roi_spec.rect
        roi_type = roi_spec.shape
        if roi_type == "none" or roi_rect[2] <= 0 or roi_rect[3] <= 0:
            roi_type = "none"
            roi_rect = None
        roi_scale = self._axis_scale(self.ax_frame) if self.ax_frame is not None else 1.0
        roi_offset = (self.crop_rect[0], self.crop_rect[1]) if self.crop_rect else (0.0, 0.0)
        frame_mapping = self._get_display_mapping(prim.id, "frame", slice_data)
        mean_mapping = self._get_display_mapping(prim.id, "mean", mean_data)
        comp_mapping = self._get_display_mapping(prim.id, "composite", comp_data)
        std_mapping = self._get_display_mapping(prim.id, "std", std_data)
        support_mapping = self._get_display_mapping(supp.id, "support", support_slice)
        std_vmin, std_vmax = std_mapping.min_val, std_mapping.max_val
        if self._playback_mode:
            norms = {
                "frame": self._norm_cached("frame", frame_mapping),
                "mean": self._norm_cached("mean", mean_mapping),
                "composite": self._norm_cached("composite", comp_mapping),
                "support": self._norm_cached("support", support_mapping),
                "std": self._norm_cached("std", std_mapping),
            }
        else:
            norms = {
                "frame": build_norm(frame_mapping),
                "mean": build_norm(mean_mapping),
                "composite": build_norm(comp_mapping),
                "support": build_norm(support_mapping),
                "std": build_norm(std_mapping),
            }

        def _spec(idx: int):
            if idx < 0:
                return LUTS[0]
            if idx >= len(LUTS):
                return LUTS[-1]
            return LUTS[idx]

        panel_cmaps = {
            "frame": cmap_for(_spec(frame_mapping.lut), frame_mapping.invert),
            "mean": cmap_for(_spec(mean_mapping.lut), mean_mapping.invert),
            "composite": cmap_for(_spec(comp_mapping.lut), comp_mapping.invert),
            "support": cmap_for(_spec(support_mapping.lut), support_mapping.invert),
            "std": cmap_for(_spec(std_mapping.lut), std_mapping.invert),
        }
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
        if self.show_smlm_points and self.ax_frame is not None:
            # Validate that results are for the current image
            current_img_id = self.primary_image.id if hasattr(self, 'primary_image') else -1
            smlm_img_id = getattr(self, '_smlm_image_id', None)
            deepstorm_img_id = getattr(self, '_deepstorm_image_id', None)
            
            scale = self._axis_scale(self.ax_frame)
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
        panel_ranges = {
            "frame": (frame_mapping.min_val, frame_mapping.max_val),
            "mean": (mean_mapping.min_val, mean_mapping.max_val),
            "composite": (comp_mapping.min_val, comp_mapping.max_val),
            "support": (support_mapping.min_val, support_mapping.max_val),
            "std": (std_mapping.min_val, std_mapping.max_val),
        }
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
                extent = extents.get("frame") or (
                    0,
                    slice_display.shape[1],
                    slice_display.shape[0],
                    0,
                )
                scale_bar = compute_scalebar(extent, cal.pixel_size_um_per_px, spec)
                if scale_bar is not None:
                    scale_bar["background_box"] = self.scale_bar_background_box
            else:
                scale_bar_warning = "Scale bar requires calibration"

        ctx = RenderContext(
            image_frame=slice_display,
            support_frame=support_display,
            projections={
                "mean": mean_display,
                "std": std_display,
                "composite": comp_display,
            },
            view=self.controller.view_state,
            annotations=self._current_keypoints(),
            panel_visibility=self._panel_visibility,
            titles=titles,
            extents=extents,
            std_range=(std_vmin, std_vmax),
            panel_annotations=panel_annotations,
            roi_overlays=roi_overlays,
            overlay_text=overlay_text,
            marker_size=self.marker_size,
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
                plt.get_cmap(self._density_overlay_cmap)
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
        self.im_frame = self.renderer.image_artists.get("frame")
        self.im_mean = self.renderer.image_artists.get("mean")
        self.im_comp = self.renderer.image_artists.get("composite")
        self.im_support = self.renderer.image_artists.get("support")
        self.im_std = self.renderer.image_artists.get("std")
        self._refresh_orthoview(prim, t_idx, z_idx, norms["frame"], panel_cmaps["frame"])
        if self.ax_mean is not None and not mean_ready:
            self.ax_mean.text(
                0.5,
                0.5,
                "Computing mean...",
                transform=self.ax_mean.transAxes,
                ha="center",
                va="center",
            )
        if self.ax_comp is not None and not comp_ready:
            self.ax_comp.text(
                0.5,
                0.5,
                "Computing composite...",
                transform=self.ax_comp.transAxes,
                ha="center",
                va="center",
            )
        if self.ax_std is not None and not std_ready:
            self.ax_std.text(
                0.5,
                0.5,
                "Computing std...",
                transform=self.ax_std.transAxes,
                ha="center",
                va="center",
            )

        if self.ax_frame is not None:
            self._restore_zoom(slice_display.shape)
        self._draw_diagnostics(slice_data, vmin, vmax)
        self._update_axes_info()
        self._update_axis_warning()
        if self.lut_combo is not None:
            if 0 <= frame_mapping.lut < self.lut_combo.count():
                self.lut_combo.blockSignals(True)
                self.lut_combo.setCurrentIndex(frame_mapping.lut)
                self.lut_combo.blockSignals(False)
        if self.lut_invert_chk is not None:
            invert_supported = True
            if 0 <= frame_mapping.lut < len(LUTS):
                invert_supported = LUTS[frame_mapping.lut].invert_supported
            self.lut_invert_chk.blockSignals(True)
            self.lut_invert_chk.setChecked(frame_mapping.invert)
            self.lut_invert_chk.setEnabled(invert_supported)
            self.lut_invert_chk.blockSignals(False)
        if self.gamma_slider is not None and self.gamma_label is not None:
            gamma_val = max(0.2, min(5.0, float(frame_mapping.gamma)))
            self.gamma_slider.blockSignals(True)
            self.gamma_slider.setValue(int(round(gamma_val * 10)))
            self.gamma_slider.blockSignals(False)
            self.gamma_label.setText(f"{gamma_val:.2f}")
        if self.log_chk is not None:
            self.log_chk.blockSignals(True)
            self.log_chk.setChecked(frame_mapping.mode == "log")
            self.log_chk.blockSignals(False)
        if self.render_level_label is not None:
            self.render_level_label.setText(f"Render: L{level}")
        self._update_status()

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
            self._refresh_image()

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

    def _particle_labels(self) -> List[Tuple[float, float, str]]:
        if self.particles_panel is None:
            return []
        if not self.particles_panel.show_labels_chk.isChecked():
            return []
        scale = self._axis_scale(self.ax_frame)
        labels: List[Tuple[float, float, str]] = []
        for idx, particle in enumerate(self._particles_results):
            x = (particle.centroid_x - (self.crop_rect[0] if self.crop_rect else 0.0)) / scale
            y = (particle.centroid_y - (self.crop_rect[1] if self.crop_rect else 0.0)) / scale
            labels.append((x, y, str(idx + 1)))
        return labels

    def _build_panel_annotations(
        self,
    ) -> Dict[str, List[Tuple[float, float, str, bool]]]:
        points = []
        for kp in self._current_keypoints():
            color = self._label_color(kp.label, faded=kp.image_id != self.primary_image.id)
            selected = kp in self._table_rows
            points.append((kp.x, kp.y, color, selected))

        def _filter(panel: str) -> List[Tuple[float, float, str, bool]]:
            if panel == "frame":
                return points if self.show_ann_frame else []
            if panel == "mean":
                return points if self.show_ann_mean else []
            if panel == "composite":
                return points if self.show_ann_comp else []
            if panel == "support":
                return points
            return []

        panel_annotations: Dict[str, List[Tuple[float, float, str, bool]]] = {}
        for panel in ["frame", "mean", "composite", "support"]:
            pts = _filter(panel)
            if not pts:
                panel_annotations[panel] = []
                continue
            scale = self._axis_scale(getattr(self, f"ax_{panel}") or self.ax_frame)
            panel_annotations[panel] = [(x / scale, y / scale, c, s) for x, y, c, s in pts]
        return panel_annotations

    def _build_roi_overlays(self) -> Dict[str, List[Tuple[str, object, str]]]:
        overlays: Dict[str, List[Tuple[str, object, str]]] = {
            panel: [] for panel in ["frame", "mean", "composite", "support"]
        }
        for roi in self.roi_manager.list_rois(self.primary_image.id):
            if not roi.visible:
                continue
            for panel in overlays:
                ax = getattr(self, f"ax_{panel}") or self.ax_frame
                scale = self._axis_scale(ax)
                if roi.roi_type == "circle" and len(roi.points) >= 2:
                    (cx, cy), (px, py) = roi.points[:2]
                    r = float(np.hypot(px - cx, py - cy))
                    rect = (cx - r, cy - r, 2 * r, 2 * r)
                    overlays[panel].append(
                        (
                            "circle",
                            (
                                rect[0] / scale,
                                rect[1] / scale,
                                rect[2] / scale,
                                rect[3] / scale,
                            ),
                            roi.color,
                        )
                    )
                elif roi.roi_type == "box" and len(roi.points) >= 2:
                    (x0, y0), (x1, y1) = roi.points[:2]
                    rect = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
                    overlays[panel].append(
                        (
                            "box",
                            (
                                rect[0] / scale,
                                rect[1] / scale,
                                rect[2] / scale,
                                rect[3] / scale,
                            ),
                            roi.color,
                        )
                    )
                elif roi.roi_type in ("polygon", "polyline") and len(roi.points) >= 3:
                    pts = [(x / scale, y / scale) for x, y in roi.points]
                    overlays[panel].append((roi.roi_type, pts, roi.color))
        if self.crop_rect:
            for panel in overlays:
                ax = getattr(self, f"ax_{panel}") or self.ax_frame
                scale = self._axis_scale(ax)
                x, y, w, h = self.crop_rect
                overlays[panel].append(
                    ("box", (x / scale, y / scale, w / scale, h / scale), "#00c0ff")
                )
        return overlays

    def _build_overlay_text(self) -> Optional[str]:
        if not self.overlay_enabled:
            return None
        img = self.primary_image
        t_idx, z_idx = self._slice_indices(img)
        t_total = img.array.shape[0] if img.array is not None else 1
        z_total = img.array.shape[1] if img.array is not None else 1
        mapping = self._get_display_mapping(img.id, "frame", img.array)
        idx = mapping.lut
        if idx < 0:
            idx = 0
        if idx >= len(LUTS):
            idx = len(LUTS) - 1
        lut = LUTS[idx].name
        inv = " (inv)" if mapping.invert else ""
        vmin = f"{mapping.min_val:.3f}"
        vmax = f"{mapping.max_val:.3f}"
        gamma = f"{mapping.gamma:.2f}"
        mode = mapping.mode
        crop_txt = "yes" if self.crop_rect else "no"
        roi_active = (
            self.roi_shape != "none"
            and self.roi_rect
            and self.roi_rect[2] > 0
            and self.roi_rect[3] > 0
        )
        roi_txt = "yes" if roi_active else "no"
        crop_rect = self.crop_rect if self.crop_rect else (0, 0, 0, 0)
        roi_rect = self.roi_rect if roi_active else (0, 0, 0, 0)
        cal = self._get_calibration_state(img.id)
        pixel_size = (
            f"{cal.pixel_size_um_per_px:.4f} um/px" if cal.pixel_size_um_per_px else "unknown"
        )
        return (
            f"{img.name}\n"
            f"T {t_idx + 1}/{t_total} | Z {z_idx + 1}/{z_total}\n"
            f"Pixel size: {pixel_size}\n"
            f"LUT: {lut}{inv} | Mode: {mode} | Gamma: {gamma}\n"
            f"vmin/vmax: {vmin}/{vmax}\n"
            f"Crop: {crop_txt} {crop_rect}\n"
            f"ROI: {roi_txt} {roi_rect}\n"
            f"Memmap: {'yes' if getattr(img.array, 'filename', None) else 'no'}"
        )

    def _get_display_mapping(
        self, image_id: int, panel: str, data: Optional[np.ndarray]
    ) -> DisplayMapping:
        created = image_id not in self.controller.display_mapping.per_image
        mapping = self.controller.display_mapping.mapping_for(image_id, panel)
        if data is not None and (created or mapping.min_val == mapping.max_val):
            mapping.reset_to_auto(data)
        return mapping

    def _toggle_overlay(self, checked: bool) -> None:
        self.overlay_enabled = checked
        self._refresh_image()

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

        hist_visible = self.dock_hist is None or self.dock_hist.isVisible()
        if (
            self.hist_enabled
            and self.hist_chk.isChecked()
            and hist_visible
            and self.ax_hist is not None
        ):
            if self._playback_mode and (time.monotonic() - self._hist_last_time) < 0.5:
                return
            self._hist_last_time = time.monotonic()
            vals = self._hist_values(slice_data)
            if vals is None:
                return
            bins = self.hist_bins_spin.value()
            self.ax_hist.clear()
            counts, edges = np.histogram(vals, bins=bins)
            centers = 0.5 * (edges[:-1] + edges[1:])
            self.ax_hist.plot(centers, counts, color="#5555aa")
            self.ax_hist.axvline(vmin, color="#ff8800", linestyle="--", linewidth=1)
            self.ax_hist.axvline(vmax, color="#ff8800", linestyle="--", linewidth=1)
            self.ax_hist.set_title("Intensity histogram")
            self.ax_hist.set_xlabel("Intensity")
            self.ax_hist.set_ylabel("Count")
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
                self.ax_hist.text(
                    0.02,
                    0.95,
                    stats,
                    transform=self.ax_hist.transAxes,
                    va="top",
                    fontsize=8,
                )
            self.ax_hist.axis("on")
        else:
            if self.ax_hist is not None:
                self.ax_hist.clear()
                self.ax_hist.axis("off")
        if self.hist_canvas is not None:
            self.hist_canvas.draw_idle()

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
                        if roi_mask is None or roi_mask_shape != frame.shape:
                            h, w = frame.shape
                            y = np.arange(h)[:, None]
                            x = np.arange(w)[None, :]
                            rx, ry, rw, rh = roi_rect
                            if roi_shape == "circle":
                                cx, cy = rx + rw / 2, ry + rh / 2
                                r = min(rw, rh) / 2
                                roi_mask = (x - cx) ** 2 + (y - cy) ** 2 <= r**2
                            else:
                                roi_mask = (rx <= x) & (x <= rx + rw) & (ry <= y) & (y <= ry + rh)
                            roi_mask_shape = frame.shape
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
            self._refresh_image()

        def _on_error(err: str) -> None:
            self._hist_job_id = None
            self._append_log(f"[JOB] Histogram error\n{err}")

        handle = self.jobs.submit(
            _job, name="Histogram sample", on_result=_on_result, on_error=_on_error
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
