"""Method group 1 split from session_ds.py."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

import numpy as np

from phage_annotator.data.sources import (
    Annotation,
    Calibration,
    ComprehensiveDataSource,
    ImageFrame,
    Projection,
)
from phage_annotator.io.data.transforms import (
    full_to_display as _full_to_display_yx,
    display_to_full as _display_to_full_yx,
)

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController


class _SessionDataSourceMethods1:
    """Methods split from SessionDataSource."""

    def __init__(self, session: "SessionController") -> None:
        """Document the init flow."""
        self._session = session

    def get_shape(self) -> Tuple[int, int, int, int]:
        """Return full data shape (T, Z, Y, X) for primary image."""
        img = self._get_primary_image()
        if img is None:
            return (1, 1, 1, 1)
        
        axis_info = getattr(img, "axis_info", {}) or {}
        tzyx = axis_info.get("tzyx")
        if isinstance(tzyx, tuple) and len(tzyx) == 4:
            return tzyx
        # LazyImage shape varies: (Y, X), (T, Y, X), or (T, Z, Y, X)
        if len(img.shape) == 2:
            return (1, 1, img.shape[0], img.shape[1])
        elif len(img.shape) == 3:
            if img.has_time and not img.has_z:
                return (img.shape[0], 1, img.shape[1], img.shape[2])
            elif img.has_z and not img.has_time:
                return (1, img.shape[0], img.shape[1], img.shape[2])
            else:
                # Ambiguous, default to time
                return (img.shape[0], 1, img.shape[1], img.shape[2])
        else:
            return tuple(img.shape)

    def get_dtype(self) -> np.dtype:
        """Return data type of arrays provided."""
        img = self._get_primary_image()
        return img.dtype if img is not None else np.dtype(np.float32)

    def is_available(self) -> bool:
        """Return True if data source is ready to provide data."""
        return self._get_primary_image() is not None

    def get_frame(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> ImageFrame:
        """Get a single image frame at display resolution.
        
        Delegates to session's ring buffer or LazyImage with cropping/downsampling.
        """
        img = self._get_primary_image()
        if img is None:
            raise RuntimeError("No primary image available")
        
        # Use ring buffer if available (handles prefetching, caching)
        if self._session.ring_buffer is not None:
            data = self._session.ring_buffer.get_frame(t_idx, z_idx)
        else:
            # Direct access
            data = self._extract_frame_direct(img, t_idx, z_idx)
        
        # Apply crop and downsample
        if crop_rect is not None:
            x, y, w, h = crop_rect
            data = data[int(y):int(y+h), int(x):int(x+w)]
        
        if downsample > 1:
            data = data[::downsample, ::downsample]
        
        full_shape = self.get_shape()[2:]  # Y, X
        display_shape = data.shape
        
        return ImageFrame(
            data=data,
            t_idx=t_idx,
            z_idx=z_idx,
            full_shape=full_shape,
            display_shape=display_shape,
            crop_rect=crop_rect,
            downsample_factor=downsample,
        )

    def get_projection(
        self,
        projection_type: str,
        axes: Tuple[int, ...],
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> Projection:
        """Get a computed projection.
        
        Delegates to session's projection cache.
        """
        img = self._get_primary_image()
        if img is None:
            raise RuntimeError("No primary image available")
        
        # Use projection cache if available
        if self._session.proj_cache is not None:
            # ProjectionCache.get(image, proj_type, axes, ...) -> array
            data = self._session.proj_cache.get(img, projection_type, axes)
        else:
            # Compute on-the-fly
            data = self._compute_projection(img, projection_type, axes)
        
        # Apply crop and downsample
        if crop_rect is not None:
            x, y, w, h = crop_rect
            data = data[int(y):int(y+h), int(x):int(x+w)]
        
        if downsample > 1:
            data = data[::downsample, ::downsample]
        
        full_shape = self.get_shape()[2:]  # Y, X
        
        return Projection(
            data=data,
            projection_type=projection_type,
            axes=axes,
            full_shape=full_shape,
        )

    def get_support_frame(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> Optional[ImageFrame]:
        """Get support image frame if available."""
        support_img = self._get_support_image()
        if support_img is None:
            return None
        
        # Extract frame
        data = self._extract_frame_direct(support_img, t_idx, z_idx)
        
        # Apply crop and downsample
        if crop_rect is not None:
            x, y, w, h = crop_rect
            data = data[int(y):int(y+h), int(x):int(x+w)]
        
        if downsample > 1:
            data = data[::downsample, ::downsample]
        
        full_shape = support_img.shape[-2:] if len(support_img.shape) >= 2 else (1, 1)
        display_shape = data.shape
        
        return ImageFrame(
            data=data,
            t_idx=t_idx,
            z_idx=z_idx,
            full_shape=full_shape,
            display_shape=display_shape,
            crop_rect=crop_rect,
            downsample_factor=downsample,
        )

    def transform_full_to_display(
        self,
        coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]],
        downsample: int,
    ) -> List[Tuple[float, float]]:
        """Transform coordinates from full-image to display space."""
        if crop_rect is None:
            crop_rect = (0, 0, 99999, 99999)
        
        result = []
        for x, y in coords:
            y_disp, x_disp = _full_to_display_yx(y, x, crop_rect, downsample)
            result.append((x_disp, y_disp))
        return result

    def transform_display_to_full(
        self,
        coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]],
        downsample: int,
    ) -> List[Tuple[float, float]]:
        """Transform coordinates from display to full-image space."""
        if crop_rect is None:
            crop_rect = (0, 0, 99999, 99999)
        
        result = []
        for x, y in coords:
            y_full, x_full = _display_to_full_yx(y, x, crop_rect, downsample)
            result.append((x_full, y_full))
        return result
