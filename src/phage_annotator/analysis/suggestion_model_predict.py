"""Extracted method group 5 for LocalPeakSuggestionModel."""

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


class SuggestionModelPredictMixin:
    """Method group 5 extracted from LocalPeakSuggestionModel."""

    def predict_from_stack(
        self,
        image_stack: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        label: str,
        z_frame: int = 0,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
        refine_from_stack: bool = True,
    ) -> List[PointSuggestion]:
        """Detect candidates on mean projection, refine using full stack.
        
        Strategy:
        1. Compute mean projection across time dimension (or z if no time)
        2. Detect local maxima on clean mean image (reduced noise)
        3. For each candidate, extract features from full stack (better SNR)
        4. Return enhanced suggestions with stack-computed properties
        
        Parameters
        ----------
        image_stack : np.ndarray
            3D array of shape (T, H, W) or (Z, H, W)
        image_id : int
            Image identifier
        image_name : str
            Image name for metadata
        label : str
            Point label/class
        z_frame : int
            Z slice to use (if 3D is Z, H, W instead of T, H, W)
        strategy : str
            Detection strategy ("raw", "corrected", "consensus")
        threshold_min_score : float
            Minimum score threshold
        roi_id : str | None
            ROI identifier
        roi_shape : str
            ROI shape type
        roi_rect : tuple
            ROI rectangle coordinates
        refine_from_stack : bool
            Whether to refine features using stack (True) or single frame (False)
            
        Returns
        -------
        List[PointSuggestion]
            Scored suggestions sorted by score (descending)
        """
        stack = np.asarray(image_stack)
        if stack.ndim != 3 or stack.size == 0:
            return []
        
        # Compute mean projection (average across time or z)
        mean_projection = np.nanmean(stack.astype(np.float64), axis=0)
        
        if mean_projection.size == 0:
            return []
        
        # Detect candidates on the cleaner mean image
        # Use slightly lower threshold since noise is reduced by averaging
        lower_quantile = max(0.99, self.threshold_quantile - 0.005)
        
        raw_candidates = self._collect_candidates(
            mean_projection,
            threshold_quantile=lower_quantile,
            source_modality="mean_stack",
            image_id=image_id,
            image_name=image_name,
            t=0,
            z=z_frame,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        
        if not raw_candidates:
            return raw_candidates
        
        if refine_from_stack:
            for suggestion in raw_candidates:
                amp, stack_snr, stack_contrast, stack_std = self._extract_stack_features(
                    stack,
                    float(suggestion.y),
                    float(suggestion.x),
                )
                suggestion.score_components["stack_amplitude"] = float(amp)
                suggestion.score_components["stack_snr"] = float(stack_snr)
                suggestion.score_components["stack_contrast"] = float(stack_contrast)
                suggestion.score_components["stack_std"] = float(stack_std)
                suggestion.score_components["temporal_persistence"] = float(max(0.0, min(1.0, amp / (amp + stack_std + 1e-8))))

        spatial_filtered = self._spatial_filtering(
            raw_candidates,
            mean_projection.shape,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )

        ranked = sorted(
            [s for s in spatial_filtered if float(s.score) >= float(threshold_min_score)],
            key=self._stable_sort_key,
        )
        return ranked
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
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> List[PointSuggestion]:
        """Predict predict for the current workflow."""
        arr = np.asarray(image_slice)
        if arr.ndim != 2 or arr.size == 0:
            return []
        strategy_key = str(strategy or "raw").strip().lower()
        raw_candidates = self._collect_candidates(
            arr,
            threshold_quantile=self.threshold_quantile,
            source_modality="raw",
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        corrected = self._corrected_image(arr)
        corrected_candidates = self._collect_candidates(
            corrected,
            threshold_quantile=self.threshold_quantile,
            source_modality="corrected",
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        if strategy_key in ("corrected",):
            selected = corrected_candidates
        elif strategy_key in ("consensus",):
            selected = self._consensus(raw_candidates, corrected_candidates, float(self.min_distance_px))
        else:
            selected = raw_candidates
        nms_selected = self._nms(selected)
        
        spatial_filtered = self._spatial_filtering(
            nms_selected,
            arr.shape,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        
        ranked = sorted(
            [s for s in spatial_filtered if float(s.score) >= float(threshold_min_score)],
            key=self._stable_sort_key,
        )
        return ranked
