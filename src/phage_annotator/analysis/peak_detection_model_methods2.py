"""Method group 2 split from peak_detection_model.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.analysis.peak_candidate_collection import LocalPeakCandidateCollector


@dataclass

class _LocalPeakSuggestionModelMethods2:
    """Methods split from LocalPeakSuggestionModel."""

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
        """Detect candidates on mean projection, refine using full stack."""
        stack = np.asarray(image_stack)
        if stack.ndim != 3 or stack.size == 0:
            return []
        mean_projection = np.nanmean(stack.astype(np.float64), axis=0)
        if mean_projection.size == 0:
            return []
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
                    stack, float(suggestion.y), float(suggestion.x),
                )
                suggestion.score_components["stack_amplitude"] = float(amp)
                suggestion.score_components["stack_snr"] = float(stack_snr)
                suggestion.score_components["stack_contrast"] = float(stack_contrast)
                suggestion.score_components["stack_std"] = float(stack_std)
                suggestion.score_components["temporal_persistence"] = float(
                    max(0.0, min(1.0, amp / (amp + stack_std + 1e-8)))
                )
        spatial_filtered = self._spatial_filtering(
            raw_candidates, mean_projection.shape, roi_shape=roi_shape, roi_rect=roi_rect,
        )
        return sorted(
            [s for s in spatial_filtered if float(s.score) >= float(threshold_min_score)],
            key=self._stable_sort_key,
        )

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
        """Predict point suggestions for one 2D image slice."""
        arr = np.asarray(image_slice)
        if arr.ndim != 2 or arr.size == 0:
            return []
        strategy_key = str(strategy or "raw").strip().lower()
        raw_candidates = self._collect_candidates(
            arr, threshold_quantile=self.threshold_quantile,
            source_modality="raw", image_id=image_id, image_name=image_name,
            t=t, z=z, label=label, roi_id=roi_id, roi_shape=roi_shape, roi_rect=roi_rect,
        )
        corrected = self._corrected_image(arr)
        corrected_candidates = self._collect_candidates(
            corrected, threshold_quantile=self.threshold_quantile,
            source_modality="corrected", image_id=image_id, image_name=image_name,
            t=t, z=z, label=label, roi_id=roi_id, roi_shape=roi_shape, roi_rect=roi_rect,
        )
        if strategy_key in ("corrected",):
            selected = corrected_candidates
        elif strategy_key in ("consensus",):
            selected = self._consensus(raw_candidates, corrected_candidates, float(self.min_distance_px))
        else:
            selected = raw_candidates
        nms_selected = self._nms(selected)
        spatial_filtered = self._spatial_filtering(
            nms_selected, arr.shape, roi_shape=roi_shape, roi_rect=roi_rect,
        )
        return sorted(
            [s for s in spatial_filtered if float(s.score) >= float(threshold_min_score)],
            key=self._stable_sort_key,
        )
