"""Model-in-the-loop point suggestion adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter, gaussian_laplace, sobel

try:
    from skimage.feature import graycomatrix, graycoprops, structure_tensor, hessian_matrix, hessian_matrix_eigvals
except ImportError:
    # Fallback if skimage not available
    graycomatrix = None
    graycoprops = None
    structure_tensor = None
    hessian_matrix = None
    hessian_matrix_eigvals = None

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.suggestion_model_base import SuggestionModelBaseMixin
from phage_annotator.analysis.suggestion_model_candidates import SuggestionModelCandidatesMixin
from phage_annotator.analysis.suggestion_model_features import SuggestionModelFeaturesMixin
from phage_annotator.analysis.suggestion_model_filtering import SuggestionModelFilteringMixin
from phage_annotator.analysis.suggestion_model_predict import SuggestionModelPredictMixin




class SuggestionModel(Protocol):
    """Interface for proposal models used by assisted annotation."""

    model_name: str

    def predict(
        self,
        image_slice: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
    ) -> List[PointSuggestion]:
        """Generate candidate point suggestions for one 2D slice."""







@dataclass
class LocalPeakSuggestionModel(
    SuggestionModelBaseMixin,
    SuggestionModelCandidatesMixin,
    SuggestionModelFilteringMixin,
    SuggestionModelFeaturesMixin,
    SuggestionModelPredictMixin,
):
    """Fast baseline model using local maxima as candidate points.

This is the first-level assist for coarse detection. Features extracted here
can be used by downstream ML models (e.g., LightGBM) for fine-tuning."""

    min_distance_px: int = 6
    max_points: int | None = None  # Backward-compatible API only; generation is no longer capped.
    threshold_quantile: float = 0.995
    anisotropic_radius_x: float | None = None
    anisotropic_radius_y: float | None = None
    scale_sigma: float = 1.0
    model_name: str = "local_peaks"
    # Spatial filtering parameters (tunable per experiment)
    enable_spatial_filtering: bool = True
    spatial_density_penalty: float = 0.6  # Penalty multiplier for dense clusters (0.6 = 40% penalty)
    spatial_isolation_penalty: float = 0.9  # Penalty for isolated spots (0.9 = 10% penalty)
    spatial_typical_bonus: float = 1.15  # Bonus for well-spaced spots (1.15 = 15% bonus)
    spatial_nn_isolation_factor: float = 2.5  # Factor above median NN to consider isolated
    spatial_density_cluster_factor: float = 3.0  # Factor above expected density for clustering
    # Adaptive thresholding parameters
    score_drop_percentile: float = 0.10  # Percentile of score drops to consider significant (0.10 = top 10%)
    min_relative_score_drop: float = 0.03  # Minimum relative score drop to consider (3%)
    expected_count_hint: int | None = 100  # Preserved for compatibility; no longer used to cap/filter proposals.
    expected_count_tolerance: float = 0.5  # Tolerance around hint (50% = ±50%)
    # Performance
    nms_intermediate_limit: int = 300  # Intermediate limit for NMS performance (reduced from 1000)





def summarize_suggestion_feedback(
    suggestions: Iterable[PointSuggestion],
    accepted_ids: set[str],
) -> dict:
    """Compute simple acceptance summary for reporting."""
    ids = [s.suggestion_id for s in suggestions]
    accepted = sum(1 for sid in ids if sid in accepted_ids)
    total = len(ids)
    return {
        "total": total,
        "accepted": accepted,
        "rejected": max(0, total - accepted),
        "accept_rate": (accepted / total) if total else 0.0,
    }
