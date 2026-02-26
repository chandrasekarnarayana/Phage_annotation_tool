"""Aggregate control mixins for UI handlers."""

from __future__ import annotations

from phage_annotator.ui_qt.controls.density import DensityControlsMixin
from phage_annotator.ui_qt.controls.display import DisplayControlsMixin
from phage_annotator.ui_qt.controls.preferences import PreferencesControlsMixin
from phage_annotator.ui_qt.controls.recorder import RecorderControlsMixin
from phage_annotator.ui_qt.controls.results import ResultsControlsMixin
from phage_annotator.ui_qt.controls.roi import RoiControlsMixin
from phage_annotator.ui_qt.controls.smlm import SmlmControlsMixin
from phage_annotator.ui_qt.controls.threshold import ThresholdControlsMixin


class ControlsMixin(
    DisplayControlsMixin,
    RoiControlsMixin,
    ResultsControlsMixin,
    RecorderControlsMixin,
    PreferencesControlsMixin,
    DensityControlsMixin,
    SmlmControlsMixin,
    ThresholdControlsMixin,
):
    """Mixin for GUI control handlers."""
