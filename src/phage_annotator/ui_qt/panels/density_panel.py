"""Backward compatibility facade for density_panel.

This module has been moved to ui_qt.panels.density.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.panels.density import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.density_panel is deprecated. "
    f"Please import from phage_annotator.ui_qt.panels.density instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
