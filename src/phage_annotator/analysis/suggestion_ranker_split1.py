"""Split definitions from suggestion_ranker.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

from phage_annotator.core.annotation import PointSuggestion









FEATURE_NAMES = (
    "score",
    "peak",
    "snr",
    "local_contrast",
    "local_std",
    "amplitude_fit",
    "sigma_fit",
    "residual_fit",
    "log_response",
    "distance_to_nearest_accepted",
    "distance_to_recent_reject",
    "border_proximity",
    "local_background",
    "local_density",
    "spatial_quality",
    "nn_dist_1",
    "nn_dist_2",
    "nn_dist_3",
    "stack_snr",
    "stack_contrast",
    "temporal_persistence",
    "cross_modality_consistency_score",
    "control_contradiction_score",
    "uncertainty_score",
    "strategy_raw",
    "strategy_corrected",
    "strategy_consensus",
    "strategy_channel_rule",
)








from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

from phage_annotator.core.annotation import PointSuggestion


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Handle the sigmoid helper flow."""
    clipped = np.clip(x, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))

def calibration_bins(
    probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    n_bins: int = 8,
) -> list[dict[str, float]]:
    """Return reliability-style bin summaries for calibration monitoring."""
    probs = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    y = np.asarray(labels, dtype=np.float64).reshape(-1)
    if probs.size == 0 or y.size == 0 or probs.size != y.size:
        return []
    edges = np.linspace(0.0, 1.0, int(max(2, n_bins)) + 1, dtype=np.float64)
    rows: list[dict[str, float]] = []
    for idx in range(len(edges) - 1):
        lo = float(edges[idx])
        hi = float(edges[idx + 1])
        if idx == len(edges) - 2:
            mask = (probs >= lo) & (probs <= hi)
        else:
            mask = (probs >= lo) & (probs < hi)
        if not np.any(mask):
            rows.append({"bin_lo": lo, "bin_hi": hi, "count": 0.0, "mean_pred": 0.0, "empirical": 0.0, "gap": 0.0})
            continue
        mean_pred = float(np.mean(probs[mask]))
        empirical = float(np.mean(y[mask]))
        rows.append(
            {
                "bin_lo": lo,
                "bin_hi": hi,
                "count": float(np.sum(mask)),
                "mean_pred": mean_pred,
                "empirical": empirical,
                "gap": float(abs(mean_pred - empirical)),
            }
        )
    return rows

def expected_calibration_error(
    probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    n_bins: int = 8,
) -> float:
    """Compute expected calibration error from reliability-style bins."""
    bins = calibration_bins(probabilities, labels, n_bins=n_bins)
    total = float(sum(row["count"] for row in bins))
    if total <= 0.0:
        return 0.0
    return float(sum((row["count"] / total) * row["gap"] for row in bins))

def feature_vector_from_suggestion(suggestion: PointSuggestion) -> np.ndarray:
    """Extract stable numeric features from one proposal."""
    comp = dict(getattr(suggestion, "score_components", {}) or {})
    strategy = str(getattr(suggestion, "source_modality", "raw")).lower()
    is_raw = 1.0 if strategy == "raw" else 0.0
    is_corrected = 1.0 if strategy == "corrected" else 0.0
    is_consensus = 1.0 if strategy == "consensus" else 0.0
    is_channel_rule = 1.0 if strategy.startswith("channel_") else 0.0
    return np.asarray(
        [
            float(getattr(suggestion, "score", 0.0)),
            float(comp.get("peak", 0.0)),
            float(comp.get("snr", 0.0)),
            float(comp.get("local_contrast", 0.0)),
            float(comp.get("local_std", 0.0)),
            float(comp.get("amplitude_fit", 0.0)),
            float(comp.get("sigma_fit", 1.0)),
            float(comp.get("residual_fit", 1.0)),
            float(comp.get("log_response", 0.0)),
            float(getattr(suggestion, "meta", {}).get("distance_to_nearest_accepted", 0.0)),
            float(getattr(suggestion, "meta", {}).get("distance_to_recent_reject", 0.0)),
            float(getattr(suggestion, "meta", {}).get("border_proximity", 0.0)),
            float(comp.get("local_background", 0.0)),
            float(getattr(suggestion, "meta", {}).get("local_density", comp.get("local_density", 0.0))),
            float(comp.get("spatial_quality", 1.0)),
            float(comp.get("nn_dist_1", 0.0)),
            float(comp.get("nn_dist_2", 0.0)),
            float(comp.get("nn_dist_3", 0.0)),
            float(comp.get("stack_snr", 0.0)),
            float(comp.get("stack_contrast", 0.0)),
            float(comp.get("temporal_persistence", 0.0)),
            float(
                getattr(suggestion, "cross_modality_consistency_score", None)
                if getattr(suggestion, "cross_modality_consistency_score", None) is not None
                else comp.get("cross_modality_consistency_score", 1.0)
            ),
            float(
                getattr(suggestion, "control_contradiction_score", None)
                if getattr(suggestion, "control_contradiction_score", None) is not None
                else comp.get("control_contradiction_score", 0.0)
            ),
            float(
                getattr(suggestion, "uncertainty_score", None)
                if getattr(suggestion, "uncertainty_score", None) is not None
                else getattr(suggestion, "meta", {}).get("uncertainty_score", 0.0)
            ),
            is_raw,
            is_corrected,
            is_consensus,
            is_channel_rule,
        ],
        dtype=np.float64,
    )
