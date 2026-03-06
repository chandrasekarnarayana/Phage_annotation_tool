#!/usr/bin/env python3
"""
Comprehensive test of the Assist feature with demo images.
Tests suggestion generation vs ground truth annotations from demo CSV files.
"""

import csv
import sys
from pathlib import Path
from typing import List, Tuple
import numpy as np
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from phage_annotator.demo import generate_dummy_image
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from tifffile import imread

@dataclass
class TestMetrics:
    """Metrics for suggestion quality."""
    true_positives: int = 0      # Suggestions within threshold of ground truth
    false_positives: int = 0     # Suggestions with no nearby ground truth
    false_negatives: int = 0     # Ground truth with no nearby suggestion
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    mean_distance: float = 0.0

def load_ground_truth(csv_path: Path) -> dict:
    """Load ground truth annotations from CSV."""
    gt = {}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = int(row['timepoint'])
            y = float(row['y'])
            x = float(row['x'])
            spot_id = int(row['spot_id'])
            
            if t not in gt:
                gt[t] = []
            gt[t].append({'y': y, 'x': x, 'spot_id': spot_id})
    
    return gt

def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points."""
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def match_suggestions_to_ground_truth(
    suggestions: List,
    ground_truth: List,
    distance_threshold: float = 5.0
) -> Tuple[int, float, List[Tuple]]:
    """
    Match suggestions to ground truth annotations.
    
    Returns:
        (matches, mean_distance, matched_pairs)
    """
    if not suggestions or not ground_truth:
        return 0, 0.0, []
    
    matched_pairs = []
    distances = []
    matched_gt_indices = set()
    
    for suggestion in suggestions:
        best_dist = float('inf')
        best_idx = -1
        
        for idx, gt in enumerate(ground_truth):
            dist = euclidean_distance(
                (float(suggestion.y), float(suggestion.x)),
                (gt['y'], gt['x'])
            )
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        
        if best_dist <= distance_threshold and best_idx >= 0:
            if best_idx not in matched_gt_indices:  # Don't match same GT twice
                matched_gt_indices.add(best_idx)
                distances.append(best_dist)
                matched_pairs.append((suggestion, ground_truth[best_idx], best_dist))
    
    mean_dist = np.mean(distances) if distances else 0.0
    return len(matched_pairs), mean_dist, matched_pairs

def test_suggestions_on_image(
    image_path: Path,
    csv_path: Path,
    test_name: str,
    distance_threshold: float = 5.0
) -> Tuple[TestMetrics, dict]:
    """Test suggestion generation on a single image."""
    print(f"\n[TEST] {test_name}")
    print("=" * 70)
    
    # Load image and ground truth
    image_data = imread(str(image_path))
    ground_truth = load_ground_truth(csv_path)
    
    print(f"  Image shape: {image_data.shape}")
    print(f"  Ground truth timepoints: {sorted(ground_truth.keys())}")
    print(f"  Total ground truth annotations: {sum(len(v) for v in ground_truth.values())}")
    
    # Initialize suggestion model
    model = LocalPeakSuggestionModel(
        min_distance_px=6,
        threshold_quantile=0.995,
        max_points=None
    )
    
    metrics_per_frame = {}
    all_suggestions = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0
    all_distances = []
    
    # Test each timepoint
    for t in sorted(ground_truth.keys()):
        gt_points = ground_truth[t]
        
        # Get the correct slice from image
        if image_data.ndim == 4:  # (T, Z, H, W)
            slice_2d = image_data[t, 0, :, :]  # First z-slice
        elif image_data.ndim == 3:  # (T, H, W)
            slice_2d = image_data[t, :, :]
        else:  # (H, W)
            slice_2d = image_data
        
        # Generate suggestions
        suggestions = model.predict(
            slice_2d,
            image_id=1,
            image_name=str(image_path.name),
            t=t,
            z=0,
            label="phage",
            strategy="raw"
        )
        
        all_suggestions[t] = suggestions
        
        # Match suggestions to ground truth
        tp, mean_dist, matched_pairs = match_suggestions_to_ground_truth(
            suggestions, gt_points, distance_threshold
        )
        
        fp = len(suggestions) - tp
        fn = len(gt_points) - tp
        
        total_tp += tp
        total_fp += fp
        total_fn += fn
        
        # Collect distances for matched suggestions
        for sugg, gt, dist in matched_pairs:
            all_distances.append(dist)
        
        metrics_per_frame[t] = {
            'gt_count': len(gt_points),
            'suggestion_count': len(suggestions),
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'mean_distance': mean_dist
        }
        
        print(f"    Frame {t:2d}: GT={len(gt_points):3d}, "
              f"Suggestions={len(suggestions):3d}, "
              f"TP={tp:3d}, FP={fp:3d}, FN={fn:3d}, "
              f"MeanDist={mean_dist:5.2f}px")
    
    # Calculate aggregate metrics
    metrics = TestMetrics()
    metrics.true_positives = total_tp
    metrics.false_positives = total_fp
    metrics.false_negatives = total_fn
    
    if total_tp + total_fp > 0:
        metrics.precision = total_tp / (total_tp + total_fp)
    
    if total_tp + total_fn > 0:
        metrics.recall = total_tp / (total_tp + total_fn)
    
    if metrics.precision + metrics.recall > 0:
        metrics.f1_score = 2 * (metrics.precision * metrics.recall) / (metrics.precision + metrics.recall)
    
    if all_distances:
        metrics.mean_distance = np.mean(all_distances)
    
    print(f"\n  Aggregate Metrics:")
    print(f"    True Positives:       {metrics.true_positives}")
    print(f"    False Positives:      {metrics.false_positives}")
    print(f"    False Negatives:      {metrics.false_negatives}")
    print(f"    Precision:            {metrics.precision:.3f}")
    print(f"    Recall:               {metrics.recall:.3f}")
    print(f"    F1-Score:             {metrics.f1_score:.3f}")
    print(f"    Mean Distance (TP):   {metrics.mean_distance:.2f}px")
    
    return metrics, metrics_per_frame

def main():
    """Run comprehensive assist feature testing."""
    print("\n" + "█" * 70)
    print("█ ASSIST FEATURE TESTING WITH DEMO IMAGES".center(70) + "█")
    print("█" * 70)
    
    test_dir = Path("/tmp/assist_tests")
    test_dir.mkdir(exist_ok=True)
    
    # Test configurations - smaller images for faster testing
    test_configs = [
        {"n_spots": 30, "seed": 42, "mode": "t", "name": "30_spots_deterministic"},
        {"n_spots": 50, "seed": 999, "mode": "t", "name": "50_spots_random"},
        {"n_spots": 50, "seed": 12345, "mode": "tz", "name": "50_spots_zstack"},
    ]
    
    print("\n[PHASE 1] Generating Demo Images")
    print("-" * 70)
    
    generated_images = []
    for config in test_configs:
        test_name = config["name"]
        img_path = test_dir / f"{test_name}.tif"
        
        print(f"  Generating: {test_name}...")
        img, csv = generate_dummy_image(
            img_path,
            mode=config["mode"],
            n_spots=config["n_spots"],
            seed=config["seed"]
        )
        print(f"    ✓ Image: {img.stat().st_size / 1024 / 1024:.2f} MB")
        print(f"    ✓ CSV: {csv.stat().st_size / 1024:.2f} KB")
        generated_images.append((img, csv, config))
    
    # Test each image
    print("\n[PHASE 2] Testing Suggestions")
    print("-" * 70)
    
    all_results = []
    for img_path, csv_path, config in generated_images:
        metrics, frame_metrics = test_suggestions_on_image(
            img_path, csv_path, 
            test_name=f"{config['name']} (mode={config['mode']}, spots={config['n_spots']})"
        )
        all_results.append({
            "config": config,
            "metrics": metrics,
            "frame_metrics": frame_metrics
        })
    
    # Summary
    print("\n" + "█" * 70)
    print("█ SUMMARY OF RESULTS".center(70) + "█")
    print("█" * 70)
    
    print(f"\n{'Test Name':<25} {'Precision':<12} {'Recall':<12} {'F1-Score':<12}")
    print("-" * 61)
    
    for result in all_results:
        config = result["config"]
        metrics = result["metrics"]
        name = config["name"][:24]
        print(f"{name:<25} {metrics.precision:<12.3f} {metrics.recall:<12.3f} {metrics.f1_score:<12.3f}")
    
    # Performance analysis
    print(f"\n[PERFORMANCE ANALYSIS]")
    print("-" * 70)
    
    avg_precision = np.mean([r["metrics"].precision for r in all_results])
    avg_recall = np.mean([r["metrics"].recall for r in all_results])
    avg_f1 = np.mean([r["metrics"].f1_score for r in all_results])
    
    print(f"  Average Precision:     {avg_precision:.3f}")
    print(f"  Average Recall:        {avg_recall:.3f}")
    print(f"  Average F1-Score:      {avg_f1:.3f}")
    
    # Quality assessment
    print(f"\n[QUALITY ASSESSMENT]")
    print("-" * 70)
    
    if avg_f1 >= 0.8:
        print(f"  ✅ EXCELLENT: F1-Score {avg_f1:.3f} indicates very strong suggestion quality")
    elif avg_f1 >= 0.7:
        print(f"  ✅ GOOD: F1-Score {avg_f1:.3f} indicates solid suggestion quality")
    elif avg_f1 >= 0.6:
        print(f"  ⚠️  ACCEPTABLE: F1-Score {avg_f1:.3f} suggests room for improvement")
    else:
        print(f"  ❌ POOR: F1-Score {avg_f1:.3f} indicates significant issues")
    
    if avg_recall >= 0.8:
        print(f"  ✅ EXCELLENT RECALL: {avg_recall:.1%} of ground truth detected")
    elif avg_recall >= 0.7:
        print(f"  ✅ GOOD RECALL: {avg_recall:.1%} of ground truth detected")
    else:
        print(f"  ⚠️  LOW RECALL: {avg_recall:.1%} of ground truth detected")
    
    if avg_precision >= 0.8:
        print(f"  ✅ EXCELLENT PRECISION: {avg_precision:.1%} of suggestions are correct")
    elif avg_precision >= 0.7:
        print(f"  ✅ GOOD PRECISION: {avg_precision:.1%} of suggestions are correct")
    else:
        print(f"  ⚠️  LOW PRECISION: {avg_precision:.1%} of suggestions are correct")
    
    print("\n" + "█" * 70)
    print("█ ✅ ASSIST FEATURE TESTING COMPLETE".center(70) + "█")
    print("█" * 70 + "\n")

if __name__ == "__main__":
    main()
