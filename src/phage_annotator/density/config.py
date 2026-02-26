"""Backward compatibility facade for density_config.

This module has been moved to config.density.
All imports are re-exported for backward compatibility.
"""

import warnings
from phage_annotator.config.density import *  # noqa: F401, F403

warnings.warn(
    f"Importing from phage_annotator.density_config is deprecated. "
    f"Please import from phage_annotator.config.density instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []  # Re-exported from target module
