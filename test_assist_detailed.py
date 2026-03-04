#!/usr/bin/env python3
"""Detailed analysis of assist prediction with ground truth comparison."""

import numpy as np
from pathlib import Path

from phage_annotator.demo import generate_dummy_image
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel


def generate_demo_with_ground_truth(n_spots=100, seed=42):
    """Generate demo and return ground truth spot locations."""
    
    rng = np.random.default_rng(seed)
    
    # Match parameters from demo.py
    frames = [(100, 300)] * 20  # 20 frames
    h, w = 1200, 1200
    n_frames = len(frames)
    
    # Calculate mean intensity
    mean_intensity = np.mean([np.mean(frame) for frame in frames])
    
    # Generate spot parameters
    ground_truth = []
    sigma_range = (3.0, 6.0)
    intensity_factor_range = (1.2, 3.0)
    
    for spot_id in range(n_spots):
        margin = 20
        y = rng.integers(margin, h - margin)
        x = rng.integers(margin, w - margin)
        sigma = rng.uniform(*sigma_range)
        intensity_factor = rng.uniform(*intensity_factor_range)
        peak_intensity = mean_intensity * intensity_factor
        
        # Determine visible frames
        if n_frames > 1:
            n_visible_frames = rng.integers(max(1, n_frames // 5), max(2, 4 * n_frames // 5))
            start_frame = rng.integers(0, max(1, n_frames - n_visible_frames))
            visible_frames = list(range(start_frame, start_frame + n_visible_frames))
        else:
            visible_frames = [0]
        
        ground_truth.append({
            'id': spot_id,
            'x': x,
            'y': y,
            'sigma': sigma,
            'peak_intensity': peak_intensity,
            'intensity_factor': intensity_factor,
            'visible_frames': visible_frames,
        })
    
    return ground_truth


def match_detections_to_ground_truth(suggestions, ground_truth_spots, max_distance=10.0):
    """Match detected suggestions to ground truth spots.
    
    Returns:
        matched: list of (suggestion, gt_spot, distance) tuples
        unmatched_suggestions: list of suggestions not matched to any spot
        unmatched_ground_truth: list of ground truth spots not detected
    """
    matched = []
    used_suggestions = set()
    used_gt = set()
    
    # For each ground truth spot, find closest suggestion
    for gt_spot in ground_truth_spots:
        best_dist = float('inf')
        best_suggestion = None
        best_idx = None
        
        for i, sug in enumerate(suggestions):
            if i in used_suggestions:
                continue
            
            dx = sug.x - gt_spot['x']
            dy = sug.y - gt_spot['y']
            dist = np.sqrt(dx*dx + dy*dy)
            
            if dist < best_dist and dist <= max_distance:
                best_dist = dist
                best_suggestion = sug
                best_idx = i
        
        if best_suggestion is not None:
            matched.append((best_suggestion, gt_spot, best_dist))
            used_suggestions.add(best_idx)
            used_gt.add(gt_spot['id'])
    
    unmatched_suggestions = [s for i, s in enumerate(suggestions) if i not in used_suggestions]
    unmatched_gt = [s for s in ground_truth_spots if s['id'] not in used_gt]
    
    return matched, unmatched_suggestions, unmatched_gt


def main():
    print("="*70)
    print("ASSIST PREDICTION EVALUATION WITH GROUND TRUTH")
    print("="*70)
    
    # Generate ground truth
    print("\nGenerating ground truth (100 Gaussian spots)...")
    ground_truth = generate_demo_with_ground_truth(n_spots=100, seed=42)
    
    # Generate demo image
    print("Generating demo image...")
    demo_path = Path("demo_test.tif")
    generate_dummy_image(demo_path, mode="t")
    
    # Load image
    import tifffile as tf
    with tf.TiffFile(demo_path) as tif:
        image = tif.asarray()
    
    print(f"\nImage shape: {image.shape}")
    print(f"Intensity range: [{image.min()}, {image.max()}]")
    
    # Test prediction model
    print("\n" + "="*70)
    print("TESTING ASSIST PREDICTION (Frame 0)")
    print("="*70)
    
    model = LocalPeakSuggestionModel(
        min_distance_px=6,
        max_points=200,
        threshold_quantile=0.995,
    )
    
    frame_0 = image[0]
    suggestions = model.predict(
        frame_0,
        image_id=0,
        image_name="demo_test.tif",
        t=0,
        z=0,
        label="phage",
        strategy="raw",
    )
    
    print(f"\nTotal detections: {len(suggestions)}")
    
    # Filter ground truth to frame 0
    gt_frame_0 = [spot for spot in ground_truth if 0 in spot['visible_frames']]
    print(f"Ground truth spots in frame 0: {len(gt_frame_0)}")
    
    # Match detections to ground truth
    print("\nMatching detections to ground truth (max distance: 10 px)...")
    matched, unmatched_sugg, unmatched_gt = match_detections_to_ground_truth(
        suggestions, gt_frame_0, max_distance=10.0
    )
    
    print(f"\n  True Positives: {len(matched)}")
    print(f"  False Positives: {len(unmatched_sugg)}")
    print(f"  False Negatives: {len(unmatched_gt)}")
    
    # Compute metrics
    precision = len(matched) / len(suggestions) if suggestions else 0
    recall = len(matched) / len(gt_frame_0) if gt_frame_0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n  Precision: {precision:.2%}")
    print(f"  Recall: {recall:.2%}")
    print(f"  F1 Score: {f1:.2%}")
    
    # Analyze matched spots
    if matched:
        print("\n" + "="*70)
        print("ANALYSIS OF MATCHED DETECTIONS")
        print("="*70)
        
        distances = [m[2] for m in matched]
        print(f"\nPosition accuracy:")
        print(f"  Mean distance: {np.mean(distances):.2f} px")
        print(f"  Median distance: {np.median(distances):.2f} px")
        print(f"  Max distance: {np.max(distances):.2f} px")
        
        # Compare detected sigma to ground truth sigma
        detected_sigmas = [m[0].score_components.get('sigma_fit', 0) for m in matched]
        gt_sigmas = [m[1]['sigma'] for m in matched]
        
        print(f"\nSigma analysis:")
        print(f"  Ground truth sigma range: [{min(gt_sigmas):.2f}, {max(gt_sigmas):.2f}] px")
        print(f"  Detected sigma range: [{min(detected_sigmas):.2f}, {max(detected_sigmas):.2f}] px")
        print(f"  Mean GT sigma: {np.mean(gt_sigmas):.2f} px")
        print(f"  Mean detected sigma: {np.mean(detected_sigmas):.2f} px")
        
        # Show some examples
        print("\n  Top 10 matches:")
        print(f"  {'Rank':<6} {'X_det':<8} {'Y_det':<8} {'X_gt':<8} {'Y_gt':<8} {'Dist':<8} {'σ_det':<8} {'σ_gt':<8}")
        print("  " + "-"*72)
        for i, (sug, gt, dist) in enumerate(matched[:10], 1):
            sigma_det = sug.score_components.get('sigma_fit', 0)
            sigma_gt = gt['sigma']
            print(f"  {i:<6} {sug.x:<8.1f} {sug.y:<8.1f} {gt['x']:<8.1f} {gt['y']:<8.1f} {dist:<8.2f} {sigma_det:<8.2f} {sigma_gt:<8.2f}")
    
    # Analyze false negatives
    if unmatched_gt:
        print("\n" + "="*70)
        print("ANALYSIS OF MISSED SPOTS (False Negatives)")
        print("="*70)
        
        fn_sigmas = [spot['sigma'] for spot in unmatched_gt]
        fn_intensities = [spot['intensity_factor'] for spot in unmatched_gt]
        
        print(f"\nMissed spots: {len(unmatched_gt)}")
        print(f"  Sigma range: [{min(fn_sigmas):.2f}, {max(fn_sigmas):.2f}] px")
        print(f"  Mean sigma: {np.mean(fn_sigmas):.2f} px")
        print(f"  Intensity factor range: [{min(fn_intensities):.2f}, {max(fn_intensities):.2f}]x")
        print(f"  Mean intensity factor: {np.mean(fn_intensities):.2f}x")
        
        print(f"\n  First 5 missed spots:")
        print(f"  {'X':<8} {'Y':<8} {'σ':<8} {'Intensity':<10}")
        print("  " + "-"*40)
        for spot in unmatched_gt[:5]:
            print(f"  {spot['x']:<8} {spot['y']:<8} {spot['sigma']:<8.2f} {spot['intensity_factor']:<10.2f}x")
    
    # Analyze false positives
    if unmatched_sugg:
        print("\n" + "="*70)
        print("ANALYSIS OF FALSE POSITIVES")
        print("="*70)
        
        fp_scores = [s.score for s in unmatched_sugg]
        fp_snrs = [s.score_components.get('snr', 0) for s in unmatched_sugg]
        fp_sigmas = [s.score_components.get('sigma_fit', 0) for s in unmatched_sugg]
        
        print(f"\nFalse positives: {len(unmatched_sugg)}")
        print(f"  Score range: [{min(fp_scores):.3f}, {max(fp_scores):.3f}]")
        print(f"  Mean score: {np.mean(fp_scores):.3f}")
        print(f"  SNR range: [{min(fp_snrs):.2f}, {max(fp_snrs):.2f}]")
        print(f"  Mean SNR: {np.mean(fp_snrs):.2f}")
        print(f"  Sigma range: [{min(fp_sigmas):.2f}, {max(fp_sigmas):.2f}]")
        print(f"  Mean sigma: {np.mean(fp_sigmas):.2f} px")
    
    # Clean up
    demo_path.unlink()
    
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print(f"\nThe assist prediction system achieved:")
    print(f"  • {recall:.0%} recall (detected {len(matched)}/{len(gt_frame_0)} spots)")
    print(f"  • {precision:.0%} precision ({len(matched)}/{len(suggestions)} detections correct)")
    print(f"  • {len(unmatched_sugg)} false positives (likely noise peaks)")
    
    if len(matched) < len(gt_frame_0) * 0.8:
        print(f"\n⚠️  Many spots missed! Consider lowering threshold_quantile.")
    elif len(unmatched_sugg) > len(matched):
        print(f"\n⚠️  Many false positives! Consider raising threshold_quantile.")
    else:
        print(f"\n✓  Good balance of precision and recall!")


if __name__ == "__main__":
    main()
