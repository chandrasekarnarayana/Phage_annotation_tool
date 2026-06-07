"""ROI manager and measurement control handlers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.controls.roi_manager_core import RoiManagerCoreMixin
from phage_annotator.ui_qt.controls.roi_controls_style import RoiControlsStyleMixin
from phage_annotator.ui_qt.controls.roi_controls_tags import RoiControlsTagsMixin
from phage_annotator.ui_qt.controls.roi_controls_io import RoiControlsIOMixin
from phage_annotator.ui_qt.controls.roi_controls_batch import RoiControlsBatchMixin


class RoiControlsMixin(
    RoiManagerCoreMixin,
    RoiControlsStyleMixin,
    RoiControlsTagsMixin,
    RoiControlsIOMixin,
    RoiControlsBatchMixin,
):
    """Aggregated mixin for all ROI control handlers."""
    pass
