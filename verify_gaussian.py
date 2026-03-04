#!/usr/bin/env python3
"""Manually verify Gaussian spots are being added correctly."""

import numpy as np
from pathlib import Path
import tifffile as tf


def manual_demo_generation():
    """Generate minimal demo with just one large Gaussian spot."""
    
    # Create blank image
    h, w = 1200, 1200
    image = np.full((h, w), 200, dtype=np.float32)  # Uniform background of 200
    
    # Add ONE large Gaussian spot in center
    y_center, x_center = 600, 600
    sigma = 5.0  # 5 pixel sigma
    peak_intensity = 600  # 3x background
    
    # Create Gaussian kernel
    kernel_size = int(sigma * 6)
    if kernel_size % 2 == 0:
        kernel_size += 1
    half = kernel_size // 2
    
    print(f"Creating Gaussian spot:")
    print(f"  Center: ({y_center}, {x_center})")
    print(f"  Sigma: {sigma} px")
    print(f"  Peak intensity: {peak_intensity} (3x background)")
    print(f"  Kernel size: {kernel_size}x{kernel_size}")
    
    # Generate Gaussian kernel
    ky, kx = np.ogrid[-half:half+1, -half:half+1]
    gaussian = np.exp(-(kx**2 + ky**2) / (2 * sigma**2))
    gaussian = gaussian / gaussian.max() * peak_intensity
    
    print(f"  Gaussian kernel:")
    print(f"    Max value: {gaussian.max():.1f}")
    print(f"    Min value: {gaussian.min():.3f}")
    print(f"    Center value: {gaussian[half, half]:.1f}")
    
    # Add to image
    y_start = y_center - half
    y_end = y_center + half + 1
    x_start = x_center - half
    x_end = x_center + half + 1
    
    image[y_start:y_end, x_start:x_end] += gaussian
    
    # Verify
    print(f"\nImage after adding spot:")
    print(f"  Max: {image.max():.1f}")
    print(f"  Value at center ({y_center}, {x_center}): {image[y_center, x_center]:.1f}")
    print(f"  Background mean (excluding center region): {np.mean(image[0:500, 0:500]):.1f}")
    
    # Show 11x11 patch around center
    print(f"\n  11x11 patch around center:")
    patch = image[y_center-5:y_center+6, x_center-5:x_center+6]
    for i, row in enumerate(patch):
        prefix = f"    y={y_center-5+i}: "
        print(prefix + " ".join(f"{val:5.0f}" for val in row))
    
    # Test Gaussian fit
    from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
    
    print(f"\n  Testing Gaussian fit:")
    amp, sig, res = LocalPeakSuggestionModel._gaussian_fit_features(
        image, y_center, x_center
    )
    print(f"    Amplitude: {amp:.1f} (expected ~{peak_intensity:.1f})")
    print(f"    Sigma: {sig:.2f} (expected ~{sigma:.2f})")
    print(f"    Residual: {res:.3f}")
    
    return image


# Generate and test
image = manual_demo_generation()

# Now test full demo
print("\n" + "="*70)
print("Testing full demo generation:")
print("="*70)

from phage_annotator.demo import generate_dummy_image

demo_path = Path("demo_verify.tif")
generate_dummy_image(demo_path, mode="t")

with tf.TiffFile(demo_path) as tif:
    demo_image = tif.asarray()

frame_0 = demo_image[0].astype(float)

# Find brightest pixel
max_val = frame_0.max()
y_max, x_max = np.unravel_index(frame_0.argmax(), frame_0.shape)

print(f"\nDemo frame 0:")
print(f"  Max value: {max_val:.0f} at ({y_max}, {x_max})")
print(f"  Mean: {frame_0.mean():.1f}")
print(f"  Factor: {max_val / frame_0.mean():.2f}x")

# Show 11x11 patch around brightest point
print(f"\n  11x11 patch around brightest point ({y_max}, {x_max}):")
patch = frame_0[y_max-5:y_max+6, x_max-5:x_max+6]
for i, row in enumerate(patch):
    prefix = f"    y={y_max-5+i}: "
    print(prefix + " ".join(f"{val:5.0f}" for val in row))

# Test Gaussian fit
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel

print(f"\n  Testing Gaussian fit on brightest peak:")
amp, sig, res = LocalPeakSuggestionModel._gaussian_fit_features(
    frame_0, y_max, x_max
)
print(f"    Amplitude: {amp:.1f}")
print(f"    Sigma: {sig:.2f} px (expected 3-6 px)")
print(f"    Residual: {res:.3f}")

demo_path.unlink()
