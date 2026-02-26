"""Backward compatibility facade for gui_roi_crop.

This module has been moved to ui_qt.rendering.roi_crop.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.rendering.roi_crop import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_roi_crop is deprecated. "
    f"Please import from phage_annotator.ui_qt.rendering.roi_crop instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
