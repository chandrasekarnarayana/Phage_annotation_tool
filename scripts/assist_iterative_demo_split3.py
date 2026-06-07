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


from scripts.assist_iterative_demo_split1 import AdaptiveRetrainingStrategy, IterativeTestSession, load_ground_truth, greedy_match, simulate_user_feedback, compute_batch_metrics, decision_row, export_decision_table, display_iteration_header, display_batch_results
from scripts.assist_iterative_demo_split2 import compute_f1_on_validated_data, compare_stack_modes

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
    """Run the automated iterative test workflow."""
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
    """Run the main workflow."""
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
