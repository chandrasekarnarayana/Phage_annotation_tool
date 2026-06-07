"""Application events for service integration.

This module defines event types used throughout the application to decouple
components through the event bus (EventService).

**Design Pattern**: Observer pattern via EventService
**Usage**: Publish events when state changes, subscribe to events for reactions

**Example**:
    - Annotation changes → AnnotationChangedEvent published
    - View state changes → ViewStateChangedEvent published
    - Settings changes → SettingsChangedEvent published
    
All components listen via EventService without tight coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class ApplicationEvent:
    """Base class for all application events.
    
    Provides common timestamp and origin tracking for all events.
    Enables uniform handling in EventService.
    """

    def __init__(self):
        """Initialize event with timestamp (current time)."""
        import time
        self.timestamp = time.time()
        self.event_type = self.__class__.__name__


@dataclass
class AnnotationChangedEvent(ApplicationEvent):
    """Published when annotations are added, removed, or modified.
    
    Listeners can invalidate caches, refresh UI, trigger analysis, etc.
    without direct coupling to annotation model.
    
    Parameters
    ----------
    image_id : int
        ID of image that was annotated
    annotations : List[Any]
        List of Keypoint annotations (after change)
    change_type : str
        "added", "removed", "modified", "cleared"
    """

    image_id: int
    annotations: List[Any]
    change_type: str = "modified"

    def __init__(self, image_id: int, annotations: List[Any], change_type: str = "modified"):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.image_id = image_id
        self.annotations = annotations
        self.change_type = change_type


@dataclass
class ViewStateChangedEvent(ApplicationEvent):
    """Published when view state changes (T, Z, ROI, crop, display mapping).
    
    Used to trigger rendering updates, cache invalidation, overlays, etc.
    
    Parameters
    ----------
    change_type : str
        Type of change: "t", "z", "roi", "crop", "display_mapping"
    t_index : int, optional
        New T index (if change_type == "t")
    z_index : int, optional
        New Z index (if change_type == "z")
    roi_rect : tuple, optional
        New ROI rectangle (if change_type == "roi")
    crop_rect : tuple, optional
        New crop rectangle (if change_type == "crop")
    viewport : dict, optional
        Viewport metadata for canvas-only sync operations such as linked zoom/pan.
    """

    change_type: str
    t_index: Optional[int] = None
    z_index: Optional[int] = None
    roi_rect: Optional[tuple] = None
    crop_rect: Optional[tuple] = None
    viewport: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        change_type: str,
        t_index: Optional[int] = None,
        z_index: Optional[int] = None,
        roi_rect: Optional[tuple] = None,
        crop_rect: Optional[tuple] = None,
        viewport: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.change_type = change_type
        self.t_index = t_index
        self.z_index = z_index
        self.roi_rect = roi_rect
        self.crop_rect = crop_rect
        self.viewport = dict(viewport or {}) if viewport else None


@dataclass
class CacheInvalidationEvent(ApplicationEvent):
    """Published when caches should be cleared or invalidated.
    
    Used by ProjectionCache, DiskCache, etc. to know when to discard data.
    
    Parameters
    ----------
    scope : str
        "all", "image", "frame", "projections"
    image_id : int, optional
        Image ID (if scope == "image")
    t_index : int, optional
        T index (if scope == "frame")
    z_index : int, optional
        Z index (if scope == "frame")
    """

    scope: str
    image_id: Optional[int] = None
    t_index: Optional[int] = None
    z_index: Optional[int] = None

    def __init__(
        self,
        scope: str,
        image_id: Optional[int] = None,
        t_index: Optional[int] = None,
        z_index: Optional[int] = None,
    ):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.scope = scope
        self.image_id = image_id
        self.t_index = t_index
        self.z_index = z_index


@dataclass
class SettingsChangedEvent(ApplicationEvent):
    """Published when settings change.
    
    UI listens to update display preferences, cache sizes, etc.
    
    Parameters
    ----------
    key : str
        Setting key that changed (e.g., "colormap", "cache_size")
    value : Any
        New value
    old_value : Any, optional
        Previous value (for debugging)
    """

    key: str
    value: Any
    old_value: Optional[Any] = None

    def __init__(self, key: str, value: Any, old_value: Optional[Any] = None):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.key = key
        self.value = value
        self.old_value = old_value


@dataclass
class RenderingStartedEvent(ApplicationEvent):
    """Published when rendering starts (frame being processed).
    
    UI can show progress spinners or disable controls.
    """

    image_id: int
    t_index: int
    z_index: int

    def __init__(self, image_id: int, t_index: int, z_index: int):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.image_id = image_id
        self.t_index = t_index
        self.z_index = z_index


@dataclass
class RenderingCompletedEvent(ApplicationEvent):
    """Published when rendering completes.
    
    UI can hide progress spinners, enable controls, update status.
    
    Parameters
    ----------
    image_id : int
        Image ID
    t_index : int
        T index
    z_index : int
        Z index
    success : bool
        Was rendering successful?
    error : str, optional
        Error message if success == False
    elapsed_ms : float, optional
        Rendering time in milliseconds
    """

    image_id: int
    t_index: int
    z_index: int
    success: bool
    error: Optional[str] = None
    elapsed_ms: Optional[float] = None

    def __init__(
        self,
        image_id: int,
        t_index: int,
        z_index: int,
        success: bool,
        error: Optional[str] = None,
        elapsed_ms: Optional[float] = None,
    ):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.image_id = image_id
        self.t_index = t_index
        self.z_index = z_index
        self.success = success
        self.error = error
        self.elapsed_ms = elapsed_ms


@dataclass
class FileOpenedEvent(ApplicationEvent):
    """Published when a file/project is opened.
    
    Components can load related data, update UI, etc.
    
    Parameters
    ----------
    file_path : str
        Path to opened file
    file_type : str
        "image", "project", "annotations"
    """

    file_path: str
    file_type: str

    def __init__(self, file_path: str, file_type: str):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type


@dataclass
class FileClosedEvent(ApplicationEvent):
    """Published when a file/project is closed.
    
    Components can cleanup, save state, etc.
    
    Parameters
    ----------
    file_path : str
        Path to closed file
    file_type : str
        "image", "project", "annotations"
    """

    file_path: str
    file_type: str

    def __init__(self, file_path: str, file_type: str):
        """Initialize the object and prepare its runtime state."""
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type


__all__ = [
    "ApplicationEvent", "AnnotationChangedEvent", "ViewStateChangedEvent",
    "CacheInvalidationEvent", "SettingsChangedEvent", "RenderingStartedEvent",
    "RenderingCompletedEvent", "FileOpenedEvent", "FileClosedEvent",
]
