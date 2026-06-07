"""QC Thresholds settings panel for interactive tuning."""

from __future__ import annotations

from typing import Optional, Callable

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.session.qc_thresholds import QCThresholds


class QCThresholdsPanel(QtWidgets.QDialog):
    """Dialog for configuring QC thresholds."""

    thresholds_changed = QtCore.Signal()

    def __init__(self, thresholds: Optional[QCThresholds] = None,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("QC Threshold Settings")
        self.setMinimumSize(600, 500)
        self._thresholds = thresholds or QCThresholds()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("QC threshold configuration is available via the QC Issues panel."))
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_thresholds(self) -> QCThresholds:
        return self._thresholds


def show_qc_thresholds_dialog(
    parent: Optional[QtWidgets.QWidget] = None,
    thresholds: Optional[QCThresholds] = None,
) -> Optional[QCThresholds]:
    """Show QC thresholds dialog and return configured thresholds."""
    dialog = QCThresholdsPanel(thresholds=thresholds, parent=parent)
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        return dialog.get_thresholds()
    return None
