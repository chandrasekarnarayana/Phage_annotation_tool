"""Dock/panel wiring helpers for the main window."""

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


from phage_annotator.ui_qt.utils.ui_docks_core import _panel_auto_open_key, _panel_pinned_key, _panel_auto_open_trigger_key, _is_auto_reason, _auto_trigger_from_reason, _is_user_intent_reason, _show_status_message, _hide_auto_open_toast, _show_auto_open_toast, _merge_system_docks, _select_system_tab_for_panel, _iter_unique_dock_specs, _find_tab_for_dock, _init_panel_auto_policy_state, refresh_panel_policy_actions, is_panel_auto_open_enabled, is_panel_auto_open_enabled_for_trigger, set_panel_auto_open_enabled, set_panel_auto_open_enabled_for_trigger, is_panel_pinned, set_panel_pinned, init_panels, get_panel_spec, get_dock, _apply_panel_constraints, _canonical_area_for_panel, _tabify_group_for_panel, _flash_dock, PanelManager, _panel_manager, open_panel, build_panel_registry, apply_panel_defaults, create_dock, wire_dock_action
from phage_annotator.ui_qt.utils.dock_sidebar_widgets import get_panel_opened_by, make_sidebar_widget, make_annotations_widget, make_review_queue_widget, make_advanced_settings_widget, make_status_details_widget, make_advanced_analysis_widget
from phage_annotator.ui_qt.utils.dock_roi_widgets import make_roi_widget
from phage_annotator.ui_qt.utils.dock_roi_widgets import make_roi_manager_widget, make_results_widget, make_recorder_widget, make_hist_widget, make_profile_widget, make_orthoview_widget, make_smlm_widget, make_threshold_widget, make_particles_widget, make_channel_controls_widget
from phage_annotator.ui_qt.utils.dock_analysis_widgets import make_logs_widget, make_metadata_widget, make_density_widget, make_qc_issues_widget
from phage_annotator.ui_qt.utils.dock_status_bar import setup_status_bar
