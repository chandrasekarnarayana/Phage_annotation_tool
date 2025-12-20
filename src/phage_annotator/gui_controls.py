"""Aggregate control mixins for UI handlers."""

from __future__ import annotations

from phage_annotator.gui_controls_density import DensityControlsMixin
from phage_annotator.gui_controls_display import DisplayControlsMixin
from phage_annotator.gui_controls_preferences import PreferencesControlsMixin
from phage_annotator.gui_controls_recorder import RecorderControlsMixin
from phage_annotator.gui_controls_results import ResultsControlsMixin
from phage_annotator.gui_controls_roi import RoiControlsMixin
from phage_annotator.gui_controls_smlm import SmlmControlsMixin
from phage_annotator.gui_controls_threshold import ThresholdControlsMixin


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
    """Composite mixin for GUI control handlers."""

