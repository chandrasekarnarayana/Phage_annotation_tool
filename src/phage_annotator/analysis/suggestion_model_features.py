"""Extracted method group 4 for LocalPeakSuggestionModel."""

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


class SuggestionModelFeaturesMixin:
    """Method group 4 extracted from LocalPeakSuggestionModel."""

    def _extract_stack_features(
        self,
        stack: np.ndarray,
        y: float,
        x: float,
    ) -> tuple[float, float, float, float]:
        """Extract enhanced features using full stack at a given (y, x) location.
        
        Computes SNR and other statistics by looking at intensity across all frames
        at a single xy position, providing more robust feature estimation.
        
        Parameters
        ----------
        stack : np.ndarray
            3D array of shape (T, H, W) or (Z, H, W)
        y : float
            Y coordinate
        x : float
            X coordinate
            
        Returns
        -------
        amplitude : float
            Mean peak value across frames
        snr : float
            Signal-to-noise ratio from stack statistics
        stack_contrast : float
            Contrast relative to background across stack
        stack_std : float
            Standard deviation of peak values across frames
        """
        y_int, x_int = int(round(y)), int(round(x))
        h, w = stack.shape[1], stack.shape[2]
        
        # Clamp to valid range
        if y_int < 0 or y_int >= h or x_int < 0 or x_int >= w:
            return 0.0, 0.0, 0.0, 0.0
        
        # Extract values at (y, x) across all frames
        values = stack[:, y_int, x_int].astype(np.float64)
        
        if not np.isfinite(values).any():
            return 0.0, 0.0, 0.0, 0.0
        
        # Compute statistics
        peak_mean = float(np.nanmean(values))
        peak_std = float(np.nanstd(values))
        
        # Estimate background from local neighborhood median (across stack mean)
        stack_mean = np.nanmean(stack.astype(np.float64), axis=0)
        r = 5
        y0, y1 = max(0, y_int - r), min(h, y_int + r + 1)
        x0, x1 = max(0, x_int - r), min(w, x_int + r + 1)
        
        patch = stack_mean[y0:y1, x0:x1]
        if patch.size > 0:
            baseline = float(np.nanmedian(patch))
        else:
            baseline = float(np.nanmedian(stack_mean))
        
        baseline_std = float(np.nanstd(stack_mean[stack_mean != baseline]))
        if baseline_std < 1e-8:
            baseline_std = 1e-8
        
        # SNR: (signal - baseline) / noise
        snr = (peak_mean - baseline) / baseline_std if baseline_std > 0 else 0.0
        snr = float(max(0.0, snr))
        
        # Contrast: relative height above background
        contrast = (peak_mean - baseline) / (abs(baseline) + 1e-8)
        contrast = float(max(0.0, contrast))
        
        return peak_mean, snr, contrast, peak_std
    @staticmethod
    def _stable_sort_key(suggestion: PointSuggestion) -> tuple[float, int, int, float, float, str]:
        """Deterministic ordering for reproducible proposal sets."""
        return (
            -float(getattr(suggestion, "score", 0.0)),
            int(getattr(suggestion, "t", 0)),
            int(getattr(suggestion, "z", 0)),
            float(getattr(suggestion, "y", 0.0)),
            float(getattr(suggestion, "x", 0.0)),
            str(getattr(suggestion, "suggestion_id", "")),
        )
    @staticmethod
    def _roi_area(arr_shape: tuple[int, int], roi_shape: str, roi_rect: tuple[float, float, float, float]) -> float:
        """Estimate effective ROI area for density normalization."""
        height, width = arr_shape
        if roi_shape == "box":
            _, _, w, h = roi_rect
            return max(1.0, float(w) * float(h))
        if roi_shape == "circle":
            _, _, r, _ = roi_rect
            return max(1.0, float(np.pi) * float(r) * float(r))
        return max(1.0, float(height) * float(width))
    @staticmethod
    def _uncertainty_from_components(components: dict[str, float], *, candidate_class: str = "") -> tuple[float, str]:
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
