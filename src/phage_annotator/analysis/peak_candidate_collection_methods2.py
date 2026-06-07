"""Method group 2 split from peak_candidate_collection.py."""

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


class _LocalPeakCandidateCollectorMethods2:
    """Methods split from LocalPeakCandidateCollector."""

    def _uncertainty_from_components(self, components: dict[str, float], *, candidate_class: str = "") -> tuple[float, str]:
        """Summarize uncertainty without discarding scientific evidence."""
        reasons: list[str] = []
        low_signal = float(components.get("snr", 0.0)) < float(components.get("image_snr_threshold", 1.5))
        if low_signal:
            reasons.append("low_signal")
        if float(components.get("spatial_quality", 1.0)) < 0.9:
            reasons.append("dense_region_ambiguity")
        if float(components.get("control_contradiction_score", 0.0)) > 0.25:
            reasons.append("control_contradiction")
        if float(components.get("cross_modality_consistency_score", 1.0)) < 0.5:
            reasons.append("modality_disagreement")
        if candidate_class == "conflict":
            reasons.append("conflict_with_existing_annotation")
        uncertainty_score = min(
            1.0,
            max(
                0.0,
                0.35 * (1.0 - min(1.0, float(components.get("snr", 0.0)) / 6.0))
                + 0.35 * (1.0 - min(1.0, float(components.get("spatial_quality", 1.0))))
                + 0.15 * min(1.0, float(components.get("control_contradiction_score", 0.0)))
                + 0.15 * (1.0 - min(1.0, float(components.get("cross_modality_consistency_score", 1.0)))),
            ),
        )
        reason = ",".join(dict.fromkeys(reasons))
        return float(uncertainty_score), reason
