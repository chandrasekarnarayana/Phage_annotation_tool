"""SMLM (ThunderSTORM/Deep-STORM) control handlers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.controls.smlm_controls_channel import SmlmControlsChannelMixin
from phage_annotator.ui_qt.controls.smlm_controls_filtering import SmlmControlsFilteringMixin
from phage_annotator.ui_qt.controls.smlm_controls_reconstruction import SmlmControlsReconstructionMixin
from phage_annotator.ui_qt.controls.smlm_controls_export import SmlmControlsExportMixin
from phage_annotator.ui_qt.controls.smlm_controls_setup import SmlmControlsSetupMixin
from phage_annotator.ui_qt.controls.smlm_controls_runbook import SmlmControlsRunbookMixin
from phage_annotator.ui_qt.controls.smlm_controls_output import SmlmControlsOutputMixin


class SmlmControlsMixin(
    SmlmControlsChannelMixin,
    SmlmControlsFilteringMixin,
    SmlmControlsReconstructionMixin,
    SmlmControlsExportMixin,
    SmlmControlsSetupMixin,
    SmlmControlsRunbookMixin,
    SmlmControlsOutputMixin,
):
    """Aggregated mixin for all SMLM control handlers."""
    pass
