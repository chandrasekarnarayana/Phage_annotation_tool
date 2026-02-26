"""Backward compatibility facade for gui_rendering.

This module has been moved to ui_qt.rendering.renderer.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.rendering.renderer import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_rendering is deprecated. "
    f"Please import from phage_annotator.ui_qt.rendering.renderer instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
