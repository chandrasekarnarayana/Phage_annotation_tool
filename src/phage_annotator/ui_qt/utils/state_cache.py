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

class StateCacheMixin:
    """Image cache management, slice loading, and crop rect tracking."""

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

    def _slice_indices(self, img: "LazyImage") -> Tuple[int, int]:
        """Document the slice_indices flow."""
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
