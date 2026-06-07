"""ROI and crop control handlers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.rendering.roi_crop_display import RoiCropDisplayMixin
from phage_annotator.ui_qt.rendering.roi_crop_templates import RoiCropTemplatesMixin
from phage_annotator.ui_qt.rendering.roi_crop_interaction import RoiCropInteractionMixin
from phage_annotator.ui_qt.rendering.roi_auto_detection import RoiAutoDetectionMixin


class RoiCropMixin(
    RoiCropDisplayMixin,
    RoiCropTemplatesMixin,
    RoiCropInteractionMixin,
    RoiAutoDetectionMixin,
):
    """Aggregated mixin for ROI and crop management."""
    pass
