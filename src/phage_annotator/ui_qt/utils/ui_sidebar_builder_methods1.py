"""Method group 1 split from ui_sidebar_builder.py."""

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

class _UiSidebarBuilderMixinMethods1:
    """Methods split from UiSidebarBuilderMixin."""

    def _make_sidebar_widget(self) -> QtWidgets.QWidget:
        """Document the make_sidebar_widget flow."""
        return ui_docks.make_sidebar_widget(self)

    def _make_annotations_widget(self) -> QtWidgets.QWidget:
        """Document the make_annotations_widget flow."""
        return ui_docks.make_annotations_widget(self)

    def _make_review_queue_widget(self) -> QtWidgets.QWidget:
        """Document the make_review_queue_widget flow."""
        return ui_docks.make_review_queue_widget(self)

    def _make_advanced_settings_widget(self) -> QtWidgets.QWidget:
        """Document the make_advanced_settings_widget flow."""
        return ui_docks.make_advanced_settings_widget(self)

    def _make_status_details_widget(self) -> QtWidgets.QWidget:
        """Document the make_status_details_widget flow."""
        return ui_docks.make_status_details_widget(self)

    def _make_advanced_analysis_widget(self) -> QtWidgets.QWidget:
        """Document the make_advanced_analysis_widget flow."""
        return ui_docks.make_advanced_analysis_widget(self)

    def _make_roi_widget(self) -> QtWidgets.QWidget:
        """Document the make_roi_widget flow."""
        return ui_docks.make_roi_widget(self)

    def _make_roi_manager_widget(self) -> QtWidgets.QWidget:
        """Document the make_roi_manager_widget flow."""
        return ui_docks.make_roi_manager_widget(self)

    def _make_results_widget(self) -> QtWidgets.QWidget:
        """Document the make_results_widget flow."""
        return ui_docks.make_results_widget(self)

    def _make_recorder_widget(self) -> QtWidgets.QWidget:
        """Document the make_recorder_widget flow."""
        return ui_docks.make_recorder_widget(self)

    def _make_hist_widget(self) -> QtWidgets.QWidget:
        """Document the make_hist_widget flow."""
        return ui_docks.make_hist_widget(self)

    def _make_profile_widget(self) -> QtWidgets.QWidget:
        """Document the make_profile_widget flow."""
        return ui_docks.make_profile_widget(self)

    def _make_orthoview_widget(self) -> QtWidgets.QWidget:
        """Document the make_orthoview_widget flow."""
        return ui_docks.make_orthoview_widget(self)

    def _make_smlm_widget(self) -> QtWidgets.QWidget:
        """Document the make_smlm_widget flow."""
        return ui_docks.make_smlm_widget(self)

    def _make_threshold_widget(self) -> QtWidgets.QWidget:
        """Document the make_threshold_widget flow."""
        return ui_docks.make_threshold_widget(self)

    def _make_particles_widget(self) -> QtWidgets.QWidget:
        """Document the make_particles_widget flow."""
        return ui_docks.make_particles_widget(self)

    def _make_density_widget(self) -> QtWidgets.QWidget:
        """Document the make_density_widget flow."""
        return ui_docks.make_density_widget(self)

    def _make_channel_controls_widget(self) -> QtWidgets.QWidget:
        """Document the make_channel_controls_widget flow."""
        return ui_docks.make_channel_controls_widget(self)

    def _make_logs_widget(self) -> QtWidgets.QWidget:
        """Document the make_logs_widget flow."""
        return ui_docks.make_logs_widget(self)

    def _make_metadata_widget(self) -> QtWidgets.QWidget:
        """Document the make_metadata_widget flow."""
        return ui_docks.make_metadata_widget(self)

    def _make_performance_widget(self) -> QtWidgets.QWidget:
        """Document the make_performance_widget flow."""
        panel = PerformancePanel(parent=self)
        panel.set_cache(self.proj_cache)
        panel.set_ring_buffer(self._playback_ring)
        self.performance_panel = panel
        return panel

    def _make_qc_issues_widget(self) -> QtWidgets.QWidget:
        """Document the make_qc_issues_widget flow."""
        return ui_docks.make_qc_issues_widget(self)
