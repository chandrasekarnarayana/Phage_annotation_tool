"""Export current view with overlays as PNG/TIFF."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from phage_annotator.rendering.scalebar import ScaleBarSpec, compute_scalebar



from phage_annotator.ui_qt.rendering.export_view_core import ExportValidationResult, validate_export_preflight, ExportOptions, render_view_to_array, render_layer_to_array
from phage_annotator.ui_qt.rendering.export_render_impl import render_chunk_to_array as _render_chunk_impl
from phage_annotator.ui_qt.rendering.export_writers import StreamingExportWriter, TiffStreamWriter, PngStreamWriter, create_streaming_writer
from phage_annotator.ui_qt.rendering.export_writers import calculate_export_chunks


def render_chunk_to_array(*args, **kwargs):
    """Render a chunk while honoring façade-level render monkeypatches."""
    original_render = _render_chunk_impl.__globals__.get("render_view_to_array")
    _render_chunk_impl.__globals__["render_view_to_array"] = render_view_to_array
    try:
        return _render_chunk_impl(*args, **kwargs)
    finally:
        _render_chunk_impl.__globals__["render_view_to_array"] = original_render
