"""Split definitions from assist_feature_benchmark.py."""


import csv
import sys
from pathlib import Path
from typing import List, Tuple
import numpy as np
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phage_annotator.demo import generate_dummy_image
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from tifffile import imread

from scripts.assist_feature_benchmark_split1 import test_suggestions_on_image

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
