"""Phage Annotator - Microscopy image annotation tool.

See documentation at: https://github.com/chandrasekarnarayana/Phage_annotation_tool

Package structure (Fiji-style architecture):
- core/: Domain models (Annotation, Keypoint, Dataset)
- io/: I/O operations (read/write TIFF, JSON, projects)
- data/: Image data handling (LazyImage, Pyramid, RingBuffer)
- algorithms/: Analysis algorithms (ROI detection, SMLM, density, deep learning)
- cache/: Caching strategies (ProjectionCache, DiskCache, ArrayPool)
- framework/: Service architecture (EventService, LogService, etc.)
- tools/: Tool logic (non-GUI business logic)
- ui_qt/: Qt GUI implementation (panels, actions, rendering, widgets)
- plugins/: Plugin space for extensions

Backward compatibility:
This package maintains backward compatibility. Old code importing from
phage_annotator.annotations still works; imports are re-exported.
New code should import from the explicit packages:
  from phage_annotator.core import Annotation, Keypoint
  from phage_annotator.io import read_tiff
  from phage_annotator.algorithms import analyze_image
"""

# Import from new locations
from phage_annotator.annotation.core import (
    Keypoint,
    keypoints_from_csv,
    keypoints_from_json,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
)
from phage_annotator.config import DEFAULT_CONFIG, AppConfig
from phage_annotator.framework import (
    ApplicationContext,
    EventService,
    LogService,
    SettingsService,
    ThreadService,
    CacheService,
)
from phage_annotator.rendering import Renderer
from phage_annotator.roi import RoiManager, Roi

# Optional in headless environments without Qt bindings.
try:  # pragma: no cover - exercised by environment-dependent imports
    from phage_annotator.session import SessionController, SessionState
except ImportError:  # pragma: no cover
    SessionController = None  # type: ignore[assignment]
    SessionState = None  # type: ignore[assignment]

# Note: Backward compatibility facades for old module names are handled
# through import aliasing (renaming the old files to module structure)

__version__ = "1.0.1"

__all__ = [
    "__version__",
    # Main classes
    "SessionController",
    "SessionState",
    "Renderer",
    "RoiManager",
    "Roi",
    # Backward compatibility (old imports)
    "Keypoint",
    "keypoints_from_csv",
    "keypoints_from_json",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "AppConfig",
    "DEFAULT_CONFIG",
    # Framework exports
    "ApplicationContext",
    "EventService",
    "LogService",
    "SettingsService",
    "ThreadService",
    "CacheService",
]
