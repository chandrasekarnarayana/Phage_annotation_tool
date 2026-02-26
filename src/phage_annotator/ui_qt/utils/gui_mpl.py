"""Backward compatibility facade for gui_mpl.

This module has been moved to ui_qt.main_window.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.main_window import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_mpl is deprecated. "
    f"Please import from phage_annotator.ui_qt.main_window instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
