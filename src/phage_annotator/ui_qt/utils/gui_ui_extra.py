"""Backward compatibility facade for gui_ui_extra.

This module has been moved to ui_qt.utils.ui_extra.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.utils.ui_extra import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_ui_extra is deprecated. "
    f"Please import from phage_annotator.ui_qt.utils.ui_extra instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
