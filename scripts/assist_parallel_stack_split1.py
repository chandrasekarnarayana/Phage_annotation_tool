"""Split definitions from assist_parallel_stack.py."""

from __future__ import annotations

import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
    parallel_speedup: float = 1.0
    time_saved_seconds: float = 0.0

def load_ground_truth(csv_path: Path) -> Dict[int, List[Dict[str, float]]]:
    """Load ground truth and group by frame index."""
    gt: Dict[int, List[Dict[str, float]]] = {}
    with csv_path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            # Support both 'timepoint', 't', 'z' column names
            frame_col = None
            for col in ["timepoint", "t_idx", "t", "z_idx", "z"]:
                if col in row:
                    frame_col = col
                    break
            frame = int(row.get(frame_col, 0)) if frame_col else 0
            y = float(row["y"])
            x = float(row["x"])
            gt.setdefault(frame, []).append({"y": y, "x": x})
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

def compute_batch_metrics(
    batch: List, feedback: List[bool], gt_points: List[Dict]
) -> Dict:
    """Compute TP/FP/FN metrics for a batch."""
    suggestions_pos = [(float(s.y), float(s.x)) for s in batch]
    
    tp = sum(1 for sugg_pos, is_accepted in zip(suggestions_pos, feedback)
             if is_accepted and find_nearest_gt(sugg_pos, gt_points)[0])
    fp = sum(1 for sugg_pos, is_accepted in zip(suggestions_pos, feedback)
             if is_accepted and not find_nearest_gt(sugg_pos, gt_points)[0])
    fn = len(gt_points) - tp
    
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "accepted": sum(feedback),
        "rejected": sum(1 for f in feedback if not f),
        "precision": tp / (tp + fp) if (tp + fp) > 0 else 0.0,
        "recall": tp / (tp + fn) if (tp + fn) > 0 else 0.0,
    }

def simulate_user_feedback(batch: List, gt_points: List[Dict]) -> List[bool]:
    """Simulate user accepting TP and rejecting FP."""
    feedback = []
    for suggestion in batch:
        is_tp, _ = find_nearest_gt((float(suggestion.y), float(suggestion.x)), gt_points)
        feedback.append(is_tp)
    return feedback

def decision_row(
    iteration: int, decision_id: int, suggestion, accepted: bool, gt_points: List[Dict]
) -> Dict:
    """Create decision row for training data."""
    is_tp, dist = find_nearest_gt((float(suggestion.y), float(suggestion.x)), gt_points)
    
    row = {
        "iteration": iteration,
        "decision_id": decision_id,
        "label": 1 if accepted else 0,
        "suggestion_score": float(suggestion.score),
        "y": float(suggestion.y),
        "x": float(suggestion.x),
        "is_tp": is_tp,
        "nn_distance": dist,
    }
    
    # Add feature vectors
    fv = feature_vector_from_suggestion(suggestion)
    for name in FEATURE_NAMES:
        row[f"fv_{name}"] = fv.get(name, 0.0)
    
    return row
