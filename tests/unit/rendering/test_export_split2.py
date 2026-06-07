"""Split definitions from test_export.py."""


import pytest


def test_export_invalid_panel():
    """Test that invalid panel is rejected."""
    from phage_annotator.ui_qt.rendering.export_view import ExportOptions, validate_export_preflight
    
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
    from phage_annotator.ui_qt.rendering.export_view import ExportOptions, validate_export_preflight
    
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
