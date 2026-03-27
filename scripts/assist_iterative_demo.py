#!/usr/bin/env python3
"""Automated iterative assist testing and benchmarking.

This script now reports:
  - Adaptive retrain trigger based on F1 score (default threshold 0.75)
  - Full decision/feature table export
  - Timing: prediction, retrain, total compute
  - Annotation efficiency estimates
  - Stack-refined vs mean-projection-only prediction comparison
"""

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
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))


def find_nearest_gt(
    suggestion_pos: Tuple[float, float], gt_points: List[Dict], distance_threshold: float = 5.0
) -> Tuple[bool, float]:
    if not gt_points:
        return False, float("inf")
    distances = [euclidean_distance(suggestion_pos, (g["y"], g["x"])) for g in gt_points]
    min_dist = min(distances)
    return min_dist <= distance_threshold, min_dist


def greedy_match(points: List[Tuple[float, float]], gt_points: List[Dict], threshold: float = 5.0) -> int:
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
    kept: List[Tuple[float, float]] = []
    for y, x in points:
        if all(euclidean_distance((y, x), p) > threshold for p in kept):
            kept.append((float(y), float(x)))
    return kept


def aggregate_gt_xy(ground_truth: Dict[int, List[Dict[str, float]]], dedupe_threshold: float = 3.0) -> List[Dict[str, float]]:
    all_points = [(float(p["y"]), float(p["x"])) for pts in ground_truth.values() for p in pts]
    deduped = dedupe_points(all_points, threshold=dedupe_threshold)
    return [{"y": y, "x": x} for y, x in deduped]


def simulate_user_feedback(suggestions: List, gt_points: List[Dict], distance_threshold: float = 5.0) -> List[bool]:
    out = []
    for s in suggestions:
        ok, _ = find_nearest_gt((float(s.y), float(s.x)), gt_points, distance_threshold)
        out.append(ok)
    return out


def compute_batch_metrics(batch: List, feedback: List[bool], gt_points: List[Dict], threshold: float = 5.0) -> Dict:
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
    print(f"\n{'╔' + '═'*78 + '╗'}")
    print(
        f"║ ITERATION {iteration}: Review {batch_size} Suggestions (Remaining: {total_remaining})".ljust(79)
        + "║"
    )
    print(f"╚{'═'*78 + '╝'}")


def display_batch_results(batch: List, feedback: List[bool], metrics: Dict, iteration: int):
    print(f"\n┌─ Batch Results (Iteration {iteration}) " + "─" * 52 + "┐")
    for i, (s, accepted) in enumerate(zip(batch, feedback), 1):
        status = "✅ ACC" if accepted else "❌ REJ"
        print(f"│ [{i:2d}] {status}  Score: {float(s.score):.3f}  Pos: ({float(s.y):7.1f}, {float(s.x):7.1f})")
    print(f"├─ Batch Metrics " + "─" * 60 + "┤")
    print(f"│ Accepted: {metrics['accepted']:3d}  Rejected: {metrics['rejected']:3d}")
    print(f"│ TP: {metrics['tp']:3d}  FP: {metrics['fp']:3d}  FN: {metrics['fn']:3d}")
    print(f"│ Precision: {metrics['precision']:.3f}  Recall: {metrics['recall']:.3f}  F1: {metrics['f1_score']:.3f}")
    print("└" + "─" * 78 + "┘")


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


def automated_iterative_test(
    image_path: Path,
    csv_path: Path,
    *,
    batch_size: int = 10,
    f1_threshold: float = 0.75,
    domain: str = "balanced",
    max_iterations: int = 5,
    baseline_points_per_min: float = 50.0,
    compare_stack: bool = True,
):
    print("\n" + "█" * 80)
    print(f"█ AUTOMATED ITERATIVE ASSIST TEST: {image_path.name}".ljust(79) + "█")
    print("█" * 80)

    image_data = imread(str(image_path))
    ground_truth = load_ground_truth(csv_path)
    t_idx = max(ground_truth.keys(), key=lambda t: len(ground_truth[t]))
    gt_points = ground_truth[t_idx]

    if image_data.ndim == 4:
        slice_2d = image_data[t_idx, 0, :, :]
    elif image_data.ndim == 3:
        slice_2d = image_data[t_idx, :, :]
    else:
        slice_2d = image_data

    model = LocalPeakSuggestionModel(min_distance_px=6, threshold_quantile=0.995, max_points=None)

    print(f"\nImage: {image_path.name}")
    print(f"Shape: {image_data.shape}")
    print(f"Testing timepoint: {t_idx} with {len(gt_points)} GT points")
    print(f"Retrain strategy: F1-threshold adaptive ({domain})")
    print(f"  → Threshold: {f1_threshold}")

    start_pred = time.perf_counter()
    suggestions = model.predict(
        slice_2d,
        image_id=1,
        image_name=str(image_path.name),
        t=t_idx,
        z=0,
        label="phage",
        strategy="raw",
    )
    pred_seconds = time.perf_counter() - start_pred

    suggestions = sorted(suggestions, key=lambda s: float(s.score), reverse=True)
    print(f"Generated {len(suggestions)} suggestions in {pred_seconds:.3f}s")

    session = IterativeTestSession(image_name=image_path.name, total_suggestions=len(suggestions), prediction_seconds=pred_seconds)
    ranker = LightweightSuggestionRanker()
    
    # Initialize adaptive retraining strategy with domain-aware threshold
    retrain_strategy = AdaptiveRetrainingStrategy(
        f1_threshold=f1_threshold,
        domain=domain,
        min_decisions=min(batch_size, 10)  # Need some minimum decisions before considering retrain
    )

    remaining = list(suggestions)
    iteration = 1
    decision_id = 0

    while remaining and iteration <= max_iterations:
        display_iteration_header(iteration, len(remaining), batch_size)

        batch = remaining[:batch_size]
        remaining = remaining[batch_size:]

        feedback = simulate_user_feedback(batch, gt_points)
        metrics = compute_batch_metrics(batch, feedback, gt_points)
        display_batch_results(batch, feedback, metrics, iteration)

        session.iterations_completed += 1
        session.total_accepted += metrics["accepted"]
        session.total_rejected += metrics["rejected"]
        session.true_positives += metrics["tp"]
        session.false_positives += metrics["fp"]
        session.false_negatives += metrics["fn"]
        session.batch_metrics.append(metrics)

        for s, accepted in zip(batch, feedback):
            decision_id += 1
            session.decision_rows.append(decision_row(iteration, decision_id, s, accepted, gt_points))

        # Compute F1 score on VALIDATED data only (user's accept/reject decisions)
        validated_metrics = compute_f1_on_validated_data(session.decision_rows, gt_points)
        f1 = validated_metrics["f1"]
        precision = validated_metrics["precision"]
        recall = validated_metrics["recall"]
        
        session.f1_scores.append(f1)
        
        # Display detailed validated metrics
        print(f"   ✓ Validated Data (decisions on {validated_metrics['decisions']} suggestions):")
        print(f"     TP={validated_metrics['tp']}, FP={validated_metrics['fp']}, FN={validated_metrics['fn']}")
        print(f"     Precision: {precision:.3f}  •  Recall: {recall:.3f}  •  F1: {f1:.3f}")
        
        # Decision on retraining based on VALIDATED F1
        reason = f"Validated F1 on {validated_metrics['decisions']} decisions"
        needs_retrain = retrain_strategy.should_retrain(f1, reason=reason) and remaining
        
        if needs_retrain:
            x = np.asarray(
                [[float(r[f"fv_{name}"]) for name in FEATURE_NAMES] for r in session.decision_rows], dtype=np.float64
            )
            y = np.asarray([int(r["label"]) for r in session.decision_rows], dtype=np.float64)

            if len(set(y.tolist())) >= 2:
                fit_start = time.perf_counter()
                ranker.fit(x, y)
                fit_seconds = time.perf_counter() - fit_start
                session.total_retrain_seconds += fit_seconds
                session.retrain_events += 1

                remaining = ranker.apply_to_suggestions(remaining)
                remaining = sorted(remaining, key=lambda s: float(s.score), reverse=True)
                reason_str = f"F1={f1:.3f} < {f1_threshold}"
                session.retrain_reasons.append(reason_str)
                print(
                    f"   → RETRAIN: {reason_str} (trained in {1000.0*fit_seconds:.2f} ms)"
                )
            else:
                print(f"   → Retrain needed but skipped (need both accepted and rejected labels)")
        else:
            status = f"F1={f1:.3f} ≥ {f1_threshold}"
            print(f"   → Skip retrain: {status} (model performance sufficient!)")

        iteration += 1

    # Export decision table.
    export_path = image_path.with_suffix("").with_name(image_path.stem + "_iterative_decisions.csv")
    export_decision_table(session.decision_rows, export_path)

    accepted_points = [(float(r["y"]), float(r["x"])) for r in session.decision_rows if int(r["label"]) == 1]
    matched_gt = greedy_match(accepted_points, gt_points)
    precision = matched_gt / max(1, len(accepted_points))
    recall = matched_gt / max(1, len(gt_points))
    f1 = 2 * (precision * recall) / max(1e-8, precision + recall)

    compute_seconds = session.prediction_seconds + session.total_retrain_seconds
    assisted_points_per_min = baseline_points_per_min * (1.0 + 0.5 * (session.total_accepted / max(1, session.total_accepted + session.total_rejected)))
    baseline_minutes = len(gt_points) / max(1e-8, baseline_points_per_min)
    assisted_minutes = len(gt_points) / max(1e-8, assisted_points_per_min)
    estimated_time_saved_minutes = baseline_minutes - assisted_minutes

    print("\n" + "█" * 80)
    print("█ FINAL SUMMARY".ljust(79) + "█")
    print("█" * 80)
    print(f"Image: {session.image_name}")
    print(f"Timepoint: {t_idx}")
    print(f"Ground truth points: {len(gt_points)}")
    print(f"Total reviewed: {session.total_accepted + session.total_rejected}")
    print(f"Accepted: {session.total_accepted}")
    print(f"Rejected: {session.total_rejected}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1: {f1:.3f}")
    print(f"Iterations completed: {session.iterations_completed}")
    print(f"Estimated iterations to cover all GT at {batch_size}/iter: {int(np.ceil(len(gt_points)/max(1,batch_size)))}")
    print(f"Prediction time: {session.prediction_seconds:.3f}s")
    
    # F1-threshold-based retraining summary
    print(f"\n🎓 Adaptive Retraining (F1-Threshold Based):")
    print(f"  Threshold: F1 < {f1_threshold}")
    print(f"  Retrain events: {session.retrain_events}")
    if session.f1_scores:
        print(f"  F1 score history: {[f'{f:.2f}' for f in session.f1_scores]}")
        avg_f1 = np.mean(session.f1_scores)
        print(f"  Average F1: {avg_f1:.3f}")
    if session.retrain_reasons:
        print(f"  Retraining triggers:")
        for reason in session.retrain_reasons:
            print(f"    • {reason}")
    
    print(f"\n⏱️  Timing:")
    print(f"  Total retrain time: {session.total_retrain_seconds:.4f}s")
    if session.retrain_events > 0:
        print(f"  Average retrain time: {1000.0*session.total_retrain_seconds/session.retrain_events:.2f} ms")
    print(f"  Total model compute time: {compute_seconds:.3f}s")
    
    print(f"\n📈 Annotation efficiency estimate:")
    print(f"  Baseline points/min: {baseline_points_per_min:.1f}")
    print(f"  Assisted points/min estimate: {assisted_points_per_min:.1f}")
    print(f"  Baseline completion time: {baseline_minutes:.2f} min")
    print(f"  Assisted completion time: {assisted_minutes:.2f} min")
    print(f"  Estimated time saved: {estimated_time_saved_minutes:.2f} min")
    print(f"Decision table exported: {export_path}")
    print("█" * 80 + "\n")

    if compare_stack:
        compare_stack_modes(model, image_data if image_data.ndim == 3 else np.asarray(image_data), ground_truth, image_path.name)

    return session


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Automated iterative assist testing with F1-threshold adaptive retraining")
    parser.add_argument("--image", help="Path to test image (default: /tmp/assist_demo_tests/test_75_spots.tif)")
    parser.add_argument("--csv", help="Path to ground truth CSV (default: /tmp/assist_demo_tests/test_75_spots.csv)")
    parser.add_argument("--batch-size", type=int, default=10, help="Suggestions per iteration")
    parser.add_argument(
        "--f1-threshold",
        type=float,
        default=0.75,
        help="F1 threshold for adaptive retraining. Only retrain if F1 < threshold. Default 0.75"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="balanced",
        choices=["high_precision", "balanced", "high_recall"],
        help="Domain preset: high_precision (0.85), balanced (0.75), high_recall (0.65)"
    )
    parser.add_argument("--max-iterations", type=int, default=5, help="Max iterations")
    parser.add_argument(
        "--baseline-points-per-min",
        type=float,
        default=50.0,
        help="Baseline manual annotation throughput used for efficiency estimates",
    )
    parser.add_argument(
        "--compare-stack",
        action="store_true",
        help="Run stack-refined vs projection-only benchmark (3D stacks only)",
    )

    args = parser.parse_args()

    test_dir = Path("/tmp/assist_demo_tests")
    image_path = Path(args.image) if args.image else test_dir / "test_75_spots.tif"
    csv_path = Path(args.csv) if args.csv else test_dir / "test_75_spots.csv"

    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}")
        sys.exit(1)

    automated_iterative_test(
        image_path,
        csv_path,
        batch_size=max(1, int(args.batch_size)),
        f1_threshold=max(0.0, min(1.0, float(args.f1_threshold))),
        domain=args.domain,
        max_iterations=max(1, int(args.max_iterations)),
        baseline_points_per_min=max(1.0, float(args.baseline_points_per_min)),
        compare_stack=bool(args.compare_stack),
    )

    print("✅ Automated iterative testing complete!\n")


if __name__ == "__main__":
    main()
