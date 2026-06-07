"""Data source interfaces for render/data separation.

This module defines abstract interfaces for data provision to renderers,
implementing the layered architecture principle of separating data access
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

These are interface contracts only. ``NotImplementedError`` occurrences in this
module are intentional abstract-method placeholders, not runtime TODO stubs.
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


from phage_annotator.data.source_abstracts import (
    ImageDataSource, AnnotationDataSource, OverlayDataSource,
    CalibratedDataSource, ComprehensiveDataSource,
)

__all__ = [
    "ImageFrame", "Projection", "Annotation", "Calibration", "DataSource",
    "ImageDataSource", "AnnotationDataSource", "OverlayDataSource",
    "CalibratedDataSource", "ComprehensiveDataSource",
]
