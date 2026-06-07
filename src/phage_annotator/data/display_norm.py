"""Matplotlib normalization helpers for display mappings."""

from __future__ import annotations

import numpy as np
from matplotlib import colors as mcolors

from phage_annotator.data.display_mapping import DisplayMapping


def build_norm(mapping: DisplayMapping) -> mcolors.Normalize:
    """Return a matplotlib normalization for the display mapping.

    Gamma is applied via PowerNorm. Log mode uses a log1p transform so values at
    or below vmin remain stable and zero-safe.
    """
    vmin = float(mapping.min_val)
    vmax = float(mapping.max_val)
    if mapping.mode == "log":

        def _forward(x):
            """Transform data values into zero-safe log display coordinates."""
            return np.log1p(np.maximum(x - vmin, 0.0))

        def _inverse(y):
            """Transform log display coordinates back into data values."""
            return np.expm1(y) + vmin

        return mcolors.FuncNorm((_forward, _inverse), vmin=vmin, vmax=vmax)
    if mapping.gamma != 1.0:
        return mcolors.PowerNorm(gamma=mapping.gamma, vmin=vmin, vmax=vmax)
    return mcolors.Normalize(vmin=vmin, vmax=vmax)
