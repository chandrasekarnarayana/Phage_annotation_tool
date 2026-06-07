"""Utils dock roi widgets impl helpers for the phage annotation tool.

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


def make_roi_manager_widget(self) -> QtWidgets.QWidget:
    """Create roi manager widget for the current workflow."""
    if getattr(self, "roi_manager_widget", None) is not None:
        return self.roi_manager_widget
    widget = RoiManagerWidget(self.roi_manager, parent=self)
    self.roi_manager_widget = widget
    return widget

def make_results_widget(self) -> QtWidgets.QWidget:
    """Create results widget for the current workflow."""
    widget = ResultsTableWidget(parent=self)
    self.results_widget = widget
    return widget

def make_recorder_widget(self) -> QtWidgets.QWidget:
    """Create recorder widget for the current workflow."""
    widget = RecorderWidget(self.recorder, parent=self)
    self.recorder_widget = widget
    return widget

def make_hist_widget(self) -> QtWidgets.QWidget:
    """Create hist widget for the current workflow."""
    if self.hist_canvas is None:
        self.hist_fig = Figure(figsize=(4, 3))
        self.hist_canvas = FigureCanvasQTAgg(self.hist_fig)
        self.ax_hist = self.hist_fig.add_subplot(111)
    hist_container = QtWidgets.QWidget()
    hist_layout = QtWidgets.QVBoxLayout(hist_container)
    hist_layout.setContentsMargins(8, 8, 8, 8)
    hist_layout.setSpacing(6)
    controls = QtWidgets.QHBoxLayout()
    self.hist_chk = QtWidgets.QCheckBox("Histogram")
    self.hist_chk.setChecked(True)
    self.show_hist_chk = self.hist_chk
    self.hist_bins_spin = QtWidgets.QSpinBox()
    self.hist_bins_spin.setRange(16, 512)
    self.hist_bins_spin.setValue(self.hist_bins)
    self.hist_region_combo = QtWidgets.QComboBox()
    self.hist_region_combo.addItems(["Full image", "ROI", "Crop area"])
    if self.hist_region == "roi":
        self.hist_region_combo.setCurrentText("ROI")
    elif self.hist_region == "crop":
        self.hist_region_combo.setCurrentText("Crop area")
    else:
        self.hist_region_combo.setCurrentText("Full image")
    self.hist_scope_combo = QtWidgets.QComboBox()
    self.hist_scope_combo.addItems(["Current slice", "Sampled stack"])
    self.hist_scope_combo.setCurrentText(self._hist_scope_mode)
    controls.addWidget(self.hist_chk)
    controls.addWidget(QtWidgets.QLabel("Bins"))
    controls.addWidget(self.hist_bins_spin)
    controls.addWidget(self.hist_region_combo)
    controls.addWidget(self.hist_scope_combo)
    controls.addStretch(1)
    hist_layout.addLayout(controls)
    hist_layout.addWidget(self.hist_canvas)
    bc_group = QtWidgets.QGroupBox("B&C")
    bc_layout = QtWidgets.QGridLayout(bc_group)
    bc_layout.setContentsMargins(6, 6, 6, 6)
    bc_layout.setSpacing(6)

    self.bc_preview = QtWidgets.QLabel()
    self.bc_preview.setFixedHeight(60)
    self.bc_preview.setMinimumWidth(140)
    self.bc_preview.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )
    bc_layout.addWidget(self.bc_preview, 0, 0, 1, 3)

    self.bc_range_slider = SliderPanelDouble()
    self.bc_range_slider.setMinimumHeight(26)
    bc_layout.addWidget(QtWidgets.QLabel("Range"), 1, 0)
    bc_layout.addWidget(self.bc_range_slider, 1, 1, 1, 2)

    self.bc_min_spin = QtWidgets.QDoubleSpinBox()
    self.bc_max_spin = QtWidgets.QDoubleSpinBox()
    for spin in (self.bc_min_spin, self.bc_max_spin):
        spin.setDecimals(3)
        spin.setSingleStep(1.0)
        spin.setKeyboardTracking(False)
    bc_layout.addWidget(QtWidgets.QLabel("Minimum"), 2, 0)
    bc_layout.addWidget(self.bc_min_spin, 2, 1)
    bc_layout.addWidget(QtWidgets.QLabel("Maximum"), 3, 0)
    bc_layout.addWidget(self.bc_max_spin, 3, 1)

    self.bc_brightness_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_brightness_slider.setRange(-100, 100)
    self.bc_brightness_slider.setValue(0)
    self.bc_contrast_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_contrast_slider.setRange(-100, 100)
    self.bc_contrast_slider.setValue(0)
    bc_layout.addWidget(QtWidgets.QLabel("Brightness"), 4, 0)
    bc_layout.addWidget(self.bc_brightness_slider, 4, 1, 1, 2)
    bc_layout.addWidget(QtWidgets.QLabel("Contrast"), 5, 0)
    bc_layout.addWidget(self.bc_contrast_slider, 5, 1, 1, 2)

    bc_btns = QtWidgets.QHBoxLayout()
    self.bc_auto_btn = QtWidgets.QPushButton("Auto")
    self.bc_reset_btn = QtWidgets.QPushButton("Reset")
    self.bc_set_btn = QtWidgets.QPushButton("Set")
    self.bc_dialog_btn = QtWidgets.QPushButton("Dialog")
    self.bc_apply_btn = QtWidgets.QPushButton("Apply")
    bc_btns.addWidget(self.bc_auto_btn)
    bc_btns.addWidget(self.bc_reset_btn)
    bc_btns.addWidget(self.bc_set_btn)
    bc_btns.addWidget(self.bc_dialog_btn)
    bc_btns.addWidget(self.bc_apply_btn)
    bc_layout.addLayout(bc_btns, 6, 0, 1, 3)

    hist_layout.addWidget(bc_group)
    return hist_container

def make_profile_widget(self) -> QtWidgets.QWidget:
    """Create the profile (line-plot) widget and checkbox."""
    if self.profile_canvas is None:
        self.profile_fig = Figure(figsize=(4, 3))
        self.profile_canvas = FigureCanvasQTAgg(self.profile_fig)
        self.ax_line = self.profile_fig.add_subplot(111)
    profile_container = QtWidgets.QWidget()
    profile_layout = QtWidgets.QVBoxLayout(profile_container)
    profile_layout.setContentsMargins(8, 8, 8, 8)
    profile_layout.setSpacing(6)
    controls = QtWidgets.QHBoxLayout()
    self.profile_chk = QtWidgets.QCheckBox("Profile")
    self.profile_chk.setChecked(True)
    self.show_profile_chk = self.profile_chk  # Alias for backward compatibility
    controls.addWidget(self.profile_chk)
    controls.addStretch(1)
    profile_layout.addLayout(controls)
    profile_layout.addWidget(self.profile_canvas)
    return profile_container

def make_orthoview_widget(self) -> QtWidgets.QWidget:
    """Create orthoview widget for the current workflow."""
    widget = OrthoViewWidget(parent=self)
    self.orthoview_widget = widget
    return widget

def make_smlm_widget(self) -> QtWidgets.QWidget:
    """Create smlm widget for the current workflow."""
    widget = SmlmPanel(parent=self)
    self.smlm_panel = widget
    return widget

def make_threshold_widget(self) -> QtWidgets.QWidget:
    """Create threshold widget for the current workflow."""
    widget = ThresholdPanel(parent=self)
    self.threshold_panel = widget
    return widget

def make_particles_widget(self) -> QtWidgets.QWidget:
    """Create particles widget for the current workflow."""
    widget = AnalyzeParticlesPanel(parent=self)
    self.particles_panel = widget
    return widget

def make_channel_controls_widget(self) -> QtWidgets.QWidget:
    """Create the channel controls dock widget."""
    widget = ChannelControlPanel(parent=self)
    self.channel_panel = widget
    return widget
