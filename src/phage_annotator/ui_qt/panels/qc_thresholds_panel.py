"""QC Thresholds settings panel for interactive tuning."""

from __future__ import annotations

from typing import Optional, Callable

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.session.qc_thresholds import QCThresholds
from phage_annotator.ui_qt.panels.qcthresholds_panel_ui import QcthresholdsPanelUiMixin
from phage_annotator.ui_qt.panels.qcthresholds_panel_controls import QcthresholdsPanelControlsMixin
from phage_annotator.ui_qt.panels.qcthresholds_panel_actions import QcthresholdsPanelActionsMixin


class QCThresholdsPanel(
    QcthresholdsPanelUiMixin,
    QcthresholdsPanelControlsMixin,
    QcthresholdsPanelActionsMixin,
    QtWidgets.QDialog,
):
    """Dialog for configuring QC thresholds.

    Organized into logical sections:
    - Annotation Spatial Constraints
    - Image Quality (Artifacts)
    - Statistical (Stochasticity)
    - Enable/Disable Checks
    """

    thresholds_changed = QtCore.Signal()


def show_qc_thresholds_dialog(
    parent: Optional[QtWidgets.QWidget] = None,
    thresholds: Optional[QCThresholds] = None,
) -> Optional[QCThresholds]:
    """Show QC thresholds dialog and return configured thresholds."""
    dialog = QCThresholdsPanel(thresholds=thresholds, parent=parent)
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        return dialog.get_thresholds()
    return None
