"""Rendering and visualization (P3 refactoring).

Matplotlib-based visualization components:
- Figure rendering and layout management
- Orthogonal views (XY, XZ, YZ projections)
- Scale bar rendering
- Lookup table (LUT) management for color mapping
"""

from phage_annotator.rendering.mpl import Renderer

__all__ = [
    "Renderer",
]
