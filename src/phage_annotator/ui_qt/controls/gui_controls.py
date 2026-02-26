"""Backward compatibility facade for gui_controls.

This module has been moved to ui_qt.controls.base.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.controls.base import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_controls is deprecated. "
    f"Please import from phage_annotator.ui_qt.controls.base instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
