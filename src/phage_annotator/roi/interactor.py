"""Matplotlib ROI interactor for rectangle and circle ROIs."""

from __future__ import annotations

from phage_annotator.roi.interactor_core import RoiInteractorCoreMixin
from phage_annotator.roi.interactor_events import RoiInteractorEventMixin
from phage_annotator.roi.interactor_geometry import RoiInteractorGeometryMixin
from phage_annotator.roi.interactor_render import RoiInteractorRenderMixin
from phage_annotator.roi.interactor_types import CircleROI, CoordinateMapper, RectROI


class RoiInteractor(
    RoiInteractorCoreMixin,
    RoiInteractorEventMixin,
    RoiInteractorGeometryMixin,
    RoiInteractorRenderMixin,
):
    """Interactive ROI editor for a Matplotlib Axes."""

    pass
