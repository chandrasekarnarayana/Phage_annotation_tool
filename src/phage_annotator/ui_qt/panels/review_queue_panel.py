"""Review queue panel for assisted-annotation triage workflows."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.panels.suggestion_explain_panel import SuggestionExplainPanel
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger


from phage_annotator.ui_qt.panels.review_queue import ReviewQueueMixin
from phage_annotator.ui_qt.panels.review_queue_ui import ReviewQueueUiMixin

class ReviewQueuePanel(ReviewQueueMixin, ReviewQueueUiMixin, QtWidgets.QWidget):
    """Right-dock panel showing current uncertain suggestion and queue progress."""

    accept_requested = QtCore.Signal()
    accept_next_requested = QtCore.Signal()
    accept_all_green_requested = QtCore.Signal()
    reject_requested = QtCore.Signal()
    skip_requested = QtCore.Signal()
    next_uncertain_requested = QtCore.Signal()
    apply_offset_requested = QtCore.Signal(int, float, float)
    suggestion_row_selected = QtCore.Signal(int)
    decision_requested = QtCore.Signal(str, str)
    suggest_points_requested = QtCore.Signal()
    clear_suggestions_requested = QtCore.Signal()
    show_suggestions_toggled = QtCore.Signal(bool)
