"""Unit tests for lightweight suggestion ranker and calibration."""

from __future__ import annotations

import numpy as np

from phage_annotator.analysis.suggestion_ranker import (
    LightweightSuggestionRanker,
    dataset_metrics_from_suggestions,
    feature_vector_from_suggestion,
)
from phage_annotator.core.annotation import PointSuggestion


def test_ranker_fit_and_predict_probability() -> None:
    ranker = LightweightSuggestionRanker()
    x = np.asarray(
        [
            [0.1, 0.2, 0.1, 0.1, 0.4],
            [0.2, 0.3, 0.1, 0.2, 0.4],
            [0.8, 0.9, 0.7, 0.5, 0.2],
            [0.9, 0.95, 0.8, 0.6, 0.2],
        ],
        dtype=np.float64,
    )
    y = np.asarray([0.0, 0.0, 1.0, 1.0], dtype=np.float64)
    ranker.fit(x, y, epochs=300)
    probs = ranker.predict_p_accept(x)
    assert probs.shape == (4,)
    assert probs[3] > probs[0]


def test_ranker_applies_calibrated_confidence_to_suggestions() -> None:
    ranker = LightweightSuggestionRanker()
    suggestions = [
        PointSuggestion(0, "img", 0, 0, 2.0, 2.0, score=0.1, score_components={"peak": 0.2, "snr": 0.1, "local_contrast": 0.1, "local_std": 0.4}),
        PointSuggestion(0, "img", 0, 0, 3.0, 3.0, score=0.9, score_components={"peak": 0.95, "snr": 0.8, "local_contrast": 0.6, "local_std": 0.2}),
    ]
    x = np.vstack([feature_vector_from_suggestion(s) for s in suggestions])
    y = np.asarray([0.0, 1.0], dtype=np.float64)
    ranker.fit(x, y, epochs=200)
    out = ranker.apply_to_suggestions(suggestions)
    assert float(out[1].score) > float(out[0].score)
    assert "p_accept" in out[0].meta
    assert out[0].confidence == float(out[0].meta["p_accept"])
    assert feature_vector_from_suggestion(out[0]).shape[0] == len(ranker.weights)


def test_dataset_metrics_contains_requested_fields() -> None:
    rows = [
        PointSuggestion(0, "a", 0, 0, 1, 1, score=0.8, status="accepted"),
        PointSuggestion(0, "a", 0, 0, 2, 2, score=0.7, status="rejected"),
        PointSuggestion(0, "a", 0, 0, 3, 3, score=0.3, status="proposed"),
    ]
    metrics = dataset_metrics_from_suggestions(rows, threshold=0.5, baseline_points_per_min=40)
    assert "precision_at_threshold" in metrics
    assert "acceptance_rate" in metrics
    assert "estimated_time_saved_minutes" in metrics
