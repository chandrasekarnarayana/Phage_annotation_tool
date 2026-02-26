"""Core domain models and data structures - FIJI Layer 1: Core Models.

This package implements the CORE LAYER of the FIJI-style architecture,
containing pure domain objects and data models independent of rendering,
storage, or UI frameworks.

**FIJI Layer**: 1 (Core domain models)

**Responsibilities**:
- Define immutable domain models (Keypoint, ViewState, SessionState)
- Provide data structures for basic microscopy concepts
- Enable serialization/deserialization of annotations
- No dependencies on Qt, rendering engines, or storage backends

**Key Classes**:
- Keypoint: Represents a single annotated point in microscopy data
  - image_id, t, z coordinates (TCZYX format)
  - Metadata (label, confidence, etc.)
  - Immutable by design

- ViewState: Represents the current view/display preferences
  - T/Z indices, crop/ROI rectangles, display mapping parameters
  - Used by rendering engines to determine what to display

- SessionState: Represents complete annotation session state
  - Images, annotations, labels, display settings
  - Used by SessionController for state management

**Design Patterns**:
- Immutable Value Objects: Keypoint, ViewState designed as frozen dataclasses
- Factory Pattern: keypoints_from_csv/json for deserialization
- Strategy Pattern: Multiple serialization formats (CSV, JSON)

**Dependencies**:
- No Qt, no matplotlib, no storage backends
- Pure Python with numpy for array operations
- Testable in isolation

**Example Usage**:
    from phage_annotator.core import Keypoint, ViewState
    
    # Create a keypoint at t=5, z=10, y=100, x=200
    kp = Keypoint(image_id=0, t=5, z=10, y=100.0, x=200.0, label="centroid")
    
    # View state is also immutable
    view = ViewState(t=5, z=10, crop_rect=(300, 300, 600, 600))

**See Also**:
    - src/phage_annotator/data - Data access layer wrapping core models
    - src/phage_annotator/framework - Services managing core objects
"""


# Import from new locations (Phase 2.5 physical migration)
from phage_annotator.core.annotation import (
    Keypoint,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
    keypoints_from_csv,
    keypoints_from_json,
)

__all__ = [
    "Keypoint",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
]
