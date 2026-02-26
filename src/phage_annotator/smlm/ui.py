"""Backward compatibility facade for smlm_ui.

This module has been moved to ui_qt.panels.smlm.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.panels.smlm import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.smlm_ui is deprecated. "
    f"Please import from phage_annotator.ui_qt.panels.smlm instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
