"""Split definitions from assist_iterative_demo.py."""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from tifffile import imread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from phage_annotator.analysis.suggestion_ranker import (
    FEATURE_NAMES,
    LightweightSuggestionRanker,
    feature_vector_from_suggestion,
)


@dataclass
class AdaptiveRetrainingStrategy:
    """Adaptive retraining based on F1 score rather than fixed decision count.
    
    F1 threshold is configurable by domain:
    - high_precision (0.85): Research, minimize false positives
    - balanced (0.75): General purpose, balanced P/R 
    - high_recall (0.65): Screening, catch everything
    """
    
    f1_threshold: float = 0.75
    min_decisions: int = 10
    domain: str = "balanced"  # high_precision, balanced, high_recall
    
    f1_history: List[float] = field(default_factory=list)
    retrain_count: int = 0
    retrain_reasons: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Auto-set threshold based on domain if not explicitly provided."""
        domain_defaults = {
            "high_precision": 0.85,
            "balanced": 0.75,
            "high_recall": 0.65,
        }
        if self.domain in domain_defaults and self.f1_threshold == 0.75:
            self.f1_threshold = domain_defaults[self.domain]
    
    def should_retrain(self, current_f1: float, reason: str = "") -> bool:
        """Check if retraining is needed based on F1 score.
        
        Only retrain if:
        1. We have minimum decisions (default 10)
        2. F1 < threshold
        3. F1 is not trending upward on its own
        """
        self.f1_history.append(current_f1)
        
        # Need minimum decisions before retraining
        if len(self.f1_history) < self.min_decisions:
            return False
        
        # Check if F1 is improving on its own (don't retrain if trend is up)
        recent_f1s = self.f1_history[-3:]
        is_improving = len(recent_f1s) >= 2 and recent_f1s[-1] >= recent_f1s[0]
        
        # Retrain only if F1 < threshold AND not improving
        needs_retrain = current_f1 < self.f1_threshold and not is_improving
        
        if needs_retrain:
            self.retrain_count += 1
            retrain_reason = f"F1={current_f1:.3f} < threshold={self.f1_threshold} ({reason})"
            self.retrain_reasons.append(retrain_reason)
        
        return needs_retrain
    
    def get_status(self) -> Dict:
        """Get retraining strategy status."""
        recent_f1 = self.f1_history[-5:] if self.f1_history else []
        return {
            'current_f1': self.f1_history[-1] if self.f1_history else 0.0,
            'avg_f1_recent': float(np.mean(recent_f1)) if recent_f1 else 0.0,
            'threshold': self.f1_threshold,
            'domain': self.domain,
            'retrain_events': self.retrain_count,
            'batches_processed': len(self.f1_history),
            'retrain_reasons': self.retrain_reasons[-3:],  # Last 3 reasons
        }

@dataclass
class IterativeTestSession:
    image_name: str
    total_suggestions: int = 0
    iterations_completed: int = 0
    decision_rows: List[Dict] = field(default_factory=list)
    batch_metrics: List[Dict] = field(default_factory=list)
    total_accepted: int = 0
    total_rejected: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    prediction_seconds: float = 0.0
    total_retrain_seconds: float = 0.0
    retrain_events: int = 0
    f1_scores: List[float] = field(default_factory=list)
    retrain_reasons: List[str] = field(default_factory=list)

def load_ground_truth(csv_path: Path) -> Dict[int, List[Dict[str, float]]]:
    """Load ground truth for the current workflow."""
    gt: Dict[int, List[Dict[str, float]]] = {}
    with csv_path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            t_col = "timepoint" if "timepoint" in row else "t"
            t = int(row.get(t_col, 0))
            y = float(row["y"])
            x = float(row["x"])
            gt.setdefault(t, []).append({"y": y, "x": x})
    return gt

def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Run the euclidean distance workflow."""
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))

def find_nearest_gt(
    suggestion_pos: Tuple[float, float], gt_points: List[Dict], distance_threshold: float = 5.0
) -> Tuple[bool, float]:
    """Find nearest gt for the current workflow."""
    if not gt_points:
        return False, float("inf")
    distances = [euclidean_distance(suggestion_pos, (g["y"], g["x"])) for g in gt_points]
    min_dist = min(distances)
    return min_dist <= distance_threshold, min_dist

def greedy_match(points: List[Tuple[float, float]], gt_points: List[Dict], threshold: float = 5.0) -> int:
    """Run the greedy match workflow."""
    unmatched = set(range(len(gt_points)))
    matched = 0
    for py, px in points:
        best_idx = None
        best_dist = float("inf")
        for idx in unmatched:
            gy, gx = float(gt_points[idx]["y"]), float(gt_points[idx]["x"])
            dist = euclidean_distance((py, px), (gy, gx))
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is not None and best_dist <= threshold:
            unmatched.remove(best_idx)
            matched += 1
    return matched

def dedupe_points(points: List[Tuple[float, float]], threshold: float = 3.0) -> List[Tuple[float, float]]:
    """Run the dedupe points workflow."""
    kept: List[Tuple[float, float]] = []
    for y, x in points:
        if all(euclidean_distance((y, x), p) > threshold for p in kept):
            kept.append((float(y), float(x)))
    return kept

def aggregate_gt_xy(ground_truth: Dict[int, List[Dict[str, float]]], dedupe_threshold: float = 3.0) -> List[Dict[str, float]]:
    """Run the aggregate gt xy workflow."""
    all_points = [(float(p["y"]), float(p["x"])) for pts in ground_truth.values() for p in pts]
    deduped = dedupe_points(all_points, threshold=dedupe_threshold)
    return [{"y": y, "x": x} for y, x in deduped]

def simulate_user_feedback(suggestions: List, gt_points: List[Dict], distance_threshold: float = 5.0) -> List[bool]:
    """Simulate user feedback for the current workflow."""
    out = []
    for s in suggestions:
        ok, _ = find_nearest_gt((float(s.y), float(s.x)), gt_points, distance_threshold)
        out.append(ok)
    return out

def compute_batch_metrics(batch: List, feedback: List[bool], gt_points: List[Dict], threshold: float = 5.0) -> Dict:
    """Compute batch metrics for the current workflow."""
    accepted_points = []
    for s, accepted in zip(batch, feedback):
        if accepted:
            accepted_points.append((float(s.y), float(s.x)))
    tp = greedy_match(accepted_points, gt_points, threshold=threshold)
    fp = max(0, len(accepted_points) - tp)
    fn = max(0, len(gt_points) - tp)

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * (precision * recall) / max(1e-8, precision + recall)

    return {
        "accepted": int(sum(feedback)),
        "rejected": int(sum(1 for f in feedback if not f)),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
    }

def decision_row(iteration: int, decision_id: int, suggestion, accepted: bool, gt_points: List[Dict]) -> Dict:
    """Run the decision row workflow."""
    ok, distance = find_nearest_gt((float(suggestion.y), float(suggestion.x)), gt_points)
    row = {
        "decision_id": decision_id,
        "iteration": iteration,
        "decision_source": "suggestion_oracle",
        "label": int(1 if accepted else 0),
        "status": "ACCEPTED" if accepted else "REJECTED",
        "y": float(suggestion.y),
        "x": float(suggestion.x),
        "score": float(suggestion.score),
        "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
        "is_gt_match": bool(ok),
        "distance_to_gt": float(distance),
    }
    fv = feature_vector_from_suggestion(suggestion)
    for idx, name in enumerate(FEATURE_NAMES):
        row[f"fv_{name}"] = float(fv[idx])

    comp = dict(getattr(suggestion, "score_components", {}) or {})
    for key, value in comp.items():
        if isinstance(value, (int, float, np.floating)):
            row[f"comp_{key}"] = float(value)
    return row

def export_decision_table(rows: List[Dict], output_csv: Path) -> Path:
    """Export decision table for the current workflow."""
    if not rows:
        output_csv.write_text("decision_id\n")
        return output_csv
    keys = set()
    for row in rows:
        keys.update(row.keys())
    fixed = [
        "decision_id",
        "iteration",
        "decision_source",
        "label",
        "status",
        "y",
        "x",
        "score",
        "suggestion_id",
        "is_gt_match",
        "distance_to_gt",
    ]
    fieldnames = fixed + sorted(k for k in keys if k not in fixed)
    with output_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_csv

def display_iteration_header(iteration: int, total_remaining: int, batch_size: int):
    """Run the display iteration header workflow."""
    print(f"\n{'╔' + '═'*78 + '╗'}")
    print(
        f"║ ITERATION {iteration}: Review {batch_size} Suggestions (Remaining: {total_remaining})".ljust(79)
        + "║"
    )
    print(f"╚{'═'*78 + '╝'}")

def display_batch_results(batch: List, feedback: List[bool], metrics: Dict, iteration: int):
    """Run the display batch results workflow."""
    print(f"\n┌─ Batch Results (Iteration {iteration}) " + "─" * 52 + "┐")
    for i, (s, accepted) in enumerate(zip(batch, feedback), 1):
        status = "✅ ACC" if accepted else "❌ REJ"
        print(f"│ [{i:2d}] {status}  Score: {float(s.score):.3f}  Pos: ({float(s.y):7.1f}, {float(s.x):7.1f})")
    print(f"├─ Batch Metrics " + "─" * 60 + "┤")
    print(f"│ Accepted: {metrics['accepted']:3d}  Rejected: {metrics['rejected']:3d}")
    print(f"│ TP: {metrics['tp']:3d}  FP: {metrics['fp']:3d}  FN: {metrics['fn']:3d}")
    print(f"│ Precision: {metrics['precision']:.3f}  Recall: {metrics['recall']:.3f}  F1: {metrics['f1_score']:.3f}")
    print("└" + "─" * 78 + "┘")
