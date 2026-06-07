"""Utils dock sidebar widgets helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import html
import logging
import pathlib
import re
from typing import List, Optional

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.roi.widgets import RoiManagerWidget
from phage_annotator.ui_qt.panels.particles import AnalyzeParticlesPanel
from phage_annotator.ui_qt.panels.channel_controls import ChannelControlPanel
from phage_annotator.ui_qt.panels.density import DensityPanel
from phage_annotator.ui_qt.panels.advanced_settings_panel import AdvancedSettingsPanel
from phage_annotator.ui_qt.panels.qc_issues_panel import QCIssuesPanel
from phage_annotator.ui_qt.panels.review_queue_panel import ReviewQueuePanel
from phage_annotator.ui_qt.panels.status_details_panel import StatusDetailsPanel
from phage_annotator.ui_qt.panels.recorder import RecorderWidget
from phage_annotator.ui_qt.panels.registry import PanelConstraints, PanelSpec
from phage_annotator.ui_qt.panels.threshold import ThresholdPanel
from phage_annotator.ui_qt.docks.metadata_dock import MetadataDock
from phage_annotator.ui_qt.widgets.results_table import ResultsTableWidget
from phage_annotator.ui_qt.widgets.orthoview import OrthoViewWidget
from phage_annotator.ui_qt.widgets.slider_panel_double import SliderPanelDouble
from phage_annotator.ui_qt.panels.smlm import SmlmPanel
from phage_annotator.ui_qt.services.status import ManagedStatusBar

logger = logging.getLogger(__name__)


PANEL_TAB_GROUPS = {
    # Right inspect panels are intentionally NOT tabified; they are shown as
    # distinct panels via right-sidebar selection.
    "tools_roi": ("roi", "roi_manager", "results", "orthoview", "metadata"),
    "plots_hist": ("hist", "profile"),
    "system": ("logs", "performance", "recorder"),
}
# so placement recipes are defined in one declarative source of truth.


def get_panel_opened_by(self, panel_id: str) -> str:
    """Return panel opened by for the current workflow."""
    state = getattr(self, "_panel_opened_by", {}) or {}
    return str(state.get(str(panel_id), "unknown"))

def make_sidebar_widget(self) -> QtWidgets.QWidget:
    """Create sidebar widget for the current workflow."""
    return self._build_sidebar_stack()

def make_annotations_widget(self) -> QtWidgets.QWidget:
    """Create annotations widget for the current workflow."""
    return self.annotation_table_panel

def make_review_queue_widget(self) -> QtWidgets.QWidget:
    """Create review queue widget for the current workflow."""
    widget = ReviewQueuePanel(parent=self)
    self.review_queue_panel = widget
    self.suggestion_explain_panel = widget.explain_panel
    return widget

def make_advanced_settings_widget(self) -> QtWidgets.QWidget:
    """Create advanced settings widget for the current workflow."""
    widget = AdvancedSettingsPanel(parent=self)
    self.advanced_settings_panel = widget
    return widget

def make_status_details_widget(self) -> QtWidgets.QWidget:
    """Create status details widget for the current workflow."""
    widget = StatusDetailsPanel(parent=self)
    self.status_details_panel = widget
    if getattr(self, "status_service", None) is not None:
        self.status_service.bind_widgets(
            context_label=self.status_context_lbl,
            state_label=self.status_state_lbl,
            metric_label=self.status_metric_lbl,
            progress_label=self.progress_label,
            progress_bar=self.progress_bar,
            progress_cancel_btn=self.progress_cancel_btn,
            progress_cancel_all_btn=self.progress_cancel_all_btn,
            details_panel=widget,
            log_status_label=getattr(self, "status_logs_lbl", None),
        )
    return widget

def make_advanced_analysis_widget(self) -> QtWidgets.QWidget:
    """Create progressive-disclosure container for advanced assist analysis."""
    container = QtWidgets.QWidget(parent=self)
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(3)

    intro = QtWidgets.QLabel(
        "Advanced assist analysis tools.\n"
        "Hidden by default to reduce onboarding load."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    toolbox = QtWidgets.QToolBox(container)
    section_explain = QtWidgets.QWidget()
    explain_layout = QtWidgets.QVBoxLayout(section_explain)
    explain_layout.setContentsMargins(3, 3, 3, 3)
    explain_layout.addWidget(
        QtWidgets.QLabel("Inspect score components, patch preview, and staleness.")
    )
    self.advanced_open_explain_btn = QtWidgets.QPushButton("Open Why This Suggestion")
    explain_layout.addWidget(self.advanced_open_explain_btn)
    explain_layout.addStretch(1)
    toolbox.addItem(section_explain, "Explain Panel")

    section_train = QtWidgets.QWidget()
    train_layout = QtWidgets.QVBoxLayout(section_train)
    train_layout.setContentsMargins(3, 3, 3, 3)
    train_layout.addWidget(
        QtWidgets.QLabel("Training controls and minima are in Settings -> Advanced.")
    )
    self.advanced_open_training_btn = QtWidgets.QPushButton("Open Training Controls")
    train_layout.addWidget(self.advanced_open_training_btn)
    self.advanced_train_now_btn = QtWidgets.QPushButton("Train Ranker Now")
    train_layout.addWidget(self.advanced_train_now_btn)
    train_layout.addStretch(1)
    toolbox.addItem(section_train, "Training Controls")

    section_cal = QtWidgets.QWidget()
    cal_layout = QtWidgets.QVBoxLayout(section_cal)
    cal_layout.setContentsMargins(3, 3, 3, 3)
    cal_layout.addWidget(
        QtWidgets.QLabel("Inspect calibration and proposal metrics diagnostics.")
    )
    self.advanced_open_calib_btn = QtWidgets.QPushButton("Open Calibration Diagnostics")
    cal_layout.addWidget(self.advanced_open_calib_btn)
    cal_layout.addStretch(1)
    toolbox.addItem(section_cal, "Calibration Diagnostics")

    layout.addWidget(toolbox)
    layout.addStretch(1)
    return container
