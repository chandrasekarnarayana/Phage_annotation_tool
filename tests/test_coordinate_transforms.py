"""Unit tests for coordinate transformation module."""

import pytest

from phage_annotator.coordinate_transforms import (canvas_to_display, crop_rect_intersection,
                                                   crop_to_full, display_to_canvas, display_to_full,
                                                   full_to_crop, full_to_display,
                                                   roi_rect_in_display_coords)


class TestCropConversions:
    """Test crop <-> full coordinate conversions."""

    def test_crop_to_full_identity(self):
        """Test conversion with zero crop offset."""
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        y_disp, x_disp = 10.0, 20.0
        y_full, x_full = crop_to_full(y_disp, x_disp, crop_rect)
        assert y_full == 10.0
        assert x_full == 20.0

    def test_crop_to_full_with_offset(self):
        """Test conversion with crop offset."""
        crop_rect = (50.0, 30.0, 100.0, 100.0)
        y_disp, x_disp = 10.0, 20.0
        y_full, x_full = crop_to_full(y_disp, x_disp, crop_rect)
        assert y_full == 40.0  # 10 + 30
        assert x_full == 70.0  # 20 + 50

    def test_full_to_crop_identity(self):
        """Test inverse conversion with zero crop offset."""
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        y_full, x_full = 10.0, 20.0
        y_disp, x_disp = full_to_crop(y_full, x_full, crop_rect)
        assert y_disp == 10.0
        assert x_disp == 20.0

    def test_full_to_crop_with_offset(self):
        """Test inverse conversion with crop offset."""
        crop_rect = (50.0, 30.0, 100.0, 100.0)
        y_full, x_full = 40.0, 70.0
        y_disp, x_disp = full_to_crop(y_full, x_full, crop_rect)
        assert y_disp == 10.0
        assert x_disp == 20.0

    def test_crop_full_roundtrip(self):
        """Test roundtrip conversion."""
        crop_rect = (25.0, 15.0, 200.0, 150.0)
        y_orig, x_orig = 50.5, 75.3
        y_crop, x_crop = full_to_crop(y_orig, x_orig, crop_rect)
        y_full, x_full = crop_to_full(y_crop, x_crop, crop_rect)
        assert abs(y_full - y_orig) < 1e-9
        assert abs(x_full - x_orig) < 1e-9


class TestDisplayConversions:
    """Test full <-> display coordinate conversions with downsampling."""

    def test_full_to_display_no_downsample(self):
        """Test with downsample=1."""
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        y_full, x_full = 20.0, 30.0
        y_disp, x_disp = full_to_display(y_full, x_full, crop_rect, downsample=1.0)
        assert y_disp == 20.0
        assert x_disp == 30.0

    def test_full_to_display_with_downsample(self):
        """Test with downsample=2."""
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        y_full, x_full = 40.0, 60.0
        y_disp, x_disp = full_to_display(y_full, x_full, crop_rect, downsample=2.0)
        assert y_disp == 20.0
        assert x_disp == 30.0

    def test_display_to_full_no_downsample(self):
        """Test inverse with downsample=1."""
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        y_disp, x_disp = 20.0, 30.0
        y_full, x_full = display_to_full(y_disp, x_disp, crop_rect, downsample=1.0)
        assert y_full == 20.0
        assert x_full == 30.0

    def test_display_to_full_with_downsample(self):
        """Test inverse with downsample=2."""
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        y_disp, x_disp = 20.0, 30.0
        y_full, x_full = display_to_full(y_disp, x_disp, crop_rect, downsample=2.0)
        assert y_full == 40.0
        assert x_full == 60.0

    def test_full_display_roundtrip_with_crop_and_downsample(self):
        """Test roundtrip with both crop and downsample."""
        crop_rect = (50.0, 30.0, 200.0, 200.0)
        downsample = 2.5
        y_orig, x_orig = 100.0, 150.0
        y_disp, x_disp = full_to_display(y_orig, x_orig, crop_rect, downsample)
        y_full, x_full = display_to_full(y_disp, x_disp, crop_rect, downsample)
        assert abs(y_full - y_orig) < 1e-9
        assert abs(x_full - x_orig) < 1e-9


class TestCanvasConversions:
    """Test matplotlib canvas <-> display conversions."""

    def test_canvas_to_display(self):
        """Test canvas to display conversion."""
        x_canvas, y_canvas = 30.0, 20.0
        y_disp, x_disp = canvas_to_display(x_canvas, y_canvas)
        assert y_disp == 20.0
        assert x_disp == 30.0

    def test_display_to_canvas(self):
        """Test display to canvas conversion."""
        y_disp, x_disp = 20.0, 30.0
        x_canvas, y_canvas = display_to_canvas(y_disp, x_disp)
        assert x_canvas == 30.0
        assert y_canvas == 20.0

    def test_canvas_display_roundtrip(self):
        """Test roundtrip."""
        x_orig, y_orig = 15.5, 25.3
        y_disp, x_disp = canvas_to_display(x_orig, y_orig)
        x_canvas, y_canvas = display_to_canvas(y_disp, x_disp)
        assert abs(x_canvas - x_orig) < 1e-9
        assert abs(y_canvas - y_orig) < 1e-9


class TestCropIntersection:
    """Test crop rectangle clipping."""

    def test_crop_fully_inside_image(self):
        """Test crop rect fully inside image."""
        crop_rect = (10.0, 10.0, 50.0, 50.0)
        image_shape = (100, 100)
        clipped = crop_rect_intersection(crop_rect, image_shape)
        assert clipped == crop_rect

    def test_crop_exceeds_bounds(self):
        """Test crop rect that exceeds image bounds."""
        crop_rect = (50.0, 50.0, 100.0, 100.0)
        image_shape = (100, 100)
        x, y, w, h = crop_rect_intersection(crop_rect, image_shape)
        assert x == 50.0
        assert y == 50.0
        assert w == 50.0  # Clamped to 100-50
        assert h == 50.0  # Clamped to 100-50

    def test_crop_negative_offset(self):
        """Test crop with negative offset."""
        crop_rect = (-10.0, -10.0, 50.0, 50.0)
        image_shape = (100, 100)
        x, y, w, h = crop_rect_intersection(crop_rect, image_shape)
        assert x == 0.0  # Clamped to 0
        assert y == 0.0  # Clamped to 0
        assert w > 0.0
        assert h > 0.0


class TestRoiInDisplay:
    """Test ROI projection to display coordinates."""

    def test_roi_projection_no_crop_no_downsample(self):
        """Test ROI projection with no transformations."""
        roi_rect = (10.0, 20.0, 50.0, 40.0)  # x, y, w, h
        crop_rect = (0.0, 0.0, 100.0, 100.0)
        x_disp, y_disp, w_disp, h_disp = roi_rect_in_display_coords(
            roi_rect, crop_rect, downsample=1.0
        )
        assert x_disp == 10.0
        assert y_disp == 20.0
        assert w_disp == 50.0
        assert h_disp == 40.0

    def test_roi_projection_with_crop(self):
        """Test ROI projection with crop."""
        roi_rect = (50.0, 30.0, 40.0, 40.0)
        crop_rect = (20.0, 10.0, 100.0, 100.0)
        x_disp, y_disp, w_disp, h_disp = roi_rect_in_display_coords(
            roi_rect, crop_rect, downsample=1.0
        )
        assert x_disp == 30.0  # 50 - 20
        assert y_disp == 20.0  # 30 - 10
        assert w_disp == 40.0
        assert h_disp == 40.0

    def test_roi_projection_with_downsample(self):
        """Test ROI projection with downsampling."""
        roi_rect = (20.0, 40.0, 100.0, 80.0)
        crop_rect = (0.0, 0.0, 200.0, 200.0)
        x_disp, y_disp, w_disp, h_disp = roi_rect_in_display_coords(
            roi_rect, crop_rect, downsample=2.0
        )
        assert x_disp == 10.0  # 20 / 2
        assert y_disp == 20.0  # 40 / 2
        assert abs(w_disp - 50.0) < 1e-9  # 100 / 2
        assert abs(h_disp - 40.0) < 1e-9  # 80 / 2
