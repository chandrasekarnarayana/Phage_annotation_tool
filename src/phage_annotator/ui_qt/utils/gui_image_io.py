"""Backward compatibility facade for gui_image_io.

This module has been moved to ui_qt.utils.image_io.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.utils.image_io import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_image_io is deprecated. "
    f"Please import from phage_annotator.ui_qt.utils.image_io instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
