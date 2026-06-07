"""Abstract data-source interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from phage_annotator.data.sources import (
    ImageFrame, Projection, Annotation, Calibration, DataSource,
)


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
