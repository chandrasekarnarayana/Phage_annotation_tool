"""Automated iterative assist testing and benchmarking.

This script now reports:
  - Adaptive retrain trigger based on F1 score (default threshold 0.75)
  - Full decision/feature table export
  - Timing: prediction, retrain, total compute
  - Annotation efficiency estimates
  - Stack-refined vs mean-projection-only prediction comparison

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from scripts.assist_iterative_demo_split1 import AdaptiveRetrainingStrategy, IterativeTestSession, load_ground_truth, euclidean_distance, find_nearest_gt, greedy_match, dedupe_points, aggregate_gt_xy, simulate_user_feedback, compute_batch_metrics, decision_row, export_decision_table, display_iteration_header, display_batch_results
from scripts.assist_iterative_demo_split2 import compute_f1_on_validated_data, evaluate_prediction_set, compare_stack_modes
from scripts.assist_iterative_demo_split3 import automated_iterative_test, main

if __name__ == "__main__":
    raise SystemExit(main())
