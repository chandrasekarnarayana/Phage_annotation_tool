"""Extracted method group 3 for LocalPeakSuggestionModel."""

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


@dataclass


class SuggestionModelFilteringMixin:
    """Method group 3 extracted from LocalPeakSuggestionModel."""

    def _spatial_filtering(
        self,
        candidates: list[PointSuggestion],
        arr_shape: tuple[int, int],
        *,
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> list[PointSuggestion]:
        """Enrich candidates with density/spatial evidence without suppressing them.

        Spatial context is scientifically informative, but it should not be used
        to hide real structure. This layer adds density, spacing, and crowding
        evidence to each proposal and adjusts score only as a soft probabilistic
        prior. The candidate set itself remains intact.
        """
        if not candidates or not self.enable_spatial_filtering:
            return candidates
        
        n = len(candidates)
        if n < 3:
            return candidates  # Too few to apply spatial stats
        
        # Extract coordinates and scores
        coords = np.array([[float(c.x), float(c.y)] for c in candidates])
        scores = np.array([float(c.score) for c in candidates])
        
        # 1. Calculate multi-neighbor distances (1st, 2nd, 3rd nearest neighbors)
        nn_distances_1 = np.full(n, np.inf)
        nn_distances_2 = np.full(n, np.inf)
        nn_distances_3 = np.full(n, np.inf)
        
        for i in range(n):
            dists = np.sqrt(np.sum((coords - coords[i:i+1]) ** 2, axis=1))
            dists[i] = np.inf  # Exclude self
            sorted_dists = np.sort(dists)
            nn_distances_1[i] = sorted_dists[0] if len(sorted_dists) > 0 else np.inf
            nn_distances_2[i] = sorted_dists[1] if len(sorted_dists) > 1 else np.inf
            nn_distances_3[i] = sorted_dists[2] if len(sorted_dists) > 2 else np.inf
        
        # 2. Identify expected spot spacing from median 1st NN distance
        median_nn = np.median(nn_distances_1[np.isfinite(nn_distances_1)])
        
        # 3. Calculate local density for each point (neighbors within 3x median distance)
        search_radius = max(median_nn * 3.0, float(self.min_distance_px) * 2.0)
        local_density = np.zeros(n)
        for i in range(n):
            dists = np.sqrt(np.sum((coords - coords[i:i+1]) ** 2, axis=1))
            local_density[i] = np.sum(dists < search_radius) - 1  # Exclude self
        
        # 4. Calculate spatial quality score for each point (soft evidence only)
        area = self._roi_area(arr_shape, roi_shape, roi_rect)
        expected_density = n / area * (np.pi * search_radius ** 2)
        
        spatial_quality = np.ones(n)
        
        # Penalize overly dense regions (likely artifacts/noise clusters)
        overdense_mask = local_density > expected_density * self.spatial_density_cluster_factor
        spatial_quality[overdense_mask] *= self.spatial_density_penalty
        
        # Penalty for isolated points (might be noise)
        isolated_mask = nn_distances_1 > median_nn * self.spatial_nn_isolation_factor
        spatial_quality[isolated_mask] *= self.spatial_isolation_penalty
        
        # Bonus for points with typical spacing (within 70-150% of median)
        typical_mask = (nn_distances_1 >= median_nn * 0.7) & (nn_distances_1 <= median_nn * 1.5)
        spatial_quality[typical_mask] *= self.spatial_typical_bonus
        
        # 5. Update scores with spatial quality and add features for downstream ML.
        # Density and spacing affect confidence, not candidate inclusion.
        adjusted_scores = np.clip(scores * spatial_quality, 0.0, 1.0)

        for i, candidate in enumerate(candidates):
            candidate.score_components['nn_dist_1'] = float(nn_distances_1[i])
            candidate.score_components['nn_dist_2'] = float(nn_distances_2[i])
            candidate.score_components['nn_dist_3'] = float(nn_distances_3[i])
            candidate.score_components['local_density'] = float(local_density[i])
            candidate.score_components['spatial_quality'] = float(spatial_quality[i])
            candidate.score_components['expected_density'] = float(expected_density)
            candidate.score_components['median_nn'] = float(median_nn)
            candidate.density_context = {
                "local_density": float(local_density[i]),
                "expected_density": float(expected_density),
                "median_nn": float(median_nn),
                "nn_dist_1": float(nn_distances_1[i]),
                "nn_dist_2": float(nn_distances_2[i]),
                "nn_dist_3": float(nn_distances_3[i]),
                "roi_area": float(area),
                "search_radius": float(search_radius),
            }
            crowding_ratio = float(local_density[i] / max(expected_density, 1e-8))
            uncertainty_score, uncertainty_reason = self._uncertainty_from_components(
                candidate.score_components,
            )
            if crowding_ratio > 1.0 and "dense_region_ambiguity" not in uncertainty_reason:
                uncertainty_reason = ",".join(filter(None, [uncertainty_reason, "dense_region_ambiguity"]))
            candidate.uncertainty_score = float(max(uncertainty_score, min(1.0, crowding_ratio / 4.0)))
            candidate.uncertainty_reason = str(uncertainty_reason)
            candidate.meta["uncertainty_score"] = float(candidate.uncertainty_score)
            candidate.meta["uncertainty_reason"] = str(candidate.uncertainty_reason)
            candidate.meta["density_context"] = dict(candidate.density_context)
            candidate.score = float(adjusted_scores[i])

        return candidates
    def _nms(self, candidates: list[PointSuggestion]) -> list[PointSuggestion]:
        """Non-maximum suppression with intermediate limit for performance."""
        radius_x = float(self.anisotropic_radius_x or self.min_distance_px)
        radius_y = float(self.anisotropic_radius_y or self.min_distance_px)
        if radius_x <= 0 or radius_y <= 0:
            return list(candidates)
        picked: list[PointSuggestion] = []
        for suggestion in sorted(candidates, key=self._stable_sort_key):
            keep = True
            for prev in picked:
                dx = (float(prev.x) - float(suggestion.x)) / radius_x
                dy = (float(prev.y) - float(suggestion.y)) / radius_y
                if dx * dx + dy * dy < 1.0:
                    keep = False
                    break
            if keep:
                picked.append(suggestion)
        return picked
    @staticmethod
    def _consensus(raw: list[PointSuggestion], corrected: list[PointSuggestion], radius: float) -> list[PointSuggestion]:
        """Handle the consensus helper flow."""
        if not raw or not corrected:
            return []
        out: list[PointSuggestion] = []
        radius2 = float(max(1.0, radius) ** 2)
        for a in raw:
            for b in corrected:
                dx = float(a.x) - float(b.x)
                dy = float(a.y) - float(b.y)
                if dx * dx + dy * dy > radius2:
                    continue
                merged = PointSuggestion(
                    image_id=a.image_id,
                    image_name=a.image_name,
                    t=a.t,
                    z=a.z,
                    y=float((a.y + b.y) / 2.0),
                    x=float((a.x + b.x) / 2.0),
                    score=float((a.score + b.score) / 2.0),
                    label=a.label,
                    source_model=a.source_model,
                    source_modality="consensus",
                    scale_sigma=a.scale_sigma,
                    psf_radius=a.psf_radius,
                    roi_id=a.roi_id,
                    score_components={
                        "raw_score": float(a.score),
                        "corrected_score": float(b.score),
                    },
                    meta={"consensus": True},
                )
                out.append(merged)
                break
        return out
