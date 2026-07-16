"""Extracted method group 2 for UiSetupRegistryMixin."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.utils import ui_docks
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)


def make_logs_widget(self) -> QtWidgets.QWidget:
    """Create logs text area widget for action/event logs panel."""
    widget = QtWidgets.QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setPlaceholderText("Action / event log output will appear here.")
    widget.setObjectName("logs_text_widget")
    self.logs_widget = widget
    return widget


def make_metadata_widget(self) -> QtWidgets.QWidget:
    """Create metadata inspector dock widget."""
    from phage_annotator.ui_qt.docks.metadata_dock import MetadataDock
    widget = MetadataDock(parent=self)
    self.metadata_dock_widget = widget
    return widget


def make_density_widget(self) -> QtWidgets.QWidget:
    """Create density analysis panel widget."""
    from phage_annotator.ui_qt.panels.density import DensityPanel
    widget = DensityPanel(parent=self)
    self.density_panel = widget
    return widget


def make_qc_issues_widget(self) -> QtWidgets.QWidget:
    """Create QC issues panel widget."""
    from phage_annotator.ui_qt.panels.qc_issues_panel import QCIssuesPanel
    widget = QCIssuesPanel(parent=self)
    self.qc_issues_panel = widget
    return widget



class DockAnalysisWidgetsMixin:
    """Method group 2 extracted from UiSetupRegistryMixin."""

    def _make_annotations_widget(self) -> QtWidgets.QWidget:
        """Create annotations widget for the current workflow."""
        return ui_docks.make_annotations_widget(self)
    def _make_review_queue_widget(self) -> QtWidgets.QWidget:
        """Create review queue widget for the current workflow."""
        return ui_docks.make_review_queue_widget(self)
    def _make_advanced_settings_widget(self) -> QtWidgets.QWidget:
        """Create advanced settings widget for the current workflow."""
        return ui_docks.make_advanced_settings_widget(self)
    def _make_status_details_widget(self) -> QtWidgets.QWidget:
        """Create status details widget for the current workflow."""
        return ui_docks.make_status_details_widget(self)
    def _make_advanced_analysis_widget(self) -> QtWidgets.QWidget:
        """Create advanced analysis widget for the current workflow."""
        return ui_docks.make_advanced_analysis_widget(self)
    def _make_roi_widget(self) -> QtWidgets.QWidget:
        """Create roi widget for the current workflow."""
        return ui_docks.make_roi_widget(self)
    def _make_roi_manager_widget(self) -> QtWidgets.QWidget:
        """Create roi manager widget for the current workflow."""
        return ui_docks.make_roi_manager_widget(self)
    def _make_results_widget(self) -> QtWidgets.QWidget:
        """Create results widget for the current workflow."""
        return ui_docks.make_results_widget(self)
    def _make_recorder_widget(self) -> QtWidgets.QWidget:
        """Create recorder widget for the current workflow."""
        return ui_docks.make_recorder_widget(self)
    def _make_hist_widget(self) -> QtWidgets.QWidget:
        """Create hist widget for the current workflow."""
        return ui_docks.make_hist_widget(self)
    def _make_profile_widget(self) -> QtWidgets.QWidget:
        """Create profile widget for the current workflow."""
        return ui_docks.make_profile_widget(self)
    def _make_orthoview_widget(self) -> QtWidgets.QWidget:
        """Create orthoview widget for the current workflow."""
        return ui_docks.make_orthoview_widget(self)
    def _make_smlm_widget(self) -> QtWidgets.QWidget:
        """Create smlm widget for the current workflow."""
        return ui_docks.make_smlm_widget(self)
    def _make_threshold_widget(self) -> QtWidgets.QWidget:
        """Create threshold widget for the current workflow."""
        return ui_docks.make_threshold_widget(self)
    def _make_particles_widget(self) -> QtWidgets.QWidget:
        """Create particles widget for the current workflow."""
        return ui_docks.make_particles_widget(self)
    def _make_density_widget(self) -> QtWidgets.QWidget:
        """Create density widget for the current workflow."""
        return ui_docks.make_density_widget(self)
    def _make_channel_controls_widget(self) -> QtWidgets.QWidget:
        """Create channel controls widget for the current workflow."""
        return ui_docks.make_channel_controls_widget(self)
    def _make_logs_widget(self) -> QtWidgets.QWidget:
        """Create logs widget for the current workflow."""
        return ui_docks.make_logs_widget(self)
    def _make_metadata_widget(self) -> QtWidgets.QWidget:
        """Create metadata widget for the current workflow."""
        return ui_docks.make_metadata_widget(self)
    def _make_performance_widget(self) -> QtWidgets.QWidget:
        """Create performance widget for the current workflow."""
        panel = PerformancePanel(parent=self)
        panel.set_cache(self.proj_cache)
        panel.set_ring_buffer(self._playback_ring)
        self.performance_panel = panel
        return panel
    def _make_qc_issues_widget(self) -> QtWidgets.QWidget:
        """Create qc issues widget for the current workflow."""
        return ui_docks.make_qc_issues_widget(self)
    def _make_deepstorm_widget(self) -> QtWidgets.QWidget:
        """Create Deep-STORM super-resolution inference panel."""
        return ui_docks.make_deepstorm_widget(self)
    def _make_onnx_density_widget(self) -> QtWidgets.QWidget:
        """Create ONNX density prediction panel."""
        return ui_docks.make_onnx_density_widget(self)
