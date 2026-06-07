"""Threshold and particle analysis control handlers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.controls.threshold_controls_logic import ThresholdControlsLogicMixin
from phage_annotator.ui_qt.controls.threshold_controls_sliders import ThresholdControlsSlidersMixin
from phage_annotator.ui_qt.controls.threshold_controls_mask import ThresholdControlsMaskMixin
from phage_annotator.ui_qt.controls.threshold_controls_particles import ThresholdControlsParticlesMixin


class ThresholdControlsMixin(
    ThresholdControlsLogicMixin,
    ThresholdControlsSlidersMixin,
    ThresholdControlsMaskMixin,
    ThresholdControlsParticlesMixin,
):
    """Aggregated mixin for threshold and particle analysis control handlers."""
    pass
