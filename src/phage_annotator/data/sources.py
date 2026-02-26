"""Data source interfaces for render/data separation.

This module defines abstract interfaces for data provision to renderers,
implementing the FIJI-style architecture principle of separating data access
from data visualization.

Architecture Principles
-----------------------
1. Renderers pull data through interfaces, never directly access data models
2. Data sources are responsible for coordinate transforms, caching, prefetching
3. Renderers are responsible only for drawing operations
4. Data sources can be swapped/mocked for testing

Key Interfaces
--------------
- DataSource: Base interface for all data providers
- ImageDataSource: Provides image frames and projections
- AnnotationDataSource: Provides annotation overlays
- OverlayDataSource: Provides generic overlay data
- CalibratedDataSource: Provides calibration metadata

Benefits
--------
- Clean separation of concerns
- Testable rendering (inject mocks)
- Swappable data backends
- Clear dependency flow (renderer depends on data interface, not implementation)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class ImageFrame:
    """A single 2D image frame with metadata.
    
    Attributes
    ----------
    data : np.ndarray
        2D array at display resolution
    t_idx : int
        Time point index
    z_idx : int
        Z-slice index
    full_shape : tuple[int, int]
        Original full-resolution shape (height, width)
    display_shape : tuple[int, int]
        Display resolution shape (height, width)
    crop_rect : tuple[float, float, float, float] or None
        Crop rectangle in full coordinates (x, y, w, h)
    downsample_factor : int
        Downsampling factor applied
    """
    
    data: np.ndarray
    t_idx: int
    z_idx: int
    full_shape: Tuple[int, int]
    display_shape: Tuple[int, int]
    crop_rect: Optional[Tuple[float, float, float, float]]
    downsample_factor: int


@dataclass(frozen=True)
class Projection:
    """A computed projection (mean, std, max, etc.).
    
    Attributes
    ----------
    data : np.ndarray
        2D projection array
    projection_type : str
        Type of projection ("mean", "std", "max", "sum")
    axes : tuple[int, ...]
        Axes over which projection was computed
    full_shape : tuple[int, int]
        Original shape before projection
    """
    
    data: np.ndarray
    projection_type: str
    axes: Tuple[int, ...]
    full_shape: Tuple[int, int]


@dataclass(frozen=True)
class Annotation:
    """A single annotation point with metadata.
    
    Attributes
    ----------
    x : float
        X coordinate in full-image space
    y : float
        Y coordinate in full-image space
    label : str
        Annotation label or category
    color : str
        Display color (hex or named)
    selected : bool
        Whether annotation is selected
    t_idx : int
        Time point index
    z_idx : int
        Z-slice index
    metadata : dict
        Additional metadata
    """
    
    x: float
    y: float
    label: str
    color: str
    selected: bool
    t_idx: int
    z_idx: int
    metadata: Dict[str, object] = None


@dataclass(frozen=True)
class Calibration:
    """Pixel size calibration metadata.
    
    Attributes
    ----------
    pixel_size_um : float
        Pixel size in micrometers
    unit : str
        Unit string (e.g., "µm", "nm")
    calibrated : bool
        Whether calibration is available
    """
    
    pixel_size_um: float
    unit: str
    calibrated: bool


class DataSource(ABC):
    """Base interface for all data sources.
    
    Data sources provide read-only access to data for rendering.
    They handle coordinate transforms, caching, and lazy loading.
    """
    
    @abstractmethod
    def get_shape(self) -> Tuple[int, ...]:
        """Return full data shape (T, Z, Y, X)."""
        raise NotImplementedError
    
    @abstractmethod
    def get_dtype(self) -> np.dtype:
        """Return data type of arrays provided."""
        raise NotImplementedError
    
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if data source is ready to provide data."""
        raise NotImplementedError


class ImageDataSource(DataSource):
    """Interface for image frame and projection data.
    
    Provides access to raw frames, support images, and computed projections.
    Handles cropping, downsampling, and coordinate transforms.
    """
    
    @abstractmethod
    def get_frame(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> ImageFrame:
        """Get a single image frame at display resolution.
        
        Parameters
        ----------
        t_idx : int
            Time point index
        z_idx : int
            Z-slice index
        crop_rect : tuple or None
            Crop rectangle in full coordinates (x, y, w, h)
        downsample : int
            Downsampling factor (1 = no downsampling)
            
        Returns
        -------
        ImageFrame
            Frame with metadata
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_projection(
        self,
        projection_type: str,
        axes: Tuple[int, ...],
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> Projection:
        """Get a computed projection.
        
        Parameters
        ----------
        projection_type : str
            "mean", "std", "max", or "sum"
        axes : tuple of int
            Axes to project over (e.g., (0,) for time)
        crop_rect : tuple or None
            Crop rectangle in full coordinates
        downsample : int
            Downsampling factor
            
        Returns
        -------
        Projection
            Projection data with metadata
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_support_frame(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> Optional[ImageFrame]:
        """Get support image frame if available.
        
        Returns None if no support image is loaded.
        """
        raise NotImplementedError
    
    @abstractmethod
    def transform_full_to_display(
        self,
        coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]],
        downsample: int,
    ) -> List[Tuple[float, float]]:
        """Transform coordinates from full-image to display space.
        
        Parameters
        ----------
        coords : sequence of (x, y)
            Coordinates in full-image space
        crop_rect : tuple or None
            Active crop rectangle
        downsample : int
            Active downsampling factor
            
        Returns
        -------
        list of (x, y)
            Coordinates in display space
        """
        raise NotImplementedError
    
    @abstractmethod
    def transform_display_to_full(
        self,
        coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]],
        downsample: int,
    ) -> List[Tuple[float, float]]:
        """Transform coordinates from display to full-image space."""
        raise NotImplementedError


class AnnotationDataSource(DataSource):
    """Interface for annotation overlay data.
    
    Provides filtered, transformed annotations for rendering.
    """
    
    @abstractmethod
    def get_annotations(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
        selected_only: bool = False,
    ) -> List[Annotation]:
        """Get annotations for a specific frame in display coordinates.
        
        Parameters
        ----------
        t_idx : int
            Time point index
        z_idx : int
            Z-slice index
        crop_rect : tuple or None
            Crop rectangle (filters out-of-bounds annotations)
        downsample : int
            Downsampling factor (transforms coordinates)
        selected_only : bool
            If True, return only selected annotations
            
        Returns
        A list of transformed annotations
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_annotation_count(
        self,
        t_idx: Optional[int] = None,
        z_idx: Optional[int] = None,
    ) -> int:
        """Get total annotation count, optionally filtered by frame."""
        raise NotImplementedError


class OverlayDataSource(DataSource):
    """Interface for generic overlay data (ROI, particles, etc.).
    
    Provides transformed overlay geometries for rendering.
    """
    
    @abstractmethod
    def get_roi_overlays(
        self,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> List[Tuple[str, object, str]]:
        """Get ROI overlays in display coordinates.
        
        Returns
        -------
        list of (shape, data, color)
            shape: "box", "circle", "polygon"
            data: geometry (e.g., (x, y, w, h) for box)
            color: hex color string
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_particle_overlays(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> List[Tuple[str, object, str, bool]]:
        """Get particle overlays in display coordinates.
        
        Returns
        -------
        list of (shape, data, color, selected)
            shape: "circle" typically
            data: (x, y, w, h) bounding box
            color: hex color string
            selected: whether particle is selected
        """
        raise NotImplementedError


class CalibratedDataSource(DataSource):
    """Interface for calibration metadata.
    
    Provides pixel size and unit information for scale bars and measurements.
    """
    
    @abstractmethod
    def get_calibration(self) -> Calibration:
        """Get pixel size calibration.
        
        Returns
        -------
        Calibration
            Calibration metadata
        """
        raise NotImplementedError


class ComprehensiveDataSource(
    ImageDataSource,
    AnnotationDataSource,
    OverlayDataSource,
    CalibratedDataSource,
):
    """Base class for data sources implementing all interfaces.
    
    This abstract base class combines all data source interfaces.
    Subclasses must implement all abstract methods from the parent interfaces.
    """
    
    pass


__all__ = [
    "DataSource",
    "ImageDataSource",
    "AnnotationDataSource",
    "OverlayDataSource",
    "CalibratedDataSource",
    "ComprehensiveDataSource",
    "ImageFrame",
    "Projection",
    "Annotation",
    "Calibration",
]
