"""Candidate collection and scoring logic for the local-peak suggestion model.

Contains the _collect_candidates method that scans a 2D image for candidate
peaks, extracts rich feature sets for each, and applies image-aware scoring.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter, gaussian_laplace, sobel

try:
    from skimage.feature import (
        graycomatrix,
        graycoprops,
        structure_tensor,
        hessian_matrix,
        hessian_matrix_eigvals,
    )
except ImportError:
    graycomatrix = None
    graycoprops = None
    structure_tensor = None
    hessian_matrix = None
    hessian_matrix_eigvals = None

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.peak_feature_extraction import LocalPeakFeatureExtractor


from phage_annotator.analysis.peak_candidate_collection_methods1 import _LocalPeakCandidateCollectorMethods1
from phage_annotator.analysis.peak_candidate_collection_methods2 import _LocalPeakCandidateCollectorMethods2

class LocalPeakCandidateCollector(_LocalPeakCandidateCollectorMethods1, _LocalPeakCandidateCollectorMethods2, LocalPeakFeatureExtractor):
    """Mixin: candidate collection and image-aware scoring."""

    pass
