"""Utils dock panel manager impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import logging
from typing import List

from matplotlib.backends.qt_compat import QtCore

from phage_annotator.ui_qt.panels.registry import PanelConstraints, PanelSpec

logger = logging.getLogger(__name__)

PANEL_TAB_GROUPS = {
    # Right inspect panels are intentionally NOT tabified; they are shown as
    # distinct panels via right-sidebar selection.
    "tools_roi": ("roi", "roi_manager", "results", "orthoview", "metadata"),
    "plots_hist": ("hist", "profile"),
    "system": ("logs", "performance", "recorder"),
}
# so placement recipes are defined in one declarative source of truth.

def build_panel_registry(self) -> List[PanelSpec]:
    """Return the declarative list of dock panel specs."""
    return [
        PanelSpec(
            id="sidebar",
            title="Sidebar",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_sidebar_widget,
            toggle_action_text="Toggle Sidebar",
            bucket="tools",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.LeftDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="annotations",
            title="Annotation Table",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_annotations_widget,
            toggle_action_text="Annotation Table",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="review_queue",
            title="Assist",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_review_queue_widget,
            toggle_action_text="Assist",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="advanced_settings",
            title="Advanced Settings",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_advanced_settings_widget,
            toggle_action_text="Advanced Settings",
            bucket="inspect",
            search_aliases=("advanced settings", "calibration", "pixel size", "axis mode"),
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="status_details",
            title="Status Details",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_status_details_widget,
            toggle_action_text="Status Details",
            bucket="inspect",
            search_aliases=("status details", "run context", "session status"),
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="advanced_analysis",
            title="Analysis",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_advanced_analysis_widget,
            toggle_action_text="Analysis",
            bucket="inspect",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="roi",
            title="ROI Controls",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,  # Hidden by default, opened from ROI/Crop panel
            widget_factory=self._make_roi_widget,
            toggle_action_text="ROI Controls",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="roi_manager",
            title="ROI Manager",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_roi_manager_widget,
            toggle_action_text="ROI Manager",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="results",
            title="Results",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_results_widget,
            toggle_action_text="Results",
            bucket="plots",
            search_aliases=("results table", "results hub"),
        ),
        PanelSpec(
            id="recorder",
            title="Recorder",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_recorder_widget,
            toggle_action_text="Recorder",
            bucket="plots",
            tab_group="system",
        ),
        PanelSpec(
            id="hist",
            title="Histogram",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,  # Hidden by default per Task G
            widget_factory=self._make_hist_widget,
            toggle_action_text="Histogram",
            bucket="plots",
            tab_group="plots_hist",
        ),
        PanelSpec(
            id="profile",
            title="Line Profile",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,  # Hidden by default per Task G
            widget_factory=self._make_profile_widget,
            toggle_action_text="Line Profile",
            bucket="plots",
            tab_group="plots_hist",
        ),
        PanelSpec(
            id="orthoview",
            title="Ortho Views",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_orthoview_widget,
            toggle_action_text="Ortho Views",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="smlm",
            title="SMLM (ROI)",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_smlm_widget,
            toggle_action_text="SMLM (ROI)",
            bucket="tools",
        ),
        PanelSpec(
            id="threshold",
            title="Threshold",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_threshold_widget,
            toggle_action_text="Threshold",
            bucket="tools",
        ),
        PanelSpec(
            id="particles",
            title="Analyze Particles",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_particles_widget,
            toggle_action_text="Analyze Particles",
            bucket="tools",
        ),
        PanelSpec(
            id="density",
            title="Density",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_density_widget,
            toggle_action_text="Density",
            bucket="tools",
        ),
        PanelSpec(
            id="channels",
            title="Channels",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_channel_controls_widget,
            toggle_action_text="Channels",
            bucket="tools",
        ),
        PanelSpec(
            id="logs",
            title="Logs / Diagnostics",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_logs_widget,
            toggle_action_text="Logs / Diagnostics",
            bucket="plots",
            tab_group="system",
            search_aliases=("logs", "system logs"),
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="metadata",
            title="Metadata",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_metadata_widget,
            toggle_action_text="Metadata",
            bucket="tools",
            tab_group="tools_roi",
        ),
        PanelSpec(
            id="performance",
            title="Performance",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_performance_widget,
            toggle_action_text="Performance Monitor",
            bucket="plots",
            tab_group="system",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
        PanelSpec(
            id="qc_issues",
            title="QC Issues",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_qc_issues_widget,
            toggle_action_text="QC Issues",
            bucket="plots",
            constraints=PanelConstraints(
                allowed_areas=(QtCore.Qt.RightDockWidgetArea,),
                floatable=False,
                fixed_area=True,
            ),
        ),
    ]
