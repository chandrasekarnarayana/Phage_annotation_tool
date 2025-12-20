"""State proxy and image helpers for the GUI.

This module provides a mixin that centralizes access to session state via properties,
simplifying GUI logic by abstracting controller calls. It also contains image loading
and coordinate transformation utilities that bridge full-resolution and displayed data.

Coordinate Conventions
----------------------
- Full-resolution: (y, x) in the original numpy array, 0-indexed
- Display/crop: (y, x) after cropping but before downsampling
- Downsampled: After pyramid downsampling; scale factor depends on level
- Canvas (matplotlib): (x, y) with potential axis inversions

All transforms are designed to be bijective; roundtrip errors <0.1 pixel expected.

Key State Proxies
-----------------
- images: List of LazyImage objects (metadata + lazy-loaded arrays)
- annotations: Dict[image_id] -> List[Keypoint] (observed keypoints)
- axis_mode: Dict[image_id] -> "time" | "depth" (3D axis interpretation)
- display_mapping: Per-image, per-panel brightness/contrast/LUT settings

Thread Safety
-------------
- All state proxies delegate to SessionController (main thread)
- Image array loading may occur in background (read_contiguous_block)
- Projection caching is thread-aware via CancelTokenShim
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from matplotlib.backends.qt_compat import QtCore

from phage_annotator.analysis import compute_mean_std
from phage_annotator.annotations import Keypoint
from phage_annotator.calibration import CalibrationState
from phage_annotator.gui_constants import PROJECTION_ASYNC_BYTES, CancelTokenShim
from phage_annotator.gui_debug import debug_log
from phage_annotator.gui_image_io import load_array
from phage_annotator.io import read_contiguous_block
from phage_annotator.pyramid import downsample_mean_pool, pyramid_level_factor

if TYPE_CHECKING:
    from phage_annotator.image_models import LazyImage


class StateMixin:
    """Mixin for state proxies and image helper utilities."""

    # --- State proxies (SessionController owns state) -------------------
    @property
    def images(self) -> List["LazyImage"]:
        return self.controller.session_state.images

    @images.setter
    def images(self, value: List["LazyImage"]) -> None:
        self.controller.set_images(value)

    @property
    def labels(self) -> List[str]:
        return self.controller.session_state.labels

    @property
    def current_label(self) -> str:
        return self.controller.session_state.current_label

    @current_label.setter
    def current_label(self, label: str) -> None:
        self.controller.set_current_label(label)

    @property
    def annotations(self) -> Dict[int, List[Keypoint]]:
        return self.controller.session_state.annotations

    @property
    def axis_mode(self) -> Dict[int, str]:
        return {k: v.axis_mode for k, v in self.controller.session_state.image_states.items()}

    @property
    def current_image_idx(self) -> int:
        return self.controller.session_state.active_primary_id

    @current_image_idx.setter
    def current_image_idx(self, value: int) -> None:
        self.controller.set_primary(value)

    @property
    def support_image_idx(self) -> int:
        return self.controller.session_state.active_support_id

    @support_image_idx.setter
    def support_image_idx(self, value: int) -> None:
        self.controller.set_support(value)

    @property
    def current_cmap_idx(self) -> int:
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        return mapping.lut

    @current_cmap_idx.setter
    def current_cmap_idx(self, value: int) -> None:
        self.controller.set_lut(value)

    @property
    def _last_vmin(self) -> float:
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        return mapping.min_val

    @_last_vmin.setter
    def _last_vmin(self, value: float) -> None:
        self.controller.set_display_mapping(value, self._last_vmax)

    @property
    def _last_vmax(self) -> float:
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        return mapping.max_val

    @_last_vmax.setter
    def _last_vmax(self, value: float) -> None:
        self.controller.set_display_mapping(self._last_vmin, value)

    @property
    def play_mode(self) -> Optional[str]:
        return self.controller.view_state.play_mode

    @play_mode.setter
    def play_mode(self, value: Optional[str]) -> None:
        if value is None:
            self.controller.stop_playback()
        else:
            self.controller.start_playback(value)

    @property
    def loop_playback(self) -> bool:
        return self.controller.view_state.loop_playback

    @loop_playback.setter
    def loop_playback(self, value: bool) -> None:
        self.controller.set_loop(value)

    @property
    def profile_line(self) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        return self.controller.view_state.profile_line

    @profile_line.setter
    def profile_line(
        self, value: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> None:
        self.controller.set_profile_line(value)

    @property
    def profile_enabled(self) -> bool:
        return self.controller.view_state.profile_enabled

    @profile_enabled.setter
    def profile_enabled(self, value: bool) -> None:
        self.controller.set_profile_enabled(value)

    @property
    def hist_enabled(self) -> bool:
        return self.controller.view_state.hist_enabled

    @hist_enabled.setter
    def hist_enabled(self, value: bool) -> None:
        self.controller.set_hist_enabled(value)

    @property
    def hist_bins(self) -> int:
        return self.controller.view_state.hist_bins

    @hist_bins.setter
    def hist_bins(self, value: int) -> None:
        self.controller.set_hist_bins(value)

    @property
    def hist_region(self) -> str:
        return self.controller.view_state.hist_region

    @hist_region.setter
    def hist_region(self, value: str) -> None:
        self.controller.set_hist_region(value)

    @property
    def link_zoom(self) -> bool:
        return self.controller.view_state.linked_zoom

    @link_zoom.setter
    def link_zoom(self, value: bool) -> None:
        self.controller.set_link_zoom(value)

    @property
    def roi_shape(self) -> str:
        return self.controller.view_state.roi_spec.shape

    @roi_shape.setter
    def roi_shape(self, value: str) -> None:
        self.controller.set_roi(self.roi_rect, shape=value)

    @property
    def roi_rect(self) -> Tuple[float, float, float, float]:
        return self.controller.view_state.roi_spec.rect

    @roi_rect.setter
    def roi_rect(self, value: Tuple[float, float, float, float]) -> None:
        self.controller.set_roi(value, shape=self.roi_shape)

    @property
    def crop_rect(self) -> Optional[Tuple[float, float, float, float]]:
        return self.controller.view_state.crop_rect

    @crop_rect.setter
    def crop_rect(self, value: Optional[Tuple[float, float, float, float]]) -> None:
        self.controller.set_crop(value)

    @property
    def annotate_target(self) -> str:
        return self.controller.view_state.annotate_target

    @annotate_target.setter
    def annotate_target(self, value: str) -> None:
        self.controller.set_annotate_target(value)

    @property
    def annotation_scope(self) -> str:
        return self.controller.view_state.annotation_scope

    @annotation_scope.setter
    def annotation_scope(self, value: str) -> None:
        self.controller.set_annotation_scope(value)

    @property
    def show_ann_frame(self) -> bool:
        return self.controller.view_state.show_ann_frame

    @show_ann_frame.setter
    def show_ann_frame(self, value: bool) -> None:
        self.controller.set_show_annotations(value, self.show_ann_mean, self.show_ann_comp)

    @property
    def show_ann_mean(self) -> bool:
        return self.controller.view_state.show_ann_mean

    @show_ann_mean.setter
    def show_ann_mean(self, value: bool) -> None:
        self.controller.set_show_annotations(self.show_ann_frame, value, self.show_ann_comp)

    @property
    def show_ann_comp(self) -> bool:
        return self.controller.view_state.show_ann_comp

    @show_ann_comp.setter
    def show_ann_comp(self, value: bool) -> None:
        self.controller.set_show_annotations(self.show_ann_frame, self.show_ann_mean, value)

    @property
    def _annotations_dirty(self) -> bool:
        return self.controller.session_state.dirty

    @_annotations_dirty.setter
    def _annotations_dirty(self, value: bool) -> None:
        self.controller.set_dirty(value)

    @property
    def _project_path(self) -> Optional[pathlib.Path]:
        return self.controller.session_state.project_path

    @_project_path.setter
    def _project_path(self, value: Optional[pathlib.Path]) -> None:
        self.controller.set_project_path(value)

    @property
    def _project_save_time(self) -> Optional[float]:
        return self.controller.session_state.project_save_time

    @property
    def overlay_enabled(self) -> bool:
        return self.controller.view_state.overlay_enabled

    @overlay_enabled.setter
    def overlay_enabled(self, value: bool) -> None:
        self.controller.set_overlay_enabled(value)

    @property
    def _last_folder(self) -> Optional[pathlib.Path]:
        return self.controller.session_state.last_folder

    @_last_folder.setter
    def _last_folder(self, value: Optional[pathlib.Path]) -> None:
        self.controller.set_last_folder(value)

    @_project_save_time.setter
    def _project_save_time(self, value: Optional[float]) -> None:
        self.controller.set_project_save_time(value)

    @property
    def primary_image(self) -> "LazyImage":
        return self.images[self.current_image_idx]

    @property
    def support_image(self) -> "LazyImage":
        return self.images[self.support_image_idx]

    def _ensure_loaded(self, idx: int) -> None:
        """Load a stack lazily into memory and evict non-active images."""
        img = self.images[idx]
        if img.array is None:
            arr, has_time, has_z = load_array(
                img.path, interpret_3d_as=img.interpret_3d_as, ome_axes=img.ome_axes
            )
            img.array = arr
            img.has_time = has_time
            img.has_z = has_z
            img.mean_proj = None
            img.std_proj = None
            if img.ome_axes is None and img.interpret_3d_as == "auto" and len(img.shape) == 3:
                axis0 = img.shape[0]
                img.axis_auto_used = True
                img.axis_auto_mode = "time" if axis0 <= 5 else "depth"
            else:
                img.axis_auto_used = False
                img.axis_auto_mode = None
            self.controller.refresh_image_state(img)
            debug_log(f"Loaded image {img.name} (id={img.id})")
        # Drop others to save memory (keep primary and support)
        for j, other in enumerate(self.images):
            if j not in (self.current_image_idx, self.support_image_idx):
                self._evict_image_cache(other)

    def _evict_image_cache(self, img: "LazyImage") -> None:
        """Remove array and projection caches for an image to free memory."""
        if img.array is not None or img.mean_proj is not None or img.std_proj is not None:
            debug_log(f"Evicting cache for {img.name} (id={img.id})")
        self._cancel_projection_jobs(img.id)
        for key in list(self._pyramid_jobs.keys()):
            if key[0] == img.id:
                self._pyramid_jobs.pop(key, None)
        self.proj_cache.invalidate_image(img.id)
        img.array = None
        img.mean_proj = None
        img.std_proj = None

    def _effective_axes(self, img: "LazyImage") -> Tuple[bool, bool]:
        mode = img.interpret_3d_as
        if mode == "time":
            return True, img.has_z
        if mode == "depth":
            return False, True
        return img.has_time, img.has_z

    def _slice_indices(self, img: "LazyImage") -> Tuple[int, int]:
        has_time, has_z = self._effective_axes(img)
        t_idx = self.t_slider.value() if has_time else 0
        z_idx = self.z_slider.value() if has_z else 0
        if not has_time and has_z:
            z_idx = self.t_slider.value()
            t_idx = 0
        if img.array is not None:
            t_idx = max(0, min(t_idx, img.array.shape[0] - 1))
            z_idx = max(0, min(z_idx, img.array.shape[1] - 1))
        return t_idx, z_idx

    def _slice_data(
        self,
        img: "LazyImage",
        t_override: Optional[int] = None,
        z_override: Optional[int] = None,
    ) -> np.ndarray:
        """Extract a single (Y, X) frame from image array at given T and Z indices.

        Parameters
        ----------
        img : LazyImage
            Image with (T, Z, Y, X) shaped array.
        t_override : Optional[int]
            If provided, use this T index instead of self.t_slider. Clamped to valid range.
        z_override : Optional[int]
            If provided, use this Z index instead of self.z_slider. Clamped to valid range.

        Returns
        -------
        np.ndarray
            2D array of shape (Y, X) for the selected frame.
        """
        t_idx, z_idx = self._slice_indices(img)
        if t_override is not None:
            t_idx = max(
                0,
                (t_override if img.array is None else min(t_override, img.array.shape[0] - 1)),
            )
        if z_override is not None:
            z_idx = max(
                0,
                (z_override if img.array is None else min(z_override, img.array.shape[1] - 1)),
            )
        assert img.array is not None
        return img.array[t_idx, z_idx, :, :]

    def _get_calibration_state(self, image_id: int) -> CalibrationState:
        project_default = self._settings.value("defaultPixelSizeUmPerPx", None, type=float)
        user_value = self.pixel_size_um_per_px if self.pixel_size_um_per_px else None
        return self.controller.resolve_calibration_state(image_id, user_value, project_default)

    def _projection_key(
        self, img: "LazyImage", kind: str
    ) -> Tuple[int, str, Tuple[float, float, float, float], int, int]:
        crop_rect = self._cache_crop_rect(img)
        # Projections are global over T/Z; keep selection fields for key shape.
        t_sel, z_sel = -1, -1
        return (img.id, kind, crop_rect, t_sel, z_sel)

    def _cache_crop_rect(self, img: "LazyImage") -> Tuple[float, float, float, float]:
        """Return the crop rect normalized for cache keys."""
        crop_rect = self.crop_rect or (0.0, 0.0, 0.0, 0.0)
        if img.array is not None:
            full_h, full_w = img.array.shape[2], img.array.shape[3]
        else:
            full_h, full_w = img.shape[-2], img.shape[-1]
        x, y, w, h = crop_rect
        if w <= 0 or h <= 0:
            return (0.0, 0.0, 0.0, 0.0)
        if x <= 0 and y <= 0 and w >= full_w and h >= full_h:
            return (0.0, 0.0, 0.0, 0.0)
        return crop_rect

    def _apply_crop_rect(
        self,
        data: np.ndarray,
        crop_rect: Tuple[float, float, float, float],
        full_shape: Tuple[int, int],
    ) -> np.ndarray:
        """Apply a crop rect (X, Y, W, H) to a 2D array."""
        x, y, w, h = crop_rect
        full_h, full_w = full_shape
        if w <= 0 or h <= 0:
            return data
        if x <= 0 and y <= 0 and w >= full_w and h >= full_h:
            return data
        x0 = int(max(0, x))
        y0 = int(max(0, y))
        x1 = int(min(full_w, x + w))
        y1 = int(min(full_h, y + h))
        return data[y0:y1, x0:x1]

    def _downsample(self, data: np.ndarray, factor: int) -> np.ndarray:
        """Downsample a 2D array by integer stride for interactive mode."""
        if factor <= 1:
            return data
        return data[::factor, ::factor]

    def _axis_scale(self, ax) -> float:
        return float(self._render_scales.get(ax, 1.0))

    def _to_display_coords(self, ax, x: float, y: float) -> Tuple[float, float]:
        scale = self._axis_scale(ax)
        return x / scale, y / scale

    def _to_full_coords(self, ax, x: float, y: float) -> Tuple[float, float]:
        scale = self._axis_scale(ax)
        return x * scale, y * scale

    def _select_pyramid_level(self, ax, data_shape: Tuple[int, int]) -> int:
        """Choose a pyramid level based on zoom and interaction state."""
        if not self.pyramid_enabled or not self._interactive:
            return 0
        if ax is None:
            return 0
        try:
            bbox = ax.get_window_extent().width
        except Exception:
            return 0
        xlim = ax.get_xlim()
        span = abs(xlim[1] - xlim[0]) if xlim else data_shape[1]
        if span <= 0:
            span = data_shape[1]
        pixels_per_image_px = bbox / max(1.0, span)
        # Hysteresis to avoid flicker: keep current level until zoom changes meaningfully.
        thresholds = {1: 1.0, 2: 0.5, 3: 0.25}
        hysteresis = 0.15
        target = 0
        for level in range(self.pyramid_max_levels, 0, -1):
            if pixels_per_image_px < thresholds.get(level, 0.25):
                target = level
                break
        if self._last_render_level > 0:
            last_thr = thresholds.get(self._last_render_level, 0.25)
            if pixels_per_image_px < last_thr * (1 + hysteresis):
                target = max(target, self._last_render_level)
        self._last_render_level = target
        return target

    def _get_pyramid_display(
        self,
        img_id: int,
        kind: str,
        data: np.ndarray,
        t_idx: int,
        z_idx: int,
        crop_rect: Tuple[float, float, float, float],
        level: int,
    ) -> np.ndarray:
        if level <= 0 or not self.pyramid_enabled:
            return data
        key = (img_id, kind, t_idx, z_idx, crop_rect, level)
        cached = self.proj_cache.get_pyramid(key)
        if cached is not None:
            return cached
        if key not in self._pyramid_jobs and not self._playback_mode:
            job_name = f"Pyramid:{img_id}:{kind}:{t_idx}:{z_idx}:{level}"
            self._pyramid_jobs[key] = job_name
            generation = self._job_generation
            scale = pyramid_level_factor(level)
            data_view = data

            def _job(progress, cancel_token):
                if cancel_token.is_cancelled():
                    return None
                result = downsample_mean_pool(data_view, scale)
                return (key, result, generation)

            def _on_result(result) -> None:
                if result is None:
                    return
                key_result, arr, gen = result
                if gen != self._job_generation:
                    self._pyramid_jobs.pop(key_result, None)
                    return
                self.proj_cache.put_pyramid(key_result, arr)
                self._pyramid_jobs.pop(key_result, None)
                self._refresh_image()

            def _on_error(err: str) -> None:
                self._pyramid_jobs.pop(key, None)
                self._append_log(f"[JOB] Pyramid error\n{err}")

            self.jobs.submit(_job, name=job_name, on_result=_on_result, on_error=_on_error)
        # Fallback: fast subsample while pyramid builds.
        scale = pyramid_level_factor(level)
        return self._downsample(data, scale)

    def _get_projection(self, img: "LazyImage", kind: str) -> Tuple[Optional[np.ndarray], bool]:
        """Return a cached projection or schedule computation."""
        key = self._projection_key(img, kind)
        cached = self.proj_cache.get(key)
        if cached is not None:
            return cached, True
        if kind == "composite":
            mean_key = self._projection_key(img, "mean")
            mean_cached = self.proj_cache.get(mean_key)
            if mean_cached is not None:
                self.proj_cache.put(key, mean_cached)
                return mean_cached, True
        self._request_projection_job(img)
        return None, False

    def _request_projection_job(self, img: "LazyImage") -> None:
        """Schedule projection computation and populate the cache on completion."""
        if self._playback_mode:
            return
        crop_rect = self.crop_rect or (0.0, 0.0, 0.0, 0.0)
        t_sel, z_sel = -1, -1
        key_mean = (img.id, "mean", crop_rect, t_sel, z_sel)
        key_std = (img.id, "std", crop_rect, t_sel, z_sel)
        key_comp = (img.id, "composite", crop_rect, t_sel, z_sel)
        if (
            key_mean in self._projection_jobs
            or key_std in self._projection_jobs
            or key_comp in self._projection_jobs
        ):
            return
        if img.array is None:
            self._ensure_loaded(img.id)
        if img.array is None:
            return
        generation = self._job_generation
        arr = img.array
        job_name = f"Projections:{img.id}"
        full_shape = (arr.shape[2], arr.shape[3])

        def _job(progress, cancel_token):
            if cancel_token.is_cancelled():
                return None
            if arr.nbytes >= PROJECTION_ASYNC_BYTES:
                progress(5, "Computing projections")
            mean_proj, std_proj = compute_mean_std(arr)
            if cancel_token.is_cancelled():
                return None
            mean_proj = self._apply_crop_rect(mean_proj, crop_rect, full_shape)
            std_proj = self._apply_crop_rect(std_proj, crop_rect, full_shape)
            progress(100, "Done")
            return (mean_proj, std_proj, img.id, generation, crop_rect, t_sel, z_sel)

        job_id_holder = {"id": None}

        def _on_result(result):
            if result is None:
                return
            mean_proj, std_proj, image_id, gen, crop_key, t_key, z_key = result
            if gen != self._job_generation:
                return
            if image_id < 0 or image_id >= len(self.images):
                return
            key_base = (image_id, "mean", crop_key, t_key, z_key)
            key_std_local = (image_id, "std", crop_key, t_key, z_key)
            key_comp_local = (image_id, "composite", crop_key, t_key, z_key)
            self.proj_cache.put(key_base, mean_proj)
            self.proj_cache.put(key_std_local, std_proj)
            self.proj_cache.put(key_comp_local, mean_proj)
            if job_id_holder["id"] is not None:
                self._clear_projection_job_name(job_id_holder["id"])
            self._refresh_image()

        def _on_error(err: str) -> None:
            if job_id_holder["id"] is not None:
                self._clear_projection_job_name(job_id_holder["id"])
            self._append_log(f"[JOB] Projection error for {img.name}\n{err}")
            if self.dock_logs is not None:
                self.dock_logs.setVisible(True)

        if arr.nbytes >= PROJECTION_ASYNC_BYTES:
            handle = self.jobs.submit(_job, name=job_name, on_result=_on_result, on_error=_on_error)
            job_id_holder["id"] = handle.job_id
            self._projection_jobs[key_mean] = handle.job_id
            self._projection_jobs[key_std] = handle.job_id
            self._projection_jobs[key_comp] = handle.job_id
        else:
            try:
                result = _job(lambda _v, _m="": None, CancelTokenShim())
            except Exception as exc:
                _on_error(str(exc))
                return
            _on_result(result)

    def _update_image_artist(
        self,
        artist,
        data: np.ndarray,
        cmap: str,
        vmin: float,
        vmax: float,
        extent: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        artist.set_data(data)
        artist.set_cmap(cmap)
        artist.set_clim(vmin, vmax)
        if extent is None:
            extent = (0, data.shape[1], data.shape[0], 0)
        artist.set_extent(extent)

    def _clear_image_overlays(self) -> None:
        if not self.renderer.axes:
            return
        for ax in self.renderer.axes.values():
            for artist in list(ax.patches):
                artist.remove()
            for artist in list(ax.lines):
                artist.remove()
            for artist in list(ax.texts):
                artist.remove()
            for artist in list(ax.collections):
                if artist in self.renderer.image_artists.values():
                    continue
                artist.remove()

    def _read_playback_block(self, t_start: int, t_stop: int, z_idx: int) -> np.ndarray:
        """Read a contiguous block of frames for playback prefetching."""
        prim = self.primary_image
        if prim.array is None:
            return np.empty((0, 0, 0), dtype=np.float32)
        block = read_contiguous_block(prim.array, t_start, t_stop, z_idx)
        if self.crop_rect is None:
            return block
        x, y, w, h = self.crop_rect
        if w <= 0 or h <= 0:
            return block
        full_h, full_w = block.shape[1], block.shape[2]
        if x <= 0 and y <= 0 and w >= full_w and h >= full_h:
            return block
        x0 = int(max(0, x))
        y0 = int(max(0, y))
        x1 = int(min(full_w, x + w))
        y1 = int(min(full_h, y + h))
        return block[:, y0:y1, x0:x1]

    def _update_buffer_stats(self) -> None:
        """Update playback buffer stats in the status bar."""
        if self.buffer_stats_label is None:
            return
        stats = self._playback_ring.stats()
        block_size = int(self._settings.value("prefetchBlockSizeFrames", 64, type=int))
        self.buffer_stats_label.setText(
            f"Buffer: {stats.filled}/{stats.capacity} | Prefetch: {block_size} | Underruns: {self._playback_underruns}"
        )

    def _flash_status(self, text: str, ms: int = 1200) -> None:
        """Show a temporary status message without overwriting the base status."""
        self._set_status(text)
        QtCore.QTimer.singleShot(ms, lambda: self._set_status(""))
