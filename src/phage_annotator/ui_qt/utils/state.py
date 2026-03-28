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
from types import MappingProxyType
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from matplotlib.backends.qt_compat import QtCore

from phage_annotator.analysis.core import compute_projection, compute_projections
from phage_annotator.annotation.core import Keypoint, PointSuggestion
from phage_annotator.io.data.calibration import CalibrationState
from phage_annotator.ui_qt.utils.constants import PROJECTION_ASYNC_BYTES, CancelTokenShim
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import load_array
from phage_annotator.io import read_contiguous_block
from phage_annotator.data.pyramid import downsample_mean_pool, pyramid_level_factor

if TYPE_CHECKING:
    from phage_annotator.data.models import LazyImage


class StateMixin:
    """Mixin for state proxies and image helper utilities."""

    # --- State proxies (SessionController owns state) -------------------
    @property
    def images(self) -> List["LazyImage"]:
        return list(self.controller.session_state.images)

    @images.setter
    def images(self, value: List["LazyImage"]) -> None:
        self.controller.set_images(value)

    @property
    def labels(self) -> List[str]:
        return list(self.controller.session_state.labels)

    @property
    def current_label(self) -> str:
        return self.controller.session_state.current_label

    @current_label.setter
    def current_label(self, label: str) -> None:
        self.controller.set_current_label(label)

    @property
    def annotations(self) -> Dict[int, List[Keypoint]]:
        return MappingProxyType(
            {int(k): tuple(v) for k, v in self.controller.session_state.annotations.items()}
        )

    @property
    def suggestions(self) -> Dict[int, List[PointSuggestion]]:
        return MappingProxyType(
            {int(k): tuple(v) for k, v in self.controller.session_state.suggestions.items()}
        )

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
        self.controller.set_show_annotations(value, self.show_ann_mean)

    @property
    def show_ann_mean(self) -> bool:
        return self.controller.view_state.show_ann_mean

    @show_ann_mean.setter
    def show_ann_mean(self, value: bool) -> None:
        self.controller.set_show_annotations(self.show_ann_frame, value)

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
        """Load a stack lazily into memory and evict non-active images.
        
        Detects memory pressure during load and tracks downsampling diagnostics
        for user feedback in the renderer.
        """
        img = self.images[idx]
        if img.array is None:
            arr, has_time, has_z = load_array(
                img.path,
                interpret_3d_as=img.interpret_3d_as,
                ome_axes=img.ome_axes,
                channel_idx=getattr(img, "channel_idx", 0),
            )
            img.array = arr
            img.has_time = has_time
            img.has_z = has_z
            img.mean_proj = None
            img.std_proj = None
            
            # Extract and track downsampling diagnostics
            if hasattr(arr, "_diagnostics"):
                diagnostics = arr._diagnostics
                img.downsampled = diagnostics.get("downsampled", False)
                img.downsampling_reason = diagnostics.get("downsampling_reason", None)
                img.downsample_factor = diagnostics.get("downsample_factor", 1)
                if img.downsampled:
                    debug_log(f"[Memory] {img.downsampling_reason}")
                    # Flag memory pressure state for UI indicators
                    if not hasattr(self, "_image_memory_pressure"):
                        self._image_memory_pressure = {}
                    self._image_memory_pressure[img.id] = True
            
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
        channel_cache = getattr(img, "_channel_stack_cache", None)
        if isinstance(channel_cache, dict):
            channel_cache.clear()

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
        
        Returns a zero-copy view for memory efficiency. The returned array
        should not be modified; use .copy() if mutation is needed downstream.

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
            2D array view of shape (Y, X) for the selected frame. Zero-copy view that
            shares memory with the source image stack.
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
        self,
        img: "LazyImage",
        kind: str,
        axis: str = "tz",
        modality_idx: Optional[int] = None,
    ) -> Tuple[int, str, Tuple[float, float, float, float], int, int, int]:
        crop_rect = self._cache_crop_rect(img)
        if axis != "tz":
            kind = f"{kind}:{axis}"
        # Projections are global over T/Z; keep selection fields for key shape.
        t_sel, z_sel = -1, -1
        if modality_idx is None:
            modality_idx = self._modality_idx_for_image(img.id)
        return (img.id, kind, crop_rect, t_sel, z_sel, int(modality_idx))

    def _modality_idx_for_image(self, image_id: int) -> int:
        """Return the first modality idx for an image id, or -1 if unknown."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None:
            return -1
        for modality in manager.get_all_modalities():
            if modality.image_id == image_id:
                return modality.idx
        return -1

    def _projection_axis_for_image(self, img: "LazyImage") -> str:
        manager = self.controller.session_state.modality_manager
        if manager is None:
            return "tz"
        for modality in manager.get_all_modalities():
            if modality.image_id == img.id:
                axis = modality.display_settings.projection_axis
                if axis in ("t", "z"):
                    return axis
        return "tz"

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
        crop_rect: Optional[Tuple[float, float, float, float]],
        full_shape: Tuple[int, int],
    ) -> np.ndarray:
        """Apply a crop rect (X, Y, W, H) to a 2D array."""
        if crop_rect is None:
            return data
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
        modality_idx: Optional[int] = None,
    ) -> np.ndarray:
        if level <= 0 or not self.pyramid_enabled:
            return data
        if modality_idx is None:
            modality_idx = self._modality_idx_for_image(img_id)
        key = (img_id, kind, t_idx, z_idx, crop_rect, level, int(modality_idx))
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
                self._request_render_refresh("pyramid-job-finished", debounce=True)

            def _on_error(err: str) -> None:
                self._pyramid_jobs.pop(key, None)
                self._append_log(f"[JOB] Pyramid error\n{err}")

            self.jobs.submit(
                _job,
                name=job_name,
                on_result=_on_result,
                on_error=_on_error,
                priority="background",
                replace_key=job_name,
            )
        # Fallback: fast subsample while pyramid builds.
        scale = pyramid_level_factor(level)
        return self._downsample(data, scale)

    def _get_projection(
        self,
        img: "LazyImage",
        kind: str,
        axis_override: Optional[str] = None,
        modality_idx: Optional[int] = None,
    ) -> Tuple[Optional[np.ndarray], bool]:
        """Return a cached projection or LOD fallback while full-res loads.
        
        LOD-first rendering behavior:
        - If full-res cached, return it (full-res ready)
        - If not cached but 8x pyramid available, return pyramid as fallback (LOD mode)
        - Otherwise schedule full-res job and return None
        """
        kind_l = kind.lower()
        axis = axis_override or self._projection_axis_for_image(img)
        key = self._projection_key(img, kind_l, axis, modality_idx=modality_idx)
        cached = self.proj_cache.get(key)
        if cached is not None:
            # Full-res available; mark LOD mode as complete
            if not hasattr(self, '_lod_mode_active'):
                self._lod_mode_active = {}
            self._lod_mode_active[img.id] = False
            return cached, True
        
        # Phase 2a: Check for 8x pyramid level as LOD fallback
        if img.array is not None and self.pyramid_enabled:
            crop_rect = self._cache_crop_rect(img)
            t_idx, z_idx = -1, -1
            kind_key = f"{kind_l}:{axis}" if axis != "tz" else kind_l
            if modality_idx is None:
                modality_idx = self._modality_idx_for_image(img.id)
            pyramid_key = (
                img.id,
                kind_key,
                t_idx,
                z_idx,
                crop_rect,
                3,
                int(modality_idx),
            )  # level 3 = 8x downsampling
            pyramid_cached = self.proj_cache.get_pyramid(pyramid_key)
            if pyramid_cached is not None:
                # LOD pyramid available; mark LOD mode as active
                if not hasattr(self, '_lod_mode_active'):
                    self._lod_mode_active = {}
                self._lod_mode_active[img.id] = True
                self._request_projection_job(
                    img,
                    {kind_l},
                    axis_override=axis,
                    modality_idx=modality_idx,
                )
                return pyramid_cached, False  # Return LOD but mark as not fully cached
        
        # Full-res not available and no LOD fallback; schedule full-res job
        self._request_projection_job(
            img,
            {kind_l},
            axis_override=axis,
            modality_idx=modality_idx,
        )
        return None, False

    def _normalize_projection_for_display(self, proj: np.ndarray) -> np.ndarray:
        """Normalize projection output to display-friendly spatial-first shape."""
        arr = np.asarray(proj)
        if arr.ndim == 3 and arr.shape[-1] not in (3, 4) and arr.shape[0] in (3, 4):
            # Convert channel-first (C, Y, X) projections into (Y, X, C).
            arr = np.moveaxis(arr, 0, -1)
        return arr

    def _request_projection_job(
        self,
        img: "LazyImage",
        kinds: Optional[set[str]] = None,
        axis_override: Optional[str] = None,
        modality_idx: Optional[int] = None,
    ) -> None:
        """Schedule projection computation and populate the cache on completion.
        
        Pyramid prefetch behavior:
        - Schedule pyramid jobs for 8x, 4x, 2x levels first (low priority)
        - Then schedule full-res job (normal priority)
        """
        if self._playback_mode:
            return
        crop_rect = self.crop_rect or (0.0, 0.0, 0.0, 0.0)
        t_sel, z_sel = -1, -1
        if not kinds:
            kinds = {"mean", "std"}
        axis = axis_override or self._projection_axis_for_image(img)
        kinds = {k.lower() for k in kinds}
        kind_keys = {k if axis == "tz" else f"{k}:{axis}" for k in kinds}
        if modality_idx is None:
            modality_idx = self._modality_idx_for_image(img.id)
        keys = [(img.id, k, crop_rect, t_sel, z_sel, int(modality_idx)) for k in kind_keys]
        if all(key in self._projection_jobs for key in keys):
            return
        if img.array is None:
            self._ensure_loaded(img.id)
        if img.array is None:
            return
        
        # Phase 2b: Schedule pyramid prefetch jobs (8x, 4x, 2x) before full-res
        # This ensures LOD preview is available quickly
        # P3a: Skip prefetch if memory pressure detected
        prefetch_enabled = not getattr(self, '_prefetch_disabled', False)
        if self.pyramid_enabled and img.array is not None and prefetch_enabled:
            arr = img.array
            full_shape = (arr.shape[-2], arr.shape[-1])
            generation = self._job_generation
            
            # Schedule pyramid levels 3, 2, 1 (8x, 4x, 2x downsampling factors)
            for level in [3, 2, 1]:
                scale = pyramid_level_factor(level)
                for kind in sorted(kinds):
                    kind_key = kind if axis == "tz" else f"{kind}:{axis}"
                    pyramid_key = (img.id, kind_key, t_sel, z_sel, crop_rect, level, int(modality_idx))
                    if pyramid_key not in self._pyramid_jobs and self.proj_cache.get_pyramid(pyramid_key) is None:
                        job_name = f"PyramidPrefetch:{img.id}:{kind}:L{level}"
                        self._pyramid_jobs[pyramid_key] = job_name
                        
                        # Capture data at job creation time (Phase 2b: pyramid prefetch)
                        kind_local = kind
                        level_local = level
                        scale_local = scale
                        data_view = arr
                        
                        def _pyramid_job(progress, cancel_token, data=data_view, scale=scale_local, 
                                       kind_l=kind_local, level_l=level_local):
                            if cancel_token.is_cancelled():
                                return None
                            proj = compute_projection(data, kind_l, axis=axis)
                            proj = self._normalize_projection_for_display(proj)
                            proj = self._apply_crop_rect(proj, crop_rect, proj.shape[:2])
                            if proj.ndim == 3:
                                result = proj[::scale, ::scale]
                            else:
                                result = downsample_mean_pool(proj, scale)
                            return (pyramid_key, result, generation, kind_l, level_l)
                        
                        def _pyramid_result(result, pkey=pyramid_key):
                            if result is None:
                                self._pyramid_jobs.pop(pkey, None)
                                return
                            pkey_r, arr_r, gen, kind_r, level_r = result
                            if gen != self._job_generation:
                                self._pyramid_jobs.pop(pkey_r, None)
                                return
                            self.proj_cache.put_pyramid(pkey_r, arr_r)
                            self._pyramid_jobs.pop(pkey_r, None)
                            debug_log(f"[P2b] Pyramid L{level_r} cached for {kind_r}")
                        
                        def _pyramid_error(err: str, pkey=pyramid_key):
                            self._pyramid_jobs.pop(pkey, None)
                        
                        self.jobs.submit(
                            _pyramid_job,
                            name=job_name,
                            on_result=_pyramid_result,
                            on_error=_pyramid_error,
                            priority="background",
                            replace_key=job_name,
                        )
        
        # Now schedule full-res projection job
        if not self.proj_cache.should_compute(int(modality_idx)):
            return
        generation = self._job_generation
        arr = img.array
        job_name = f"Projections:{img.id}"
        full_shape = (arr.shape[-2], arr.shape[-1])

        def _job(progress, cancel_token):
            if cancel_token.is_cancelled():
                return None
            if arr.nbytes >= PROJECTION_ASYNC_BYTES:
                progress(5, "Computing projections")
            proj_map = compute_projections(arr, kinds, axis=axis)
            if cancel_token.is_cancelled():
                return None
            for k in list(proj_map.keys()):
                proj = self._normalize_projection_for_display(proj_map[k])
                proj_map[k] = self._apply_crop_rect(proj, crop_rect, full_shape)
            progress(100, "Done")
            return (proj_map, img.id, generation, crop_rect, t_sel, z_sel)

        job_id_holder = {"id": None}

        def _on_result(result):
            if result is None:
                return
            proj_map, image_id, gen, crop_key, t_key, z_key = result
            if gen != self._job_generation:
                return
            if image_id < 0 or image_id >= len(self.images):
                return
            for kind_local, proj in proj_map.items():
                kind_key = kind_local if axis == "tz" else f"{kind_local}:{axis}"
                key_local = (image_id, kind_key, crop_key, t_key, z_key, int(modality_idx))
                self.proj_cache.put(key_local, proj)
            if job_id_holder["id"] is not None:
                self._clear_projection_job_name(job_id_holder["id"])
            # Mark LOD mode as complete (full-res now available)
            if not hasattr(self, '_lod_mode_active'):
                self._lod_mode_active = {}
            self._lod_mode_active[image_id] = False
            # Projection job completions are debounced to avoid re-entering
            # projection scheduling in the same event-loop turn.
            self._request_render_refresh("projection-job-finished", debounce=True)

        def _on_error(err: str) -> None:
            if job_id_holder["id"] is not None:
                self._clear_projection_job_name(job_id_holder["id"])
            self._append_log(f"[JOB] Projection error for {img.name}\n{err}")
            if self.dock_logs is not None:
                self.set_panel_visible("logs", True, source="projection_error")

        if arr.nbytes >= PROJECTION_ASYNC_BYTES:
            handle = self.jobs.submit(
                _job,
                name=job_name,
                on_result=_on_result,
                on_error=_on_error,
                priority="interactive",
                replace_key=job_name,
            )
            job_id_holder["id"] = handle.job_id
            for key in keys:
                self._projection_jobs[key] = handle.job_id
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
        img = self._playback_source_image() if hasattr(self, "_playback_source_image") else self.primary_image
        if img is None or img.array is None:
            return np.empty((0, 0, 0), dtype=np.float32)
        arr = img.array
        if arr.ndim >= 4:
            z_safe = max(0, min(int(z_idx), int(arr.shape[1]) - 1))
            block = read_contiguous_block(arr, t_start, t_stop, z_safe)
        elif arr.ndim == 3:
            # Compatibility path for legacy (T, Y, X) stacks.
            block = arr[t_start:t_stop, :, :]
        else:
            return np.empty((0, 0, 0), dtype=np.float32)
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

    def get_diagnostic_info(self, image_id: int) -> dict:
        """Get detailed diagnostic info for a given image.
        
        Returns
        -------
        dict
            Diagnostic information including:
            - downsampled: bool
            - downsampling_reason: Optional[str]
            - lod_active: bool
            - memmap: bool
            - downsample_factor: int
            - render_scale: float (interactive downsampling factor)
        """
        img = None
        for image in self.images:
            if image.id == image_id:
                img = image
                break
        if img is None:
            return {}
        
        render_scales = getattr(self, "_render_scales", {}) or {}
        render_scale = render_scales.get(image_id, 1.0)
        lod_active = getattr(self, "_lod_mode_active", {}) or {}
        
        return {
            "downsampled": getattr(img, "downsampled", False),
            "downsampling_reason": getattr(img, "downsampling_reason", None),
            "downsample_factor": getattr(img, "downsample_factor", 1),
            "lod_active": lod_active.get(image_id, False),
            "memmap": getattr(img.array, "filename", None) is not None if img.array else False,
            "render_scale": float(render_scale),
        }

    def format_diagnostic_tooltip(self, image_id: int) -> str:
        """Format a detailed diagnostic tooltip for display.
        
        Example output:
        "Image 1: Spatial 2x downsampled (memory: 1.9 GB > 1.5 GB threshold)
         Interactive: 2x downsampled; LOD active; Memmap"
        """
        diags = self.get_diagnostic_info(image_id)
        if not diags:
            return "No diagnostic information"
        
        lines = []
        
        # Memory pressure diagnostics
        if diags["downsampled"]:
            reason = diags.get("downsampling_reason", "")
            lines.append(f"Spatial downsampling: {diags['downsample_factor']}x")
            if reason:
                lines.append(f"  Reason: {reason}")
        
        # Interactive/render diagnostics
        interactive_flags = []
        if diags["render_scale"] > 1:
            interactive_flags.append(f"Interactive {int(diags['render_scale'])}x")
        if diags["lod_active"]:
            interactive_flags.append("LOD active")
        if diags["memmap"]:
            interactive_flags.append("Memmap mode")
        
        if interactive_flags:
            lines.append("Display: " + "; ".join(interactive_flags))
        
        return "\n".join(lines) if lines else "Full resolution, no optimizations active"

    def _flash_status(self, text: str, ms: int = 1200) -> None:
        """Show a temporary status message without overwriting derived status."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        from phage_annotator.ui_qt.services.status import StatusMessage

        status_service.post_message(
            StatusMessage(
                text=str(text),
                severity=status_service.infer_severity(text),
                timeout_ms=int(ms),
                source="legacy._flash_status",
                sticky=False,
                min_visible_ms=min(int(ms), 1200),
            )
        )

    def _status_info(self, text: str, *, timeout_ms: int | None = None, source: str = "ui") -> None:
        """Post an informational status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.info(text, timeout_ms=timeout_ms, source=source)

    def _status_success(self, text: str, *, timeout_ms: int | None = None, source: str = "ui") -> None:
        """Post a success status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.success(text, timeout_ms=timeout_ms, source=source)

    def _status_warning(
        self,
        text: str,
        *,
        timeout_ms: int | None = None,
        source: str = "ui",
        sticky: bool = False,
    ) -> None:
        """Post a warning status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.warning(text, timeout_ms=timeout_ms, source=source, sticky=sticky)

    def _status_error(
        self,
        text: str,
        *,
        timeout_ms: int | None = None,
        source: str = "ui",
        sticky: bool = False,
    ) -> None:
        """Post an error status message through the centralized service."""
        status_service = getattr(self, "status_service", None)
        if status_service is None:
            return
        status_service.error(text, timeout_ms=timeout_ms, source=source, sticky=sticky)
