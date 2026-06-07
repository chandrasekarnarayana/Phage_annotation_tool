"""Pure analysis helpers for background jobs (no Qt dependencies).

Functions in this module are safe to run in background threads. They operate
on numpy arrays and plain data structures, avoiding any Qt or GUI state.

Conventions
-----------
- Arrays are expected in (T, Z, Y, X) order.
- Coordinates are full-resolution image coordinates unless explicitly cropped.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Tuple

import numpy as np
import tifffile as tif
from scipy.ndimage import maximum_filter
from scipy.optimize import curve_fit

from phage_annotator.io import standardize_axes

_logger = logging.getLogger(__name__)


from phage_annotator.algorithms.roi_analysis import (
    roi_mask_for_shape,
    roi_mask_for_polygon,
    roi_mask_from_points,
    roi_mean_timeseries,
    compute_roi_mean_for_path,
    fit_bleach_curve,
    apply_crop_rect,
    map_point_to_crop,
    compute_bleach_means,
    roi_stats,
)
from phage_annotator.algorithms.projection_analysis import (
    compute_mean_std,
    compute_projections,
    compute_projection,
    compute_auto_window,
    mad_sigma,
)
from phage_annotator.algorithms.peak_detection import (
    local_maxima,
    gaussian_2d,
    fit_gaussian_2d,
)
