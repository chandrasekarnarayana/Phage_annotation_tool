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

from phage_annotator.ui_qt.utils.state_projection_methods1 import _StateProjectionMixinMethods1
from phage_annotator.ui_qt.utils.state_projection_methods2 import _StateProjectionMixinMethods2

class StateProjectionMixin(_StateProjectionMixinMethods1, _StateProjectionMixinMethods2):
    """Projection computation, pyramid display, and background job scheduling."""

    pass
