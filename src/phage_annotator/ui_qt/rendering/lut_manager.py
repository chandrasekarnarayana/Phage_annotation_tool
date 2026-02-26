"""LUT registry for display mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import matplotlib.cm as cm


@dataclass(frozen=True)
class LutSpec:
    """LUT specification for a matplotlib colormap."""

    name: str
    matplotlib_cmap_name: str
    invert_supported: bool = True


LUTS: List[LutSpec] = [
    LutSpec("gray", "gray", True),
    LutSpec("fire", "hot", True),
    LutSpec("ice", "cool", True),
    LutSpec("green", "Greens", True),
    LutSpec("red", "Reds", True),
    LutSpec("spectrum", "nipy_spectral", True),
    LutSpec("viridis", "viridis", True),
    LutSpec("magma", "magma", True),
    LutSpec("plasma", "plasma", True),
    LutSpec("cividis", "cividis", True),
]


def lut_names() -> List[str]:
    """Return display names for all LUTs."""
    return [spec.name for spec in LUTS]


def cmap_for(spec: LutSpec, invert: bool = False):
    """Return a matplotlib colormap for the LUT spec."""
    cmap = cm.get_cmap(spec.matplotlib_cmap_name)
    if invert and spec.invert_supported:
        return cmap.reversed()
    return cmap
