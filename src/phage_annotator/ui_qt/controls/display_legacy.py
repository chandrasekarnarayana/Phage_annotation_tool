"""Backward compatibility facade for gui_controls_display.

This module has been moved to ui_qt.controls.display.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.controls.display import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_controls_display is deprecated. "
    f"Please import from phage_annotator.ui_qt.controls.display instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
