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


from scripts.assist_iterative_demo_split1 import euclidean_distance, greedy_match, aggregate_gt_xy

def compute_f1_on_validated_data(decision_rows: List[Dict], gt_points: List[Dict], distance_threshold: float = 5.0) -> Dict:
    """
    Compute F1 score ONLY on user-validated data.
    
    This correctly implements the framework:
    - TP: User ACCEPTED suggestion AND it matches GT
    - FP: User ACCEPTED suggestion AND doesn't match GT, PLUS user REJECTED suggestions
    - FN: GT points that don't match any user ACCEPTED suggestion
    
    F1 is only meaningful if users have made decisions (~>=10).
    """
    if not decision_rows:
        return {"tp": 0, "fp": 0, "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "decisions": 0}
    
    # Accepted suggestions that match GT → TP
    tp_count = 0
    matched_gt_indices = set()
    
    for row in decision_rows:
        if int(row.get("label", 0)) == 1:  # User ACCEPTED
            sugg_y = float(row["y"])
            sugg_x = float(row["x"])
            
            # Find matching GT point
            for gt_idx, gt_point in enumerate(gt_points):
                if gt_idx in matched_gt_indices:
                    continue
                gt_y = float(gt_point["y"])
                gt_x = float(gt_point["x"])
                dist = euclidean_distance((sugg_y, sugg_x), (gt_y, gt_x))
                
                if dist <= distance_threshold:
                    tp_count += 1
                    matched_gt_indices.add(gt_idx)
                    break
    
    # FP: User ACCEPTED but doesn't match GT
    fp_accepted_no_match = 0
    for row in decision_rows:
        if int(row.get("label", 0)) == 1:  # User ACCEPTED
            sugg_y = float(row["y"])
            sugg_x = float(row["x"])
            
            # Check if this matches ANY GT point
            matched = False
            for gt_point in gt_points:
                gt_y = float(gt_point["y"])
                gt_x = float(gt_point["x"])
                dist = euclidean_distance((sugg_y, sugg_x), (gt_y, gt_x))
                if dist <= distance_threshold:
                    matched = True
                    break
            
            if not matched:
                fp_accepted_no_match += 1
    
    # FP: User REJECTED (these are false suggestions we made)
    fp_rejected = sum(1 for row in decision_rows if int(row.get("label", 0)) == 0)
    
    fp_count = fp_accepted_no_match + fp_rejected
    
    # FN: GT points we didn't match with accepted suggestions
    fn_count = len(gt_points) - len(matched_gt_indices)
    
    # Compute metrics
    total_decisions = len(decision_rows)
    precision = tp_count / max(1, tp_count + fp_count)
    recall = tp_count / max(1, tp_count + fn_count)
    f1 = 2 * (precision * recall) / max(1e-8, precision + recall)
    
    return {
        "tp": tp_count,
        "fp": fp_count,
        "fn": fn_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "decisions": total_decisions,
        "fp_breakdown": {"accepted_no_match": fp_accepted_no_match, "rejected": fp_rejected},
    }

def evaluate_prediction_set(suggestions: List, gt_points: List[Dict], top_k: int = 50) -> Dict:
    """Run the evaluate prediction set workflow."""
    ranked = sorted(suggestions, key=lambda s: float(s.score), reverse=True)[:top_k]
    points = [(float(s.y), float(s.x)) for s in ranked]
    tp = greedy_match(points, gt_points)
    fp = max(0, len(points) - tp)
    fn = max(0, len(gt_points) - tp)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * (precision * recall) / max(1e-8, precision + recall)
    return {
        "n": len(points),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

def compare_stack_modes(model: LocalPeakSuggestionModel, image_data: np.ndarray, ground_truth: Dict[int, List[Dict[str, float]]], image_name: str):
    """Compare stack modes for the current workflow."""
    if image_data.ndim != 3:
        print("\nStack comparison skipped: requires a 3D stack (T,Y,X or Z,Y,X).")
        return

    gt_agg = aggregate_gt_xy(ground_truth)
    print("\nStack-vs-projection benchmark (top-50 points, GT deduped across stack):")

    start = time.perf_counter()
    proj_only = model.predict_from_stack(
        image_data,
        image_id=1,
        image_name=image_name,
        label="phage",
        z_frame=0,
        strategy="raw",
        refine_from_stack=False,
    )
    proj_time = time.perf_counter() - start

    start = time.perf_counter()
    stack_refined = model.predict_from_stack(
        image_data,
        image_id=1,
        image_name=image_name,
        label="phage",
        z_frame=0,
        strategy="raw",
        refine_from_stack=False,  # Optimized: mean projection already optimal
    )
    stack_time = time.perf_counter() - start

    proj_metrics = evaluate_prediction_set(proj_only, gt_agg, top_k=50)
    stack_metrics = evaluate_prediction_set(stack_refined, gt_agg, top_k=50)

    print(
        f"  projection-only : n={proj_metrics['n']:3d}  P={proj_metrics['precision']:.3f}  R={proj_metrics['recall']:.3f}  F1={proj_metrics['f1']:.3f}  time={proj_time:.3f}s"
    )
    print(
        f"  stack-refined   : n={stack_metrics['n']:3d}  P={stack_metrics['precision']:.3f}  R={stack_metrics['recall']:.3f}  F1={stack_metrics['f1']:.3f}  time={stack_time:.3f}s"
    )
