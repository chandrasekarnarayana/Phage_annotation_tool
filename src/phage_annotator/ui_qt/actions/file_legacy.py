"""Backward compatibility facade for gui_file_actions.

This module has been moved to ui_qt.actions.file.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.actions.file import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_file_actions is deprecated. "
    f"Please import from phage_annotator.ui_qt.actions.file instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
