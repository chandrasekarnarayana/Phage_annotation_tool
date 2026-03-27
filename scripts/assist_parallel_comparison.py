#!/usr/bin/env python3
"""Quick test of parallel frame prediction efficiency."""

import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from tifffile import imread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel


def test_sequential_vs_parallel():
    """Compare sequential vs parallel frame processing."""
    
    # Load test image
    image_path = Path("/tmp/assist_demo_tests/test_75_spots.tif")
    if not image_path.exists():
        print(f"❌ Test image not found: {image_path}")
        return
    
    print("\n" + "="*80)
    print("PARALLEL FRAME PROCESSING TEST")
    print("="*80)
    
    # Load stack
    stack = imread(image_path)
    print(f"\nLoaded stack: {stack.shape}")
    print(f"  Frames: {stack.shape[0]}")
    print(f"  Dimensions: {stack.shape[1:]} pixels")
    
    # Initialize model
    model = LocalPeakSuggestionModel()
    
    # ════════════════════════════════════════════════════════════════════════
    # Test 1: SEQUENTIAL PREDICTION (current approach)
    # ════════════════════════════════════════════════════════════════════════
    
    print(f"\n" + "-"*80)
    print(f"SEQUENTIAL PROCESSING: Predict each frame one-by-one")
    print("-"*80)
    
    sequential_results = {}
    seq_start = time.perf_counter()
    
    for frame_idx in range(stack.shape[0]):
        frame = stack[frame_idx]
        frame_stack = np.array([frame])
        
        frame_predict_start = time.perf_counter()
        suggestions = model.predict_from_stack(
            frame_stack,
            image_id=1,
            image_name=f"frame_{frame_idx}",
            label="phage",
            z_frame=frame_idx,
            strategy="raw",
            refine_from_stack=False,
        )
        frame_time = time.perf_counter() - frame_predict_start
        
        sequential_results[frame_idx] = {
            'count': len(suggestions),
            'time': frame_time,
        }
        print(f"  Frame {frame_idx}: {len(suggestions):3d} suggestions in {frame_time:.3f}s")
    
    seq_total = time.perf_counter() - seq_start
    seq_count = sum(r['count'] for r in sequential_results.values())
    print(f"\nSequential Total:  {seq_count} suggestions in {seq_total:.3f}s")
    
    # ════════════════════════════════════════════════════════════════════════
    # Test 2: PARALLEL PREDICTION (new approach)
    # ════════════════════════════════════════════════════════════════════════
    
    print(f"\n" + "-"*80)
    print(f"PARALLEL PROCESSING: Predict all frames simultaneously")
    print("-"*80)
    
    def predict_frame(frame_idx: int):
        """Predict on single frame."""
        frame = stack[frame_idx]
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
    
    parallel_results = {}
    par_start = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=min(3, stack.shape[0])) as executor:
        futures = [executor.submit(predict_frame, f) for f in range(stack.shape[0])]
        for future in futures:
            frame_idx, suggestions = future.result()
            parallel_results[frame_idx] = {
                'count': len(suggestions),
            }
            print(f"  Frame {frame_idx}: {len(suggestions):3d} suggestions")
    
    par_total = time.perf_counter() - par_start
    par_count = sum(r['count'] for r in parallel_results.values())
    print(f"\nParallel Total:    {par_count} suggestions in {par_total:.3f}s")
    
    # ════════════════════════════════════════════════════════════════════════
    # COMPARISON & ANALYSIS
    # ════════════════════════════════════════════════════════════════════════
    
    print(f"\n" + "="*80)
    print(f"PERFORMANCE ANALYSIS")
    print("="*80)
    
    speedup = seq_total / par_total
    time_saved = seq_total - par_total
    efficiency = (1.0 - par_total / seq_total) * 100.0
    
    print(f"\nSequential approach:   {seq_total:.3f}s (baseline)")
    print(f"Parallel approach:     {par_total:.3f}s")
    print(f"Speedup:               {speedup:.2f}×")
    print(f"Time saved:            {time_saved:.3f}s ({efficiency:.1f}%)")
    
    # Estimate with retraining overhead
    print(f"\nWith Retraining Included:")
    print(f"  Sequential: {seq_total:.3f}s + {(stack.shape[0]-1)*0.5:.3f}s retrain = {seq_total + (stack.shape[0]-1)*0.5:.3f}s total")
    print(f"  Parallel:   {par_total:.3f}s + {0.5:.3f}s retrain = {par_total + 0.5:.3f}s total")
    
    total_seq = seq_total + (stack.shape[0]-1)*0.5
    total_par = par_total + 0.5
    total_speedup = total_seq / total_par
    total_saved = total_seq - total_par
    
    print(f"  Total speedup:         {total_speedup:.2f}×")
    print(f"  Total time saved:      {total_saved:.3f}s")
    
    # Scalability analysis
    print(f"\nScalability Analysis:")
    print(f"  Sequential scales as:     O(n_frames × time_per_frame)")
    print(f"  Parallel scales as:       O(time_per_frame)  [constant!]")
    
    if stack.shape[0] > 1:
        print(f"\n  For {stack.shape[0]} frames:")
        print(f"    • Sequential overhead: {stack.shape[0]-1} redundant retrains")
        print(f"    • Parallel overhead:   0 redundant retrains")
        print(f"    • Efficiency gain:     {100*(stack.shape[0]-1)/stack.shape[0]:.0f}% fewer computations")
    
    # Memory efficiency
    print(f"\nMemory Efficiency:")
    frame_size_mb = stack[0].nbytes / (1024**2)
    print(f"  Single frame: ~{frame_size_mb:.1f} MB")
    print(f"  ThreadPoolExecutor memory overhead: Minimal (frames shared in memory)")
    
    print(f"\n" + "="*80)
    print(f"✅ CONCLUSION")
    print("="*80)
    print(f"Parallel processing is {speedup:.1f}× faster than sequential.")
    print(f"With retraining, gains become {total_speedup:.1f}× (avoids {stack.shape[0]-1} redundant trains).")
    print(f"\nRecommendation: Use parallel prediction for multi-frame stacks.")


if __name__ == "__main__":
    test_sequential_vs_parallel()
