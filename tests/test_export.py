"""
Export workflow validation tests (P4.2).

P4.2 Implementation: Unit tests for export functionality with preflight validation.
Tests cover:
  - Export preflight validation (DPI, marker size, ROI requirements, format checks)
  - Export scope validation
  - Export format validation
  - Export parameter bounds validation
"""

import pytest


@pytest.mark.parametrize("dpi,should_pass", [
    (72, True),   # min valid
    (150, True),  # typical
    (300, True),  # high
    (600, True),  # max valid
    (71, False),  # below min
    (601, False), # above max
])
def test_export_dpi_validation(dpi, should_pass):
    """Test DPI parameter validation (72-600)."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=dpi,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    if should_pass:
        assert result.is_valid, f"DPI {dpi} should be valid"
    else:
        assert not result.is_valid, f"DPI {dpi} should be invalid"


@pytest.mark.parametrize("marker_size,should_pass", [
    (1.0, True),   # min valid
    (40.0, True),  # typical
    (200.0, True), # max valid
    (0.5, False),  # below min
    (201.0, False) # above max
])
def test_export_marker_size_validation(marker_size, should_pass):
    """Test marker size parameter validation (1.0-200.0)."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=marker_size,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    if should_pass:
        assert result.is_valid, f"Marker size {marker_size} should be valid"
    else:
        assert not result.is_valid, f"Marker size {marker_size} should be invalid"


@pytest.mark.parametrize("roi_lw,should_pass", [
    (0.5, True),   # min valid
    (1.5, True),   # typical
    (6.0, True),   # max valid
    (0.4, False),  # below min
    (6.1, False)   # above max
])
def test_export_roi_linewidth_validation(roi_lw, should_pass):
    """Test ROI line width parameter validation (0.5-6.0)."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=roi_lw,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    if should_pass:
        assert result.is_valid, f"ROI line width {roi_lw} should be valid"
    else:
        assert not result.is_valid, f"ROI line width {roi_lw} should be invalid"


@pytest.mark.parametrize("fmt,should_pass", [
    ("png", True),
    ("PNG", True),
    ("tiff", True),
    ("TIFF", True),
    ("jpg", False),
    ("bmp", False)
])
def test_export_format_validation(fmt, should_pass):
    """Test format parameter validation (PNG/TIFF only)."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt=fmt,
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    if should_pass:
        assert result.is_valid, f"Format {fmt} should be valid"
    else:
        assert not result.is_valid, f"Format {fmt} should be invalid"


def test_export_roi_region_requires_roi():
    """Test that ROI-based regions require active ROI."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    # ROI bounds without ROI should fail
    opts = ExportOptions(
        panel="frame",
        region="roi bounds",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts, has_roi=False)
    assert not result.is_valid
    assert any("ROI" in err for err in result.errors)
    
    # Same options with ROI should pass
    result = validate_export_preflight(opts, has_roi=True)
    assert result.is_valid


def test_export_overlay_only_warning():
    """Test that overlay-only without overlays triggers warning."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=True,  # No overlays but overlay_only=True
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    assert result.is_valid  # Still valid, just warned
    assert any("Overlay" in w for w in result.warnings)


@pytest.mark.parametrize("panel", ["frame", "mean", "composite", "support", "std"])
def test_export_valid_panels(panel):
    """Test that all valid panels are accepted."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel=panel,
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    assert result.is_valid, f"Panel {panel} should be valid"


@pytest.mark.parametrize("region", ["full view", "crop", "roi bounds", "roi mask-clipped"])
def test_export_valid_regions(region):
    """Test that all valid regions are accepted (with ROI when needed)."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region=region,
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    # ROI-based regions need has_roi=True
    has_roi = "roi" in region.lower()
    result = validate_export_preflight(opts, has_roi=has_roi)
    assert result.is_valid, f"Region {region} should be valid"


def test_export_invalid_panel():
    """Test that invalid panel is rejected."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="invalid_panel",
        region="full view",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    assert not result.is_valid
    assert any("panel" in err.lower() for err in result.errors)


def test_export_invalid_region():
    """Test that invalid region is rejected."""
    from phage_annotator.export_view import ExportOptions, validate_export_preflight
    
    opts = ExportOptions(
        panel="frame",
        region="invalid_region",
        include_roi_outline=False,
        include_roi_fill=False,
        include_annotations=False,
        include_annotation_labels=False,
        include_particles=False,
        include_scalebar=False,
        include_overlay_text=False,
        marker_size=40.0,
        roi_line_width=1.5,
        dpi=150,
        fmt="png",
        overlay_only=False,
        transparent_bg=True,
        roi_mask_clip=False
    )
    
    result = validate_export_preflight(opts)
    assert not result.is_valid
    assert any("region" in err.lower() for err in result.errors)
