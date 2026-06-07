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

class StateCoordsMixin:
    """Coordinate transforms, axis helpers, playback, and image artist updates."""

    def _effective_axes(self, img: "LazyImage") -> Tuple[bool, bool]:
        """Document the effective_axes flow."""
        mode = img.interpret_3d_as
        if mode == "time":
            return True, img.has_z
        if mode == "depth":
            return False, True
        return img.has_time, img.has_z

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
        """Document the projection_axis_for_image flow."""
        manager = self.controller.session_state.modality_manager
        if manager is None:
            return "tz"
        for modality in manager.get_all_modalities():
            if modality.image_id == img.id:
                axis = modality.display_settings.projection_axis
                if axis in ("t", "z"):
                    return axis
        return "tz"

    def _downsample(self, data: np.ndarray, factor: int) -> np.ndarray:
        """Downsample a 2D array by integer stride for interactive mode."""
        if factor <= 1:
            return data
        return data[::factor, ::factor]

    def _axis_scale(self, ax) -> float:
        """Document the axis_scale flow."""
        return float(self._render_scales.get(ax, 1.0))

    def _to_display_coords(self, ax, x: float, y: float) -> Tuple[float, float]:
        """Document the to_display_coords flow."""
        scale = self._axis_scale(ax)
        return x / scale, y / scale

    def _to_full_coords(self, ax, x: float, y: float) -> Tuple[float, float]:
        """Document the to_full_coords flow."""
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

    def _update_image_artist(
        self,
        artist,
        data: np.ndarray,
        cmap: str,
        vmin: float,
        vmax: float,
        extent: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        """Document the update_image_artist flow."""
        artist.set_data(data)
        artist.set_cmap(cmap)
        artist.set_clim(vmin, vmax)
        if extent is None:
            extent = (0, data.shape[1], data.shape[0], 0)
        artist.set_extent(extent)

    def _clear_image_overlays(self) -> None:
        """Document the clear_image_overlays flow."""
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
