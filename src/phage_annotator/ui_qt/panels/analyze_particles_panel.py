"""Backward compatibility facade for analyze_particles_panel.

This module has been moved to ui_qt.panels.particles.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.ui_qt.panels.particles import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.analyze_particles_panel is deprecated. "
    f"Please import from phage_annotator.ui_qt.panels.particles instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
