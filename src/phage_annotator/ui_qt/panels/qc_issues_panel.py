"""QC issues panel for quality-control and problem review workflows.

Displays quality control issues detected by validators with filtering
and click-to-jump navigation.
"""

from __future__ import annotations

from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.session.qc_state import QCState


from phage_annotator.ui_qt.panels.qc_issues_panel_methods1 import _QCIssuesPanelMethods1
from phage_annotator.ui_qt.panels.qc_issues_panel_methods2 import _QCIssuesPanelMethods2

class QCIssuesPanel(_QCIssuesPanelMethods1, _QCIssuesPanelMethods2, QtWidgets.QWidget):
    """Dock widget panel displaying QC issues with filtering and navigation.

Provides issue browsing, severity-based filtering, and click-to-jump
navigation to annotation locations."""

    # Signals
    jump_to_location = QtCore.Signal(float, float, int, int, int)  # x, y, z, t, image_id
    issue_clicked = QtCore.Signal(str)  # issue_id
    issue_status_changed = QtCore.Signal(str, str)  # issue_id, status
    validation_requested = QtCore.Signal()  # Request re-validation
    export_requested = QtCore.Signal(str)  # Export format: "csv", "json", "html"
