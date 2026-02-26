"""Backward compatibility facade for gui_events.

This module has been moved to ui_qt.actions.events.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.actions.events import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_events is deprecated. "
    f"Please import from phage_annotator.ui_qt.actions.events instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
