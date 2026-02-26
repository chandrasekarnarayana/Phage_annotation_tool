"""Mock data sources for testing render/data separation.

This module provides simple mock implementations of data source interfaces,
enabling isolated testing of renderers and other components that consume
data source interfaces.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from phage_annotator.data.sources import (
    Annotation,
    Calibration,
    ComprehensiveDataSource,
    ImageFrame,
    Projection,
)


class MockDataSource(ComprehensiveDataSource):
    """Simple mock data source for testing.
    
    Provides predictable synthetic data for all data source interfaces.
    Useful for unit testing renderers without needing a full session.
    
    Parameters
    ----------
    shape : tuple of int
        Data shape as (T, Z, Y, X)
    fill_value : float
        Value to fill synthetic images with
    num_annotations : int
        Number of synthetic annotations to generate
        
    Examples
    --------
    >>> mock = MockDataSource(shape=(10, 1, 100, 100), fill_value=128.0)
    >>> frame = mock.get_frame(t_idx=0, z_idx=0)
    >>> frame.data.shape
    (100, 100)
    >>> frame.data[0, 0]
    128.0
    """
    
    def __init__(
        self,
        shape: Tuple[int, int, int, int] = (10, 1, 100, 100),
        fill_value: float = 128.0,
        num_annotations: int = 5,
    ) -> None:
        self._shape = shape
        self._fill_value = fill_value
        self._num_annotations = num_annotations
        self._annotations = self._generate_annotations()
    
    # =========================================================================
    # DataSource base interface
    # =========================================================================
    
    def get_shape(self) -> Tuple[int, int, int, int]:
        """Return full data shape (T, Z, Y, X)."""
        return self._shape
    
    def get_dtype(self) -> np.dtype:
        """Return data type of arrays provided."""
        return np.dtype(np.float32)
    
    def is_available(self) -> bool:
        """Return True if data source is ready to provide data."""
        return True
    
    # =========================================================================
    # ImageDataSource interface
    # =========================================================================
    
    def get_frame(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> ImageFrame:
        """Get a single image frame at display resolution."""
        t, z, h, w = self._shape
        
        # Create synthetic frame
        data = np.full((h, w), self._fill_value, dtype=np.float32)
        
        # Add pattern for visual debugging
        data[t_idx % h, :] = self._fill_value * 1.5  # Horizontal line
        data[:, z_idx % w] = self._fill_value * 1.5  # Vertical line
        
        # Apply crop
        if crop_rect is not None:
            x, y, cw, ch = crop_rect
            data = data[int(y):int(y+ch), int(x):int(x+cw)]
        
        # Apply downsample
        if downsample > 1:
            data = data[::downsample, ::downsample]
        
        full_shape = (h, w)
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
        """Get a computed projection."""
        t, z, h, w = self._shape
        
        # Create synthetic projection
        if projection_type == "mean":
            value = self._fill_value
        elif projection_type == "std":
            value = self._fill_value * 0.1
        elif projection_type == "max":
            value = self._fill_value * 1.5
        elif projection_type == "sum":
            value = self._fill_value * t if 0 in axes else self._fill_value * z
        else:
            value = self._fill_value
        
        data = np.full((h, w), value, dtype=np.float32)
        
        # Apply crop
        if crop_rect is not None:
            x, y, cw, ch = crop_rect
            data = data[int(y):int(y+ch), int(x):int(x+cw)]
        
        # Apply downsample
        if downsample > 1:
            data = data[::downsample, ::downsample]
        
        full_shape = (h, w)
        
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
        # Return None (no support image in mock)
        return None
    
    def transform_full_to_display(
        self,
        coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]],
        downsample: int,
    ) -> List[Tuple[float, float]]:
        """Transform coordinates from full-image to display space."""
        if crop_rect is None:
            result = [(x / downsample, y / downsample) for x, y in coords]
        else:
            crop_x, crop_y, _, _ = crop_rect
            result = [
                ((x - crop_x) / downsample, (y - crop_y) / downsample)
                for x, y in coords
            ]
        return result
    
    def transform_display_to_full(
        self,
        coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]],
        downsample: int,
    ) -> List[Tuple[float, float]]:
        """Transform coordinates from display to full-image space."""
        if crop_rect is None:
            result = [(x * downsample, y * downsample) for x, y in coords]
        else:
            crop_x, crop_y, _, _ = crop_rect
            result = [
                (x * downsample + crop_x, y * downsample + crop_y)
                for x, y in coords
            ]
        return result
    
    # =========================================================================
    # AnnotationDataSource interface
    # =========================================================================
    
    def get_annotations(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
        selected_only: bool = False,
    ) -> List[Annotation]:
        """Get annotations for a specific frame in display coordinates."""
        # Filter by selection
        annotations = [a for a in self._annotations if not selected_only or a.selected]
        
        # Transform to display coordinates
        result = []
        for ann in annotations:
            full_coords = [(ann.x, ann.y)]
            display_coords = self.transform_full_to_display(
                full_coords, crop_rect, downsample
            )
            x_disp, y_disp = display_coords[0]
            
            # Filter if outside bounds
            if crop_rect is not None:
                _, _, cw, ch = crop_rect
                if x_disp < 0 or y_disp < 0 or x_disp >= cw / downsample or y_disp >= ch / downsample:
                    continue
            
            result.append(Annotation(
                x=x_disp,
                y=y_disp,
                label=ann.label,
                color=ann.color,
                selected=ann.selected,
                t_idx=t_idx,
                z_idx=z_idx,
                metadata=ann.metadata,
            ))
        
        return result
    
    def get_annotation_count(
        self,
        t_idx: Optional[int] = None,
        z_idx: Optional[int] = None,
    ) -> int:
        """Get total annotation count, optionally filtered by frame."""
        return len(self._annotations)
    
    # =========================================================================
    # OverlayDataSource interface
    # =========================================================================
    
    def get_roi_overlays(
        self,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> List[Tuple[str, object, str]]:
        """Get ROI overlays in display coordinates."""
        # Return a simple box ROI
        _, _, h, w = self._shape
        roi_full = (w * 0.25, h * 0.25, w * 0.5, h * 0.5)  # Center box
        
        # Transform to display
        if crop_rect is not None:
            crop_x, crop_y, _, _ = crop_rect
            roi_disp = (
                (roi_full[0] - crop_x) / downsample,
                (roi_full[1] - crop_y) / downsample,
                roi_full[2] / downsample,
                roi_full[3] / downsample,
            )
        else:
            roi_disp = (
                roi_full[0] / downsample,
                roi_full[1] / downsample,
                roi_full[2] / downsample,
                roi_full[3] / downsample,
            )
        
        return [("box", roi_disp, "#00ff00")]
    
    def get_particle_overlays(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> List[Tuple[str, object, str, bool]]:
        """Get particle overlays in display coordinates."""
        # Return empty list (no particles in mock)
        return []
    
    # =========================================================================
    # CalibratedDataSource interface
    # =========================================================================
    
    def get_calibration(self) -> Calibration:
        """Get pixel size calibration."""
        return Calibration(
            pixel_size_um=0.1,
            unit="µm",
            calibrated=True,
        )
    
    # =========================================================================
    # Private helpers
    # =========================================================================
    
    def _generate_annotations(self) -> List[Annotation]:
        """Generate synthetic annotations for testing."""
        _, _, h, w = self._shape
        annotations = []
        
        for i in range(self._num_annotations):
            x = (i + 1) * w / (self._num_annotations + 1)
            y = (i + 1) * h / (self._num_annotations + 1)
            
            annotations.append(Annotation(
                x=x,
                y=y,
                label=f"Mock_{i}",
                color="#ff0000" if i % 2 == 0 else "#00ff00",
                selected=(i == 0),  # First annotation selected
                t_idx=0,
                z_idx=0,
                metadata={"mock_id": i},
            ))
        
        return annotations


__all__ = ["MockDataSource"]
