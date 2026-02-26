"""Backward compatibility facade for gui_playback.

This module has been moved to ui_qt.utils.playback.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.utils.playback import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.gui_playback is deprecated. "
    f"Please import from phage_annotator.ui_qt.utils.playback instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
