"""Backward compatibility facade for gui_export.

This module has been moved to ui_qt.utils.export.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.utils.export import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_export is deprecated. "
    f"Please import from phage_annotator.ui_qt.utils.export instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
