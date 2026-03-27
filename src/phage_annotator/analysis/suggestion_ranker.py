"""Lightweight proposal ranking and calibration for assisted annotation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

from phage_annotator.core.annotation import PointSuggestion


def _sigmoid(x: np.ndarray) -> np.ndarray:
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


@dataclass
class LightweightSuggestionRanker:
    """Simple logistic ranker with optional Platt-style calibration."""

    weights: np.ndarray = field(default_factory=lambda: np.zeros(len(FEATURE_NAMES), dtype=np.float64))
    bias: float = 0.0
    mean: np.ndarray = field(default_factory=lambda: np.zeros(len(FEATURE_NAMES), dtype=np.float64))
    std: np.ndarray = field(default_factory=lambda: np.ones(len(FEATURE_NAMES), dtype=np.float64))
    calibrator_a: float = 1.0
    calibrator_b: float = 0.0
    trained_samples: int = 0
    calibration_ece: float = 0.0
    calibration_brier: float = 0.0
    calibration_bins_payload: list[dict[str, float]] = field(default_factory=list)

    def fit(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        sample_weight: np.ndarray | None = None,
        *,
        lr: float = 0.1,
        epochs: int = 250,
        l2: float = 1e-3,
    ) -> None:
        """Train base logistic model and fit Platt calibrator."""
        x = np.asarray(features, dtype=np.float64)
        y = np.asarray(labels, dtype=np.float64).reshape(-1)
        if x.ndim != 2 or x.shape[0] == 0 or x.shape[0] != y.shape[0]:
            return
        if len(np.unique(y)) < 2:
            return
        if x.shape[1] != self.weights.shape[0]:
            self.weights = np.zeros(x.shape[1], dtype=np.float64)
            self.mean = np.zeros(x.shape[1], dtype=np.float64)
            self.std = np.ones(x.shape[1], dtype=np.float64)
        wgt = (
            np.asarray(sample_weight, dtype=np.float64).reshape(-1)
            if sample_weight is not None
            else np.ones(x.shape[0], dtype=np.float64)
        )
        if wgt.shape[0] != x.shape[0]:
            wgt = np.ones(x.shape[0], dtype=np.float64)
        wgt = np.clip(wgt, 1e-6, 1e6)
        wgt = wgt / float(np.mean(wgt))
        self.mean = np.nanmean(x, axis=0)
        self.std = np.nanstd(x, axis=0)
        self.std[self.std < 1e-8] = 1.0
        xn = (x - self.mean) / self.std

        w = np.asarray(self.weights, dtype=np.float64).copy()
        b = float(self.bias)
        n = float(xn.shape[0])
        for _ in range(int(max(1, epochs))):
            logits = xn @ w + b
            probs = _sigmoid(logits)
            err = probs - y
            weighted_err = err * wgt
            grad_w = (xn.T @ weighted_err) / n + l2 * w
            grad_b = float(np.mean(weighted_err))
            w -= lr * grad_w
            b -= lr * grad_b
        self.weights = w
        self.bias = b
        self.trained_samples = int(x.shape[0])

        # Platt scaling on logits.
        logits = xn @ self.weights + self.bias
        a = float(self.calibrator_a)
        c = float(self.calibrator_b)
        for _ in range(200):
            z = a * logits + c
            p = _sigmoid(z)
            e = (p - y) * wgt
            grad_a = float(np.mean(e * logits))
            grad_c = float(np.mean(e))
            a -= 0.05 * grad_a
            c -= 0.05 * grad_c
        self.calibrator_a = a
        self.calibrator_b = c
        calibrated = self.predict_p_accept(x)
        self.calibration_ece = float(expected_calibration_error(calibrated, y, n_bins=8))
        self.calibration_brier = float(np.mean((calibrated - y) ** 2))
        self.calibration_bins_payload = calibration_bins(calibrated, y, n_bins=8)

    def predict_logits(self, features: np.ndarray) -> np.ndarray:
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        xn = (x - self.mean) / self.std
        return xn @ self.weights + float(self.bias)

    def predict_p_accept(self, features: np.ndarray) -> np.ndarray:
        logits = self.predict_logits(features)
        calibrated = self.calibrator_a * logits + self.calibrator_b
        return _sigmoid(calibrated)

    def apply_to_suggestions(self, suggestions: Sequence[PointSuggestion]) -> list[PointSuggestion]:
        if not suggestions:
            return []
        feats = np.vstack([feature_vector_from_suggestion(s) for s in suggestions])
        probs = self.predict_p_accept(feats)
        out = list(suggestions)
        for idx, suggestion in enumerate(out):
            suggestion.meta.setdefault(
                "generator_score",
                float(getattr(suggestion, "score", getattr(suggestion, "confidence", 0.0))),
            )
            p_accept = float(probs[idx])
            suggestion.meta["p_accept"] = p_accept
            suggestion.meta["confidence"] = p_accept
            suggestion.meta["confidence_available"] = True
            suggestion.score = p_accept
        return out

    def to_dict(self) -> dict:
        return {
            "weights": self.weights.tolist(),
            "bias": float(self.bias),
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "calibrator_a": float(self.calibrator_a),
            "calibrator_b": float(self.calibrator_b),
            "trained_samples": int(self.trained_samples),
            "calibration_ece": float(self.calibration_ece),
            "calibration_brier": float(self.calibration_brier),
            "calibration_bins_payload": list(self.calibration_bins_payload),
            "feature_names": list(FEATURE_NAMES),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "LightweightSuggestionRanker":
        ranker = cls()
        if not isinstance(payload, dict):
            return ranker
        weights = payload.get("weights")
        if isinstance(weights, list) and len(weights) == len(FEATURE_NAMES):
            ranker.weights = np.asarray(weights, dtype=np.float64)
        ranker.bias = float(payload.get("bias", 0.0))
        mean = payload.get("mean")
        if isinstance(mean, list) and len(mean) == len(FEATURE_NAMES):
            ranker.mean = np.asarray(mean, dtype=np.float64)
        std = payload.get("std")
        if isinstance(std, list) and len(std) == len(FEATURE_NAMES):
            ranker.std = np.asarray(std, dtype=np.float64)
            ranker.std[ranker.std < 1e-8] = 1.0
        ranker.calibrator_a = float(payload.get("calibrator_a", 1.0))
        ranker.calibrator_b = float(payload.get("calibrator_b", 0.0))
        ranker.trained_samples = int(payload.get("trained_samples", 0))
        ranker.calibration_ece = float(payload.get("calibration_ece", 0.0))
        ranker.calibration_brier = float(payload.get("calibration_brier", 0.0))
        bins = payload.get("calibration_bins_payload")
        if isinstance(bins, list):
            ranker.calibration_bins_payload = [dict(row) for row in bins if isinstance(row, dict)]
        return ranker


def dataset_metrics_from_suggestions(
    suggestions: Iterable[PointSuggestion],
    *,
    threshold: float = 0.5,
    baseline_points_per_min: float = 50.0,
) -> dict:
    """Compute explicit proposal metrics for dashboarding."""
    rows = list(suggestions)
    proposed = [s for s in rows if str(getattr(s, "status", "proposed")) in ("proposed", "accepted", "rejected")]
    accepted = [s for s in rows if str(getattr(s, "status", "")) == "accepted"]
    rejected = [s for s in rows if str(getattr(s, "status", "")) == "rejected"]
    above = [s for s in proposed if float(getattr(s, "score", 0.0)) >= float(threshold)]
    precision = (
        float(sum(1 for s in above if str(getattr(s, "status", "")) == "accepted")) / float(len(above))
        if above
        else 0.0
    )
    acceptance_rate = float(len(accepted)) / float(len(proposed)) if proposed else 0.0
    assisted_ppm = baseline_points_per_min * (1.0 + 0.5 * acceptance_rate)
    time_saved_min = (
        (float(len(accepted)) / max(1e-8, baseline_points_per_min))
        - (float(len(accepted)) / max(1e-8, assisted_ppm))
    )
    return {
        "proposed": int(len(proposed)),
        "accepted": int(len(accepted)),
        "rejected": int(len(rejected)),
        "precision_at_threshold": float(precision),
        "acceptance_rate": float(acceptance_rate),
        "estimated_time_saved_minutes": float(time_saved_min),
        "baseline_points_per_min": float(baseline_points_per_min),
        "assisted_points_per_min_estimate": float(assisted_ppm),
        "threshold": float(threshold),
    }
