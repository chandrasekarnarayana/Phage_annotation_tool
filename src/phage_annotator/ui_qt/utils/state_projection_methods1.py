"""Method group 1 split from state_projection.py."""

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

class _StateProjectionMixinMethods1:
    """Methods split from StateProjectionMixin."""

    def _get_calibration_state(self, image_id: int) -> CalibrationState:
        """Document the get_calibration_state flow."""
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
        """Document the projection_key flow."""
        crop_rect = self._cache_crop_rect(img)
        if axis != "tz":
            kind = f"{kind}:{axis}"
        # Projections are global over T/Z; keep selection fields for key shape.
        t_sel, z_sel = -1, -1
        if modality_idx is None:
            modality_idx = self._modality_idx_for_image(img.id)
        return (img.id, kind, crop_rect, t_sel, z_sel, int(modality_idx))

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
        """Document the get_pyramid_display flow."""
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
                """Document the job flow."""
                if cancel_token.is_cancelled():
                    return None
                result = downsample_mean_pool(data_view, scale)
                return (key, result, generation)

            def _on_result(result) -> None:
                """Document the on_result flow."""
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
                """Document the on_error flow."""
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
