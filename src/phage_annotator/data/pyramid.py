"""Multi-resolution pyramid helpers for large 2D frames.

Pyramid levels are generated lazily using mean pooling to preserve intensity
statistics better than naive subsampling. This reduces redraw cost during
interactive zooming/panning without changing stored annotation coordinates.
"""

from __future__ import annotations

import numpy as np


def pyramid_level_factor(level: int) -> int:
    """Return the integer downsample factor for a pyramid level."""
    if level <= 0:
        return 1
    return 2 ** int(level)


def downsample_mean_pool(frame: np.ndarray, factor: int) -> np.ndarray:
    """Downsample a 2D frame using mean pooling.

    Parameters
    ----------
    frame : numpy.ndarray
        2D image array (Y, X).
    factor : int
        Downsample factor (e.g., 2, 4, 8).

    Returns
    -------
    numpy.ndarray
        Downsampled frame with mean pooling applied.
    """
    factor = int(max(1, factor))
    if factor == 1:
        return frame
    h, w = frame.shape[:2]
    h_trim = (h // factor) * factor
    w_trim = (w // factor) * factor
    if h_trim == 0 or w_trim == 0:
        return frame
    trimmed = frame[:h_trim, :w_trim]
    pooled = trimmed.reshape(h_trim // factor, factor, w_trim // factor, factor).mean(
        axis=(1, 3), dtype=np.float32
    )
    return pooled
