"""Integration tests for coordinate transform usage in rendering pipeline.

Verifies that coordinate_transforms.py functions work correctly when used
in RenderContext and overlay coordinate transformations.
"""

from __future__ import annotations

import pytest

from phage_annotator.coordinate_transforms import (
    crop_to_full,
    display_to_full,
    full_to_crop,
    full_to_display,
)


class TestOverlayCoordinateTransforms:
    """Test annotation and ROI overlay coordinate transformations."""

    def test_full_annotation_to_display_simple_crop(self):
        """Annotation in full coords -> display coords with crop."""
        # Full image: 1000x800, annotation at (400, 500) in full space
        # Crop region: x=100, y=50, w=400, h=300
        crop_rect = (100, 50, 400, 300)
        
        # Annotation in full space
        y_full, x_full = 120.0, 350.0
        
        # Convert to display (no downsampling)
        y_disp, x_disp = full_to_display(y_full, x_full, crop_rect, downsample=1.0)
        
        # Should be (120-50, 350-100) = (70, 250)
        assert y_disp == pytest.approx(70.0)
        assert x_disp == pytest.approx(250.0)

    def test_display_annotation_to_full_roundtrip(self):
        """Roundtrip: full -> display -> full should recover original."""
        crop_rect = (200.0, 100.0, 400.0, 300.0)
        downsample = 2.0
        
        y_orig, x_orig = 250.0, 450.0
        
        # Full -> display
        y_disp, x_disp = full_to_display(y_orig, x_orig, crop_rect, downsample)
        
        # Display -> full
        y_recovered, x_recovered = display_to_full(y_disp, x_disp, crop_rect, downsample)
        
        # Should recover original (within floating-point precision)
        assert y_recovered == pytest.approx(y_orig, abs=1e-9)
        assert x_recovered == pytest.approx(x_orig, abs=1e-9)

    def test_roi_corner_points_transform(self):
        """Transform ROI bounding box corners from display to full coordinates."""
        crop_rect = (100.0, 50.0, 400.0, 300.0)
        downsample = 1.5
        
        # ROI corners in display space: (10, 20) to (110, 120)
        display_corners = [(10.0, 20.0), (10.0, 120.0), (110.0, 120.0), (110.0, 20.0)]
        
        # Transform to full space
        full_corners = [
            display_to_full(y, x, crop_rect, downsample)
            for y, x in display_corners
        ]
        
        # First corner: (10, 20) -> (10*1.5 + 50, 20*1.5 + 100) = (65, 130)
        assert full_corners[0][0] == pytest.approx(65.0)
        assert full_corners[0][1] == pytest.approx(130.0)
        
        # Check all corners are distinct
        assert len(set(full_corners)) == 4

    def test_downsampled_overlay_coordinates(self):
        """Overlay at different downsample levels maintains coherence."""
        crop_rect = (0.0, 0.0, 512.0, 512.0)
        
        # Point in full space
        y_full, x_full = 256.0, 256.0
        
        # At downsample=1.0 (no downsampling)
        y_d1, x_d1 = full_to_display(y_full, x_full, crop_rect, 1.0)
        assert y_d1 == pytest.approx(256.0)
        assert x_d1 == pytest.approx(256.0)
        
        # At downsample=2.0 (2x downsampling)
        y_d2, x_d2 = full_to_display(y_full, x_full, crop_rect, 2.0)
        assert y_d2 == pytest.approx(128.0)
        assert x_d2 == pytest.approx(128.0)
        
        # At downsample=4.0 (4x downsampling)
        y_d4, x_d4 = full_to_display(y_full, x_full, crop_rect, 4.0)
        assert y_d4 == pytest.approx(64.0)
        assert x_d4 == pytest.approx(64.0)

    def test_partial_crop_with_downsampling(self):
        """Complex case: partial crop + downsampling."""
        # Full image: 2000x1500, crop to (x=250, y=100, w=1000, h=800)
        crop_rect = (250.0, 100.0, 1000.0, 800.0)
        downsample = 2.5
        
        # Point in full space (within crop region)
        y_full, x_full = 350.0, 750.0
        
        # Convert to display
        y_disp, x_disp = full_to_display(y_full, x_full, crop_rect, downsample)
        
        # Manual calculation: (350-100)/2.5 = 100, (750-250)/2.5 = 200
        assert y_disp == pytest.approx(100.0)
        assert x_disp == pytest.approx(200.0)
        
        # Reverse transform
        y_rec, x_rec = display_to_full(y_disp, x_disp, crop_rect, downsample)
        assert y_rec == pytest.approx(y_full)
        assert x_rec == pytest.approx(x_full)

    def test_edge_case_zero_crop_offset(self):
        """Crop region at origin (0, 0) with full image size."""
        crop_rect = (0.0, 0.0, 1024.0, 768.0)
        downsample = 1.0
        
        y_full, x_full = 100.0, 200.0
        y_disp, x_disp = full_to_display(y_full, x_full, crop_rect, downsample)
        
        # No crop offset, no downsampling -> coordinates unchanged
        assert y_disp == pytest.approx(y_full)
        assert x_disp == pytest.approx(x_full)

    def test_edge_case_large_downsampling(self):
        """Handles large downsampling factors (extreme pyramids)."""
        crop_rect = (0.0, 0.0, 4096.0, 4096.0)
        downsample = 16.0  # 4x4 = 16x total downsampling
        
        y_full, x_full = 2048.0, 2048.0
        y_disp, x_disp = full_to_display(y_full, x_full, crop_rect, downsample)
        
        # 2048 / 16 = 128
        assert y_disp == pytest.approx(128.0)
        assert x_disp == pytest.approx(128.0)

    def test_negative_coordinates_within_crop(self):
        """Coordinates slightly before crop offset (clipping behavior)."""
        crop_rect = (100.0, 50.0, 400.0, 300.0)
        
        # Point just outside crop region (above)
        y_full, x_full = 40.0, 150.0
        
        # Convert to crop space (should give negative values)
        y_crop, x_crop = full_to_crop(y_full, x_full, crop_rect)
        assert y_crop == pytest.approx(-10.0)  # 40 - 50 = -10
        assert x_crop == pytest.approx(50.0)   # 150 - 100 = 50
        
        # When displayed, overlays handling these would skip or clip


class TestCropDownsampleComposition:
    """Test composition of crop and downsample transforms."""

    def test_crop_then_downsample(self):
        """Verify downsample scaling works after crop."""
        crop_rect = (100.0, 50.0, 400.0, 300.0)
        downsample = 2.0
        
        y_crop, x_crop = 100.0, 200.0
        
        # Manual downsample: crop / downsample_factor
        y_down, x_down = (y_crop / downsample, x_crop / downsample)
        
        assert y_down == pytest.approx(50.0)
        assert x_down == pytest.approx(100.0)

    def test_downsample_then_crop_vs_full_to_display(self):
        """Verify full_to_display matches the two-step process."""
        crop_rect = (200.0, 100.0, 500.0, 400.0)
        downsample = 2.0
        
        y_full, x_full = 300.0, 400.0
        
        # One-step: full -> display
        y_direct, x_direct = full_to_display(y_full, x_full, crop_rect, downsample)
        
        # Two-step: full -> crop -> downsample
        y_crop, x_crop = full_to_crop(y_full, x_full, crop_rect)
        y_indirect = y_crop / downsample
        x_indirect = x_crop / downsample
        
        assert y_direct == pytest.approx(y_indirect)
        assert x_direct == pytest.approx(x_indirect)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
