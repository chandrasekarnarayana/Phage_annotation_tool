"""Renderer overlay methods: annotations, ROI outlines, particles, text, scalebar."""

from __future__ import annotations

# Unified logging through service framework
try:
    from phage_annotator.framework import get_log_service
    _logger = get_log_service().get_logger(__name__)
except (ImportError, RuntimeError, AttributeError):
    import logging
    _logger = logging.getLogger(__name__)

from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from phage_annotator.roi.interactor import CircleROI, RectROI
from phage_annotator.rendering.mpl_canvas import RenderContext
from phage_annotator.rendering.mpl_utils import _clear_overlays


from phage_annotator.rendering.renderer_overlays_methods1 import _RendererOverlaysMixinMethods1
from phage_annotator.rendering.renderer_overlays_methods2 import _RendererOverlaysMixinMethods2

class RendererOverlaysMixin(_RendererOverlaysMixinMethods1, _RendererOverlaysMixinMethods2):
    """Mixin providing overlay drawing methods for the Renderer."""

    pass
