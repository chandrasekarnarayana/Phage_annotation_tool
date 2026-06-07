"""Extracted method group 4 for StateMixin."""

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



class PlaybackControlsTimerMixin:
    """Method group 4 extracted from StateMixin."""

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
                            """Handle the pyramid job helper flow."""
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
                            """Handle the pyramid result helper flow."""
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
                            """Handle the pyramid error helper flow."""
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
            """Handle the job helper flow."""
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
            """Handle the on result helper flow."""
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
            """Handle the on error helper flow."""
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
        """Update image artist for the current workflow."""
        artist.set_data(data)
        artist.set_cmap(cmap)
        artist.set_clim(vmin, vmax)
        if extent is None:
            extent = (0, data.shape[1], data.shape[0], 0)
        artist.set_extent(extent)
    def _clear_image_overlays(self) -> None:
        """Clear image overlays for the current workflow."""
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
