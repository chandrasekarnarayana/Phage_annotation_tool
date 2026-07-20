"""Display, playback, and general control handlers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.controls.display_controls_histogram import DisplayControlsHistogramMixin
from phage_annotator.ui_qt.controls.display_controls_channel import DisplayControlsChannel
from phage_annotator.ui_qt.controls.display_controls_playback import DisplayControlsPlayback
from phage_annotator.ui_qt.controls.display_controls_sync import DisplayControlsSyncMixin
from phage_annotator.ui_qt.controls.display_controls_modality import DisplayControlsModalityMixin
from phage_annotator.ui_qt.controls.display_controls_lut import DisplayControlsLutMixin
from phage_annotator.ui_qt.controls.display_contrast import DisplayContrastMixin
from phage_annotator.ui_qt.controls.axes_controls import AxesControlsMixin
from phage_annotator.session.signal_hub import emit_view_changed


class DisplayControlsMixin(
    DisplayControlsHistogramMixin,
    DisplayControlsChannel,
    DisplayControlsPlayback,
    DisplayControlsSyncMixin,
    DisplayControlsModalityMixin,
    DisplayControlsLutMixin,
    DisplayContrastMixin,
    AxesControlsMixin,
):
    """Aggregated mixin for display, playback, and control handlers."""
    pass
