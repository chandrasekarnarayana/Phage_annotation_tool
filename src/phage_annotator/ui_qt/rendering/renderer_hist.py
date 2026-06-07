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

class RenderingHistMixin:
    """Histogram computation, normalization, and background job scheduling."""

    def _hist_values(self, slice_data: np.ndarray) -> Optional[np.ndarray]:
        """Document the hist_values flow."""
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
        """Document the hist_values_current flow."""
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
        """Document the request_hist_job flow."""
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
            """Document the job flow."""
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
            """Document the on_result flow."""
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
            """Document the on_error flow."""
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
        """Document the norm_cached flow."""
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
