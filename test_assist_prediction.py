#!/usr/bin/env python3
"""Test assist prediction on demo image with Gaussian spots."""

import numpy as np
from pathlib import Path

from phage_annotator.demo import generate_dummy_image
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel


def test_assist_prediction():
    """Generate demo with Gaussian spots and test prediction."""
    
    # Generate demo image
    print("Generating demo image with 100 Gaussian spots...")
    demo_path = Path("demo_test.tif")
    generate_dummy_image(demo_path, mode="t")
    
    # Load the image
    import tifffile as tf
    with tf.TiffFile(demo_path) as tif:
        image = tif.asarray()
    
    print(f"Image shape: {image.shape}")
    print(f"Image dtype: {image.dtype}")
    print(f"Intensity range: [{image.min()}, {image.max()}]")
    
    # Test suggestion model on first frame
    print("\n" + "="*60)
    print("Testing assist prediction on first frame...")
    print("="*60)
    
    model = LocalPeakSuggestionModel(
        min_distance_px=6,
        max_points=200,
        threshold_quantile=0.995,
    )
    
    first_frame = image[0] if image.ndim == 3 else image
    suggestions = model.predict(
        first_frame,
        image_id=0,
        image_name="demo_test.tif",
        t=0,
        z=0,
        label="phage",
        strategy="raw",
    )
    
    print(f"\nDetected {len(suggestions)} suggestions")
    print(f"Expected: ~100 spots (some may not appear in all frames)")
    
    # Show top 10 suggestions
    print("\nTop 10 suggestions:")
    print(f"{'Rank':<6} {'X':<8} {'Y':<8} {'Score':<8} {'SNR':<8} {'Sigma':<8}")
    print("-" * 60)
    for i, s in enumerate(suggestions[:10], 1):
        snr = s.score_components.get('snr', 0)
        sigma = s.score_components.get('sigma_fit', 0)
        print(f"{i:<6} {s.x:<8.1f} {s.y:<8.1f} {s.score:<8.3f} {snr:<8.2f} {sigma:<8.2f}")
    
    # Analyze all suggestions
    if suggestions:
        scores = [s.score for s in suggestions]
        snrs = [s.score_components.get('snr', 0) for s in suggestions]
        sigmas = [s.score_components.get('sigma_fit', 0) for s in suggestions]
        
        print(f"\n\nSummary Statistics:")
        print(f"  Score range: [{min(scores):.3f}, {max(scores):.3f}]")
        print(f"  Mean score: {np.mean(scores):.3f}")
        print(f"  SNR range: [{min(snrs):.2f}, {max(snrs):.2f}]")
        print(f"  Mean SNR: {np.mean(snrs):.2f}")
        print(f"  Sigma range: [{min(sigmas):.2f}, {max(sigmas):.2f}]")
        print(f"  Mean sigma: {np.mean(sigmas):.2f}")
        print(f"  Expected sigma: 3-6 px")
    
    # Test on multiple frames to see detection consistency
    print("\n" + "="*60)
    print("Testing across all frames...")
    print("="*60)
    
    frame_counts = []
    for t in range(image.shape[0]):
        frame = image[t]
        frame_suggestions = model.predict(
            frame,
            image_id=0,
            image_name="demo_test.tif",
            t=t,
            z=0,
            label="phage",
            strategy="raw",
        )
        frame_counts.append(len(frame_suggestions))
    
    print(f"\nDetections per frame:")
    print(f"  Min: {min(frame_counts)}")
    print(f"  Max: {max(frame_counts)}")
    print(f"  Mean: {np.mean(frame_counts):.1f}")
    print(f"  Median: {np.median(frame_counts):.1f}")
    print(f"\nFrame-by-frame counts: {frame_counts}")
    
    # Clean up
    demo_path.unlink()
    
    return suggestions


if __name__ == "__main__":
    test_assist_prediction()
