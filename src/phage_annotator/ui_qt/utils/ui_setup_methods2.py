"""Method group 2 split from ui_setup.py."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils import ui_actions, ui_docks
from phage_annotator.ui_qt.utils.ui_setup_registry import UiSetupRegistryMixin
from phage_annotator.ui_qt.utils.ui_setup_assist import build_assist_controls
from phage_annotator.ui_qt.utils.ui_setup_canvas import (
    build_annotation_table_panel,
    build_canvas_workspace,
)
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)
from phage_annotator.ui_qt.utils.ui_setup_action_connections import connect_main_window_actions
from phage_annotator.ui_qt.utils.ui_setup_advanced_sections import build_advanced_sidebar_sections
from phage_annotator.ui_qt.utils.ui_setup_display_controls import build_display_controls
from phage_annotator.ui_qt.utils.ui_setup_panel_connections import connect_panel_runtime_signals
from phage_annotator.ui_qt.utils.ui_setup_workspace_sections import build_workspace_sections
from phage_annotator.ui_qt.utils.ui_setup_workspace import build_modality_loader_section
from phage_annotator.ui_qt.keyboard_registry import apply_menu_shortcuts
from phage_annotator.ui_qt.utils.constants import DEFAULT_PLAYBACK_FPS
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, cmap_for, lut_names
from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.rendering.mpl import Renderer
from phage_annotator.ui_qt.models.lazy_loader import LAZY_LOADER_TREE_HEADER
from phage_annotator.ui_qt.widgets.modality_canvas import ModalityCanvasManager

try:
    from phage_annotator.ui_qt.utils.bcontrast_integration import integrate_b_contrast_features
    HAS_BCONTRAST = True
except ImportError:
    HAS_BCONTRAST = False

# Temporary feature gates.
DISABLE_QC = True
DISABLE_DIAGNOSTICS = True
DISABLE_SHORTCUTS = False

class _UiSetupMixinMethods2:
    """Methods split from UiSetupMixin."""

    def _setup_ui(self) -> None:
        """Create menus, toolbars, dock panels, and central widgets."""
        self._shortcuts_enabled = not DISABLE_SHORTCUTS
        self.setWindowTitle("Phage Annotator - Microscopy Keypoints")
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            min_w = min(1100, avail.width())
            min_h = min(700, avail.height())
            target_w = min(1700, int(avail.width() * 0.9))
            target_h = min(1000, int(avail.height() * 0.9))
            self.resize(max(min_w, target_w), max(min_h, target_h))
            self.setMinimumSize(min_w, min_h)
        else:
            self.resize(1700, 1000)
            self.setMinimumSize(1100, 700)
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AnimatedDocks
        )
        self.setStyleSheet(
            "QToolBar { spacing: 6px; }"
            "QDockWidget { border: 1px solid #d0d0d0; }"
            "QDockWidget::title { padding: 4px 6px; background: #f5f5f5; border-bottom: 1px solid #e0e0e0; }"
            "QGroupBox { margin-top: 8px; border: 1px solid #e8e8e8; border-radius: 4px; }"
            "QPushButton { padding: 4px 8px; }"
            "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 2px 6px; }"
        )

        actions, dock_panels_menu = ui_actions.build_menus(self)
        self._action_map = actions
        open_files_act = actions["open_files"]
        open_folder_act = actions["open_folder"]
        load_ann_current_act = actions["load_ann_current"]
        load_ann_multi_act = actions["load_ann_multi"]
        load_ann_all_act = actions["load_ann_all"]
        save_csv_act = actions["save_csv"]
        save_json_act = actions["save_json"]
        export_standard_act = actions["export_standard"]
        export_view_act = actions["export_view"]
        save_proj_act = actions["save_proj"]
        load_proj_act = actions["load_proj"]
        prefs_act = actions["prefs"]
        reset_confirms_act = actions["reset_confirms"]
        reload_ann_act = actions["reload_ann"]
        suggest_points_act = actions["suggest_points"]
        suggest_points_image_act = actions["suggest_points_image"]
        select_suggestion_strategy_act = actions["select_suggestion_strategy"]
        load_suggestion_rule_config_act = actions["load_suggestion_rule_config"]
        set_suggestion_score_threshold_act = actions["set_suggestion_score_threshold"]
        accept_visible_suggestions_act = actions["accept_visible_suggestions"]
        accept_green_suggestions_act = actions["accept_green_suggestions"]
        accept_suggestions_in_roi_act = actions["accept_suggestions_in_roi"]
        reject_visible_suggestions_act = actions["reject_visible_suggestions"]
        clear_suggestions_act = actions["clear_suggestions"]
        show_suggestion_patch_act = actions["show_suggestion_patch"]
        start_timed_session_assisted_act = actions["start_timed_session_assisted"]
        start_timed_session_manual_act = actions["start_timed_session_manual"]
        stop_timed_session_act = actions["stop_timed_session"]
        assist_warmup_act = actions["assist_warmup"]
        train_ranker_now_act = actions["train_ranker_now"]
        batch_correct_suggestions_act = actions["batch_correct_suggestions"]
        propagate_suggestions_act = actions["propagate_suggestions"]
        toggle_suggestions_overlay_act = actions["toggle_suggestions_overlay"]
        qc_validate_act = actions["qc_validate"]
        qc_jump_next_act = actions["qc_jump_next"]
        set_current_user_act = actions["set_current_user"]
        mark_selected_in_review_act = actions["mark_selected_in_review"]
        mark_selected_approved_act = actions["mark_selected_approved"]
        mark_selected_needs_changes_act = actions["mark_selected_needs_changes"]
        assign_selected_act = actions["assign_selected"]
        show_reviewer_analytics_act = actions["show_reviewer_analytics"]
        queue_all_act = actions["queue_all"]
        queue_my_act = actions["queue_my"]
        queue_needs_review_act = actions["queue_needs_review"]
        queue_blocked_qc_act = actions["queue_blocked_qc"]
        clear_hist_cache_act = actions.get("clear_hist_cache")
        exit_act = actions["exit"]
        about_act = actions["about"]
        context_help_act = actions["context_help"]
        copy_display_act = actions["copy_display"]
        measure_act = actions["measure"]
        jump_to_frame_act = actions["jump_to_frame"]
        jump_to_z_act = actions["jump_to_z"]
        show_roi_handles_act = self.show_roi_handles_act
        clear_roi_act = self.clear_roi_act
        self._qc_enabled = not DISABLE_QC

        if DISABLE_QC:
            qc_validate_act.setEnabled(False)
            qc_validate_act.setVisible(False)
            qc_jump_next_act.setEnabled(False)
            qc_jump_next_act.setVisible(False)
            queue_blocked_qc_act.setEnabled(False)
        if DISABLE_DIAGNOSTICS and getattr(self, "toggle_logs_act", None) is not None:
            self.toggle_logs_act.setEnabled(False)
            self.toggle_logs_act.setVisible(False)

        # Status widgets must exist before panel factories are constructed.
        self._setup_status_bar()
        
        self._init_tool_bar()
        show_roi_handles_act.setChecked(bool(self.show_roi_handles))

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(
            "QWidget { background: #ffffff; }"
        )
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.setSpacing(10)

        fig_container, playback_bar = build_workspace_sections(self)
        display_group = build_display_controls(self)
        build_advanced_sidebar_sections(self, display_group)

        # Panels/docks + sidebar (status bar already initialized earlier)
        self._init_panels(dock_panels_menu)
        self.open_panel_switcher_act = QtWidgets.QAction("Panels: Open Panel…", self)
        self.open_panel_switcher_act.setObjectName("open_panel_switcher")
        self.open_panel_switcher_act.triggered.connect(self._show_panel_switcher)
        if not DISABLE_SHORTCUTS:
            self.open_panel_switcher_act.setShortcut("Ctrl+Alt+P")
        first_action = dock_panels_menu.actions()[0] if dock_panels_menu.actions() else None
        if first_action is not None:
            dock_panels_menu.insertAction(first_action, self.open_panel_switcher_act)
        else:
            dock_panels_menu.addAction(self.open_panel_switcher_act)
        self.addAction(self.open_panel_switcher_act)
        # Re-apply registry shortcuts now that panel-switcher action exists.
        if not DISABLE_SHORTCUTS:
            apply_menu_shortcuts(self)
        self._init_panel_policy_controls()
        self._init_channel_panel_integration()
        self._setup_annotation_toolbar()

        central_layout.addWidget(fig_container, stretch=1)
        central_layout.addWidget(playback_bar, stretch=0)

        connect_main_window_actions(
            self,
            actions,
            disable_shortcuts=DISABLE_SHORTCUTS,
            disable_qc=DISABLE_QC,
        )
        connect_panel_runtime_signals(
            self,
            disable_qc=DISABLE_QC,
            disable_diagnostics=DISABLE_DIAGNOSTICS,
        )
