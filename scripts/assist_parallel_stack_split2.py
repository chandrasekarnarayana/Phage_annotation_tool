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


from scripts.assist_parallel_stack_split1 import IterativeTestSession, load_ground_truth, compute_batch_metrics, simulate_user_feedback, decision_row

def process_stack_parallel(
    stack: np.ndarray,
    gt_points: Dict[int, List[Dict]],
    model: LocalPeakSuggestionModel,
    max_parallel_frames: int = 4,
) -> IterativeTestSession:
    """Process multi-frame stack with parallel prediction and single training.
    
    For a 3-frame Z-stack:
      Before: predict(3s) + train(0.5s) + predict(3s) + train(0.5s) + predict(3s) = 10s
      After:  parallel_predict(3s) + train(0.5s) = 3.5s
      Speedup: 2.9×
    """
    
    n_frames = stack.shape[0]
    ranker = LightweightSuggestionRanker()
    session = IterativeTestSession(
        image_name=f"{n_frames}-frame stack",
        total_suggestions=0,
    )
    
    # ════════════════════════════════════════════════════════════════════════
    # 1. PARALLEL PREDICTION: Predict all frames simultaneously
    # ════════════════════════════════════════════════════════════════════════
    
    print(f"\n{'='*80}")
    print(f"STACK PARALLEL PROCESSING: {n_frames} frames")
    print(f"{'='*80}")
    print(f"\n🔄 Phase 1: Parallel Prediction on {n_frames} frames...")
    
    predict_start = time.perf_counter()
    all_suggestions_by_frame = {}
    
    def predict_frame(frame_idx: int):
        """Predict on single frame."""
        frame = stack[frame_idx]
        # Wrap in time dimension for API compatibility
        frame_stack = np.array([frame])
        suggestions = model.predict_from_stack(
            frame_stack,
            image_id=1,
            image_name=f"frame_{frame_idx}",
            label="phage",
            z_frame=frame_idx,
            strategy="raw",
            refine_from_stack=False,
        )
        return frame_idx, suggestions
    
    # Launch parallel predictions
    with ThreadPoolExecutor(max_workers=min(max_parallel_frames, n_frames)) as executor:
        futures = [executor.submit(predict_frame, f) for f in range(n_frames)]
        for future in futures:
            frame_idx, suggestions = future.result()
            all_suggestions_by_frame[frame_idx] = suggestions
    
    predict_seconds = time.perf_counter() - predict_start
    total_suggestions = sum(len(s) for s in all_suggestions_by_frame.values())
    
    # Estimate sequential time (if done frame-by-frame)
    estimated_sequential_time = n_frames * 3.5  # ~3.5s per frame with prediction
    
    print(f"✅ Predicted {total_suggestions} suggestions in {predict_seconds:.3f}s")
    if n_frames > 1:
        parallel_speedup = estimated_sequential_time / predict_seconds
        time_saved = estimated_sequential_time - predict_seconds
        print(f"   Estimated sequential: {estimated_sequential_time:.3f}s")
        print(f"   Speedup: {parallel_speedup:.2f}×")
        print(f"   Time saved: {time_saved:.3f}s")
        session.parallel_speedup = parallel_speedup
        session.time_saved_seconds = time_saved
    
    # ════════════════════════════════════════════════════════════════════════
    # 2. COLLECT FEEDBACK: Aggregate annotations from all frames
    # ════════════════════════════════════════════════════════════════════════
    
    print(f"\n📋 Phase 2: Collecting Feedback from {n_frames} frames...")
    
    all_feedback = {}
    all_decision_rows = []
    decision_id = 1
    
    for frame_idx in range(n_frames):
        suggestions = all_suggestions_by_frame[frame_idx]
        gt_frame = gt_points.get(frame_idx, [])
        
        # Get user feedback (simulated)
        feedback = simulate_user_feedback(suggestions, gt_frame)
        all_feedback[frame_idx] = {
            'suggestions': suggestions,
            'feedback': feedback,
            'gt': gt_frame,
        }
        
        # Compute metrics
        metrics = compute_batch_metrics(suggestions, feedback, gt_frame)
        session.total_accepted += metrics['accepted']
        session.total_rejected += metrics['rejected']
        session.true_positives += metrics['tp']
        session.false_positives += metrics['fp']
        session.false_negatives += metrics['fn']
        
        print(f"  Frame {frame_idx}: {len(suggestions)} suggestions, "
              f"TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']}")
        
        # Collect decision rows for training
        for suggestion, accepted in zip(suggestions, feedback):
            row = decision_row(1, decision_id, suggestion, accepted, gt_frame)
            all_decision_rows.append(row)
            decision_id += 1
    
    session.total_suggestions = total_suggestions
    session.decision_rows = all_decision_rows
    
    # ════════════════════════════════════════════════════════════════════════
    # 3. SMART TRAINING: Train ONCE on combined feedback (not per-frame)
    # ════════════════════════════════════════════════════════════════════════
    
    print(f"\n🎓 Phase 3: Smart Training on Combined Feedback...")
    print(f"   Training on {len(all_decision_rows)} decisions from {n_frames} frames")
    
    if len(all_decision_rows) >= 2:
        # Prepare training data
        x = np.asarray(
            [[float(r[f"fv_{name}"]) for name in FEATURE_NAMES] for r in all_decision_rows],
            dtype=np.float64
        )
        y = np.asarray([int(r["label"]) for r in all_decision_rows], dtype=np.float64)
        
        # Check for both classes
        if len(set(y.tolist())) >= 2:
            train_start = time.perf_counter()
            ranker.fit(x, y)
            train_seconds = time.perf_counter() - train_start
            session.total_retrain_seconds = train_seconds
            session.retrain_events = 1
            
            print(f"✅ Trained in {train_seconds:.3f}s")
            print(f"   Efficiency gain: 1 training event for {n_frames} frames")
            if n_frames > 1:
                saved_trains = n_frames - 1
                estimated_saved_time = saved_trains * 0.5  # ~0.5s per retrain
                print(f"   Redundant trainings avoided: {saved_trains}")
                print(f"   Training time saved: ~{estimated_saved_time:.3f}s")
        else:
            print("⚠️  Skipped training (need both positive and negative labels)")
            session.retrain_events = 0
    
    # ════════════════════════════════════════════════════════════════════════
    # 4. SUMMARY & METRICS
    # ════════════════════════════════════════════════════════════════════════
    
    total_compute_time = predict_seconds + session.total_retrain_seconds
    
    print(f"\n{'='*80}")
    print(f"PARALLEL PROCESSING RESULTS")
    print(f"{'='*80}")
    print(f"Frames processed:        {n_frames}")
    print(f"Total predictions:       {total_suggestions}")
    print(f"Parallel prediction:     {predict_seconds:.3f}s")
    print(f"Smart training:          {session.total_retrain_seconds:.3f}s (1 event)")
    print(f"Total compute time:      {total_compute_time:.3f}s")
    
    if n_frames > 1:
        sequential_time = estimate_sequential_time(n_frames, 3.5, 0.5)
        speedup = sequential_time / total_compute_time
        savings = sequential_time - total_compute_time
        savings_pct = 100.0 * savings / sequential_time
        
        print(f"\nComparison to Sequential Processing:")
        print(f"  Sequential would take: {sequential_time:.3f}s")
        print(f"  Parallel delivers:     {total_compute_time:.3f}s")
        print(f"  Speedup:               {speedup:.2f}×")
        print(f"  Time saved:            {savings:.3f}s ({savings_pct:.1f}%)")
        print(f"  Retrains avoided:      {n_frames - 1} ({100*(n_frames-1)/n_frames:.0f}%)")
    
    print(f"\nDetection Metrics:")
    print(f"  TP: {session.true_positives}, FP: {session.false_positives}, "
          f"FN: {session.false_negatives}")
    if session.true_positives + session.false_positives > 0:
        precision = session.true_positives / (session.true_positives + session.false_positives)
        recall = session.true_positives / (session.true_positives + session.false_negatives)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        print(f"  Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")
    
    print(f"{'='*80}\n")
    
    return session

def estimate_sequential_time(n_frames: int, time_per_frame: float, time_per_retrain: float) -> float:
    """Estimate time if processing sequentially."""
    # Each frame: predict + retrain (except last)
    return n_frames * time_per_frame + (n_frames - 1) * time_per_retrain

def main():
    """Run the main workflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Parallel stack processing demo")
    parser.add_argument("--image", type=Path, required=True, help="Input image file")
    parser.add_argument("--csv", type=Path, required=True, help="Ground truth CSV")
    parser.add_argument("--max-parallel", type=int, default=4, help="Max parallel frames")
    args = parser.parse_args()
    
    # Load data
    print(f"Loading image: {args.image}")
    stack = imread(args.image)
    print(f"  Shape: {stack.shape}")
    
    print(f"Loading ground truth: {args.csv}")
    gt_points = load_ground_truth(args.csv)
    print(f"  {sum(len(v) for v in gt_points.values())} ground truth points across {len(gt_points)} frames")
    
    # Initialize model
    print(f"Initializing detection model...")
    model = LocalPeakSuggestionModel()
    
    # Process stack in parallel
    session = process_stack_parallel(
        stack,
        gt_points,
        model,
        max_parallel_frames=args.max_parallel,
    )
    
    # Export decisions
    export_path = args.image.with_suffix("").with_name(
        args.image.stem + "_parallel_decisions.csv"
    )
    print(f"Exporting decisions to: {export_path}")
    if session.decision_rows:
        with export_path.open("w") as f:
            writer = csv.DictWriter(f, fieldnames=session.decision_rows[0].keys())
            writer.writeheader()
            writer.writerows(session.decision_rows)
    
    print(f"✅ Complete!")
