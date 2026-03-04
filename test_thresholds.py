#!/usr/bin/env python3
"""Test different threshold quantiles to find optimal setting."""

import numpy as np
from pathlib import Path
import tifffile as tf

from phage_annotator.demo import generate_dummy_image
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel


# Generate demo
demo_path = Path("demo_threshold_test.tif")
print("Generating demo...")
generate_dummy_image(demo_path, mode="t")

# Load
with tf.TiffFile(demo_path) as tif:
    image = tif.asarray()

frame_0 = image[0]

print(f"Image: {image.shape}, dtype: {image.dtype}")
print(f"Frame 0: min={frame_0.min()}, max={frame_0.max()}, mean={frame_0.mean():.1f}\n")

# Test different threshold quantiles
quantiles = [0.995, 0.997, 0.998, 0.999, 0.9995, 0.9999]

print("="*80)
print("TESTING DIFFERENT THRESHOLD QUANTILES")
print("="*80)

for q in quantiles:
    model = LocalPeakSuggestionModel(
        min_distance_px=6,
        max_points=200,
        threshold_quantile=q,
    )
    
    suggestions = model.predict(
        frame_0,
        image_id=0,
        image_name="demo",
        t=0,
        z=0,
        label="phage",
        strategy="raw",
    )
    
    # Get threshold used
    threshold = np.percentile(frame_0, q * 100)
    factor = threshold / frame_0.mean()
    
    # Analyze sigma values
    sigmas = [s.score_components.get('sigma_fit', 0) for s in suggestions]
    snrs = [s.score_components.get('snr', 0) for s in suggestions]
    
    print(f"\nQuantile {q:.4f} (threshold={threshold:.0f}, {factor:.2f}x mean):")
    print(f"  Detections: {len(suggestions)}")
    if suggestions:
        print(f"  Sigma range: [{min(sigmas):.2f}, {max(sigmas):.2f}], mean: {np.mean(sigmas):.2f} px")
        print(f"  SNR range: [{min(snrs):.2f}, {max(snrs):.2f}], mean: {np.mean(snrs):.2f}")
        print(f"  Top 5 SNRs: {[f'{s:.1f}' for s in sorted(snrs, reverse=True)[:5]]}")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

# Expected: 100 spots, each visible in 20-80% of frames
# For frame 0, expect roughly 10-80 spots
print("\nFor demo with 100 Gaussian spots (sigma 3-6 px, intensity 1.2-3x mean):")
print("  • Each spot visible in 20-80% of frames (4-16 frames out of 20)")
print("  • Expected spots per frame: 20-80 (average ~40-50)")
print("\nRecommended settings:")
print("  • threshold_quantile=0.9999 or higher (detects peaks >2x mean)")
print("  • OR use threshold_quantile=0.998 + min_distance_px=10 (filter close peaks)")
print("  • Expected detection: 40-60 spots with good SNR")

demo_path.unlink()
