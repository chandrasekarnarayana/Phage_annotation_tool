"""Backward compatibility facade for gui_annotations.

This module has been moved to ui_qt.utils.annotations.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.utils.annotations import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_annotations is deprecated. "
    f"Please import from phage_annotator.ui_qt.utils.annotations instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
