#!/usr/bin/env python3
"""Debug: visualize what's actually in the demo image."""

import numpy as np
from pathlib import Path
import tifffile as tf

from phage_annotator.demo import generate_dummy_image


# Generate demo
demo_path = Path("demo_debug.tif")
print("Generating demo...")
generate_dummy_image(demo_path, mode="t")

# Load and analyze
with tf.TiffFile(demo_path) as tif:
    image = tif.asarray()

print(f"Shape: {image.shape}")
print(f"Dtype: {image.dtype}")

# Analyze first frame
frame_0 = image[0].astype(float)
print(f"\nFrame 0 statistics:")
print(f"  Min: {frame_0.min()}")
print(f"  Max: {frame_0.max()}")
print(f"  Mean: {frame_0.mean():.1f}")
print(f"  Median: {np.median(frame_0):.1f}")
print(f"  Std: {frame_0.std():.1f}")

# Count pixels above various thresholds
background_mean = frame_0.mean()
thresholds = [1.2, 1.5, 2.0, 2.5, 3.0]
print(f"\nPixels above intensity thresholds:")
for factor in thresholds:
    threshold = background_mean * factor
    count = np.sum(frame_0 >= threshold)
    print(f"  {factor}x mean ({threshold:.0f}): {count} pixels")

# Check 99.5th percentile (used by model)
percentile_995 = np.percentile(frame_0, 99.5)
print(f"\n99.5th percentile: {percentile_995:.1f}")
print(f"Pixels above 99.5th percentile: {np.sum(frame_0 >= percentile_995)}")

# Find actual peaks manually
from scipy.ndimage import maximum_filter

# Use maximum filter to find local maxima
footprint = 3
max_filt = maximum_filter(frame_0, size=footprint, mode='nearest')
is_peak = (frame_0 == max_filt) & (frame_0 >= percentile_995)
peak_coords = np.column_stack(np.nonzero(is_peak))

print(f"\nLocal maxima above 99.5th percentile: {len(peak_coords)}")

# Show top peaks
peak_values = [frame_0[y, x] for y, x in peak_coords]
sorted_indices = np.argsort(peak_values)[::-1]

print(f"\nTop 20 peaks:")
print(f"{'Rank':<6} {'Y':<8} {'X':<8} {'Value':<8} {'Factor':<8}")
print("-" * 50)
for i, idx in enumerate(sorted_indices[:20], 1):
    y, x = peak_coords[idx]
    value = frame_0[y, x]
    factor = value / background_mean
    print(f"{i:<6} {y:<8} {x:<8} {value:<8.0f} {factor:<8.2f}x")

# Visualize local region around brightest peak
if len(peak_coords) > 0:
    y, x = peak_coords[sorted_indices[0]]
    print(f"\n5x5 patch around brightest peak at ({y}, {x}):")
    patch = frame_0[y-2:y+3, x-2:x+3]
    for row in patch:
        print("  " + " ".join(f"{val:5.0f}" for val in row))

demo_path.unlink()
