"""Backward compatibility facade for LUT helpers.

This module has been moved to phage_annotator.ui_qt.rendering.lut_manager.
"""

from phage_annotator.ui_qt.rendering.lut_manager import LUTS, LutSpec, cmap_for, lut_names

__all__ = ["LUTS", "LutSpec", "cmap_for", "lut_names"]
