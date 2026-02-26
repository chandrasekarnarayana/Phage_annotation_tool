"""Backward compatibility facade for gui_constants.

This module has been moved to ui_qt.utils.constants.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.utils.constants import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_constants is deprecated. "
    f"Please import from phage_annotator.ui_qt.utils.constants instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
