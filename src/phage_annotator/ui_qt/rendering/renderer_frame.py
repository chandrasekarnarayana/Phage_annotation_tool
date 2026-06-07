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

class RenderingFrameMixin:
    """Channel frame building, multichannel composition, and cache invalidation."""

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
        """Document the clear_histogram_cache flow."""
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
