"""Data models and image handling (Layer 2).

This package implements the Data Layer, providing
immutable value objects for all domain concepts and interfaces for data access.

**Layer 2 Responsibilities**:
- Image models: LazyImage (memory-mapped TIFF), DisplayMapping
- Image streaming: FrameRingBuffer, BlockPrefetcher  
- Data source interfaces: ComprehensiveDataSource, ImageDataSource, AnnotationDataSource
- Projection caching: ProjectionCache with LRU eviction
- Display state: DisplayMapping with contrast/gamma/color mapping

**Key Concepts**:
1. **LazyImage**: Memory-mapped TIFF loading (no immediate data in memory)
2. **FrameRingBuffer**: Fast streaming with configurable buffer size
3. **ComprehensiveDataSource**: Abstract interface for all data access
4. **DisplayMapping**: Contrast/gamma/color pipeline (non-destructive)
5. **Immutability**: All value objects are frozen, enabling safe sharing

**Dependencies**:
- core: Domain models (Keypoint, ViewState, SessionState)
- algorithms: For computation results  
- Not on: ui_qt, plugins (decoupled from presentation)

**Design Patterns**:
- Lazy evaluation: Data loaded on demand
- Stream processing: Ring buffer for memory efficiency
- Interface segregation: Separate sources for different data types
- Immutable value objects: Safe concurrent access

**Usage**:
    from phage_annotator.data import LazyImage, ComprehensiveDataSource
    
    # Data access through interface, not direct coupling
    image = LazyImage.from_path("data.tiff")
    data_source = SessionDataSource(controller)
    frame = data_source.get_frame(t=5, z=3)

**Architecture Evolution**:
- Physical migration from core → data
- Data source interfaces added
- Full documentation complete
"""

# Import from new locations (Phase 2.5 physical migration)
from phage_annotator.data.models import LazyImage
from phage_annotator.data.pyramid import downsample_mean_pool, pyramid_level_factor
from phage_annotator.data.ring_buffer import BlockPrefetcher, BufferStats, FrameRingBuffer
from phage_annotator.data.display_mapping import (
    DisplayMapping,
    build_norm,
    mapping_from_dict,
    mapping_to_dict,
)

# Phase 6 (P8.6): Data source interfaces for render/data separation
from phage_annotator.data.sources import (
    Annotation,
    AnnotationDataSource,
    Calibration,
    CalibratedDataSource,
    ComprehensiveDataSource,
    DataSource,
    ImageDataSource,
    ImageFrame,
    OverlayDataSource,
    Projection,
)

# Phase 8.1 (P8.8.1): Data source adapter implementations
from phage_annotator.data.session_ds import SessionDataSource
from phage_annotator.data.mock_ds import MockDataSource

__all__ = [
    # models.py
    "LazyImage",
    # pyramid.py
    "downsample_mean_pool",
    "pyramid_level_factor",
    # ring_buffer.py
    "BlockPrefetcher",
    "BufferStats",
    "FrameRingBuffer",
    # display_mapping.py
    "DisplayMapping",
    "build_norm",
    "mapping_from_dict",
    "mapping_to_dict",
    # sources.py (Phase 6)
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
    # session_ds.py (Phase 8.1)
    "SessionDataSource",
    "MockDataSource",
]
