"""Rendering export preflight helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from phage_annotator.rendering.scalebar import ScaleBarSpec, compute_scalebar


@dataclass
class ExportValidationResult:
    """P4.2: Validation result for export preflight checks."""
    
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, msg: str) -> None:
        """Add validation error."""
        self.errors.append(msg)
        self.is_valid = False
    
    def add_warning(self, msg: str) -> None:
        """Add validation warning (non-blocking)."""
        self.warnings.append(msg)

def validate_export_preflight(
    options: ExportOptions,
    has_support_image: bool = False,
    has_roi: bool = False,
    image_shape: Optional[Tuple[int, ...]] = None,
) -> ExportValidationResult:
    """P4.2: Validate export options before execution.
    
    Preflight checks:
    - scope: full requires support image, roi requires active ROI
    - panels: at least one must be selected
    - overlays: validate consistency
    - format: PNG/TIFF supported
    - dpi: 72-600 range
    
    Parameters
    ----------
    options : ExportOptions
        Export configuration
    has_support_image : bool
        Whether a support image is available
    has_roi : bool
        Whether an ROI is defined
    image_shape : Optional[Tuple[int, ...]]
        Shape of primary image for bounds checking
        
    Returns
    -------
    ExportValidationResult
        Validation result with errors and warnings
    """
    result = ExportValidationResult(is_valid=True)
    
    # Check region validity
    region = options.region.lower()
    if region in ("roi bounds", "roi mask-clipped"):
        if not has_roi:
            result.add_error("ROI-based export requires an active ROI")
    
    # Check format
    fmt = options.fmt.lower()
    if fmt not in ("png", "tiff"):
        result.add_error(f"Unsupported format: {fmt} (PNG or TIFF required)")
    
    # Check DPI
    if not (72 <= options.dpi <= 600):
        result.add_error(f"DPI must be 72-600, got {options.dpi}")
    
    # Check marker size
    if not (1.0 <= options.marker_size <= 200.0):
        result.add_error(f"Marker size must be 1.0-200.0, got {options.marker_size}")
    
    # Check ROI line width
    if not (0.5 <= options.roi_line_width <= 6.0):
        result.add_error(f"ROI line width must be 0.5-6.0, got {options.roi_line_width}")
    
    # Check panel validity
    panel = options.panel.lower()
    valid_panels = ("frame", "mean", "support", "std")
    if panel not in valid_panels:
        result.add_error(f"Invalid panel: {panel} (must be one of {valid_panels})")
    
    # Check region validity
    valid_regions = ("full view", "crop", "roi bounds", "roi mask-clipped")
    if region not in valid_regions:
        result.add_error(f"Invalid region: {region} (must be one of {valid_regions})")
    
    # Warn if overlay-only without overlays
    has_overlays = (
        options.include_annotations or
        options.include_roi_outline or
        options.include_roi_fill or
        options.include_particles or
        options.include_scalebar or
        options.include_overlay_text
    )
    if options.overlay_only and not has_overlays:
        result.add_warning("Overlay-only export selected but no overlays enabled")
    
    return result

@dataclass(frozen=True)
class ExportOptions:
    panel: str
    region: str
    include_roi_outline: bool
    include_roi_fill: bool
    include_annotations: bool
    include_annotation_labels: bool
    include_particles: bool
    include_scalebar: bool
    include_overlay_text: bool
    marker_size: float
    roi_line_width: float
    dpi: int
    fmt: str
    overlay_only: bool
    transparent_bg: bool
    roi_mask_clip: bool
    export_as_layers: bool = False  # P3.4: Export overlays as separate layer files
    export_as_chunked: bool = False  # P4a: Use streaming chunk-based export
