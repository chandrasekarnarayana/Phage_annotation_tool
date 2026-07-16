"""SessionDataSource adapter wrapping SessionController.

This module provides a concrete data source implementation that bridges the
SessionController to the ComprehensiveDataSource interface, enabling testable
and modular rendering without breaking existing code.

Architecture
------------
- SessionDataSource wraps SessionController and implements ComprehensiveDataSource
- Minimal changes to existing code (adapter pattern)
- Enables renderer refactoring while preserving backward compatibility

Usage
-----
::

    # Wrap existing session controller.
    data_source = SessionDataSource(session_controller)
    frame = data_source.get_frame(t_idx=0, z_idx=0)
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

import numpy as np

from phage_annotator.data.source_base import (
    Annotation,
    Calibration,
    ComprehensiveDataSource,
    ImageFrame,
    Projection)
from phage_annotator.io.data.transforms import (
    full_to_display as _full_to_display_yx,
    display_to_full as _display_to_full_yx)

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController


from phage_annotator.data.session_data_source_methods1 import _SessionDataSourceMethods1
from phage_annotator.data.session_data_source_methods2 import _SessionDataSourceMethods2

class SessionDataSource(_SessionDataSourceMethods1, _SessionDataSourceMethods2, ComprehensiveDataSource):
    """Data source adapter wrapping SessionController.

    This adapter bridges the old SessionController API to the new
    ComprehensiveDataSource interface, enabling incremental refactoring.

    Parameters
    ----------
    session : SessionController
        The session controller to wrap.

    Notes
    -----
    - All coordinate transforms use the session's view state (crop, downsample).
    - Caching is handled by underlying session controller components.
    - This adapter is read-only; mutations still go through SessionController.
    """

    # ------------------------------------------------------------------
    # Core shape/dtype/availability
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Frame and projection access
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Overlays
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------



__all__ = ["SessionDataSource"]
