"""Backward compatibility facade for deepstorm_widget.

This module has been moved to ui_qt.panels.deepstorm.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.panels.deepstorm import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.deepstorm_widget is deprecated. "
    f"Please import from phage_annotator.ui_qt.panels.deepstorm instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
