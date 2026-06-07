"""Candidate collection façade for the local peak detector."""

from __future__ import annotations

import numpy as np

from phage_annotator.analysis.candidate_feature_rows import (
    CandidateScanContext,
    collect_feature_rows,
    finalize_feature_rows,
)
from phage_annotator.core.annotation import PointSuggestion


class _LocalPeakCandidateCollectorMethods1:
    """Methods split from LocalPeakCandidateCollector."""

    def _collect_candidates(
        self,
        arr: np.ndarray,
        *,
        threshold_quantile: float,
        source_modality: str,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        roi_id: str | None,
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> list[PointSuggestion]:
        """Collect, feature, score, and return local peak suggestions."""
        # Keep all call-site metadata immutable while shared helpers scan pixels.
        ctx = CandidateScanContext(
            threshold_quantile=threshold_quantile,
            source_modality=source_modality,
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        rows = collect_feature_rows(self, arr, ctx)
        return finalize_feature_rows(self, rows)
