"""UI construction helpers for the main window."""

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
from phage_annotator.ui_qt.utils.ui_setup_workspace import build_modality_loader_section
from phage_annotator.ui_qt.keyboard_registry import apply_menu_shortcuts
from phage_annotator.ui_qt.utils.constants import DEFAULT_PLAYBACK_FPS
from phage_annotator.ui_qt.panels.registry_legacy import PanelSpec
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


class UiSetupMixin(UiSetupRegistryMixin):
    """Mixin containing UI construction and dock wiring."""

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

        # Explore pane: FOV list + primary/support (sidebar page)
        self.explore_panel = QtWidgets.QWidget()
        self.explore_panel.setStyleSheet(
            "QWidget { border: 1px solid #d8d8d8; border-radius: 3px; background: #fafafa; }"
        )
        explore_layout = QtWidgets.QVBoxLayout(self.explore_panel)
        explore_layout.setContentsMargins(8, 8, 8, 8)
        explore_layout.setSpacing(8)
        self.fov_list = QtWidgets.QListWidget()
        for img in self.images:
            self.fov_list.addItem(img.name)
        self.fov_list.setCurrentRow(self.current_image_idx)
        explore_layout.addWidget(QtWidgets.QLabel("FOVs"))
        explore_layout.addWidget(self.fov_list)
        self.clear_fovs_btn = QtWidgets.QPushButton("Clear FOV list")
        explore_layout.addWidget(self.clear_fovs_btn)

        primary_box = QtWidgets.QHBoxLayout()
        primary_box.addWidget(QtWidgets.QLabel("Modality 1"))
        self.primary_combo = QtWidgets.QComboBox()
        self.support_combo = QtWidgets.QComboBox()
        for img in self.images:
            self.primary_combo.addItem(img.name)
            self.support_combo.addItem(img.name)
        self.primary_combo.setCurrentIndex(self.current_image_idx)
        self.support_combo.setCurrentIndex(self.support_image_idx)
        
        # Add context menu for renaming modalities (Phase γ)
        self.primary_combo.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.primary_combo.customContextMenuRequested.connect(self._on_modality_context_menu)
        self.support_combo.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.support_combo.customContextMenuRequested.connect(self._on_modality_context_menu)
        
        primary_box.addWidget(self.primary_combo)
        primary_box.addWidget(QtWidgets.QLabel("Modality 2"))
        primary_box.addWidget(self.support_combo)
        # Primary/support selectors remain available for internal wiring and the
        # Prepare workflow page, but stay out of the default canvas strip.
        self.primary_combo.setVisible(False)
        self.support_combo.setVisible(False)
        build_modality_loader_section(self, explore_layout)

        build_annotation_table_panel(self)
        fig_container, playback_bar = build_canvas_workspace(self)

        self.playback_mode_combo = QtWidgets.QComboBox()
        self.playback_mode_combo.addItems(["Synchronized", "Independent", "Sequential"])
        self.playback_target_combo = QtWidgets.QComboBox()
        self.playback_target_combo.addItem("Active")
        self.playback_target_btn = QtWidgets.QPushButton("Play Target")
        # Keep advanced playback routing controls available for programmatic use,
        # but do not crowd the default bottom control strip.
        self.playback_mode_combo.setVisible(False)
        self.playback_target_combo.setVisible(False)
        self.playback_target_btn.setVisible(False)
        self.quick_panels_btn = QtWidgets.QToolButton()
        self.quick_panels_btn.setText("Panels")
        self.quick_panels_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.quick_panels_menu = QtWidgets.QMenu(self.quick_panels_btn)
        self.quick_hist_act = self.quick_panels_menu.addAction("Histogram")
        self.quick_hist_act.setCheckable(True)
        self.quick_profile_act = self.quick_panels_menu.addAction("Profile")
        self.quick_profile_act.setCheckable(True)
        self.quick_qc_act = self.quick_panels_menu.addAction("QC Issues")
        self.quick_qc_act.setCheckable(True)
        self.quick_panels_btn.setMenu(self.quick_panels_menu)
        self.quick_layout_btn = QtWidgets.QToolButton()
        self.quick_layout_btn.setText("Layouts")
        self.quick_layout_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.quick_layout_menu = QtWidgets.QMenu(self.quick_layout_btn)
        self.quick_layout_menu.addAction("Default", lambda: self.apply_preset("Default"))
        self.quick_layout_menu.addAction("Annotate", lambda: self.apply_preset("Annotate"))
        self.quick_layout_menu.addAction("Analyze", lambda: self.apply_preset("Analyze"))
        self.quick_layout_menu.addAction("Assist Expert", lambda: self.apply_preset("Assist Expert"))
        self.quick_layout_menu.addAction("Minimal", lambda: self.apply_preset("Minimal"))
        self.quick_layout_btn.setMenu(self.quick_layout_menu)
        self.quick_panels_btn.setToolTip("Quick panel toggles")
        self.quick_layout_btn.setToolTip("Quick layout presets")
        # Keep panel/layout quick menus available from menu bar and command palette.
        self.quick_panels_btn.setVisible(False)
        self.quick_layout_btn.setVisible(False)

        display_group = QtWidgets.QGroupBox("Contrast & Projection")
        display_group.setObjectName("contrast_projection_group")
        display_group.setStyleSheet(
            "#contrast_projection_group QGroupBox {"
            " margin-top: 10px; border: 1px solid #e4e7eb; border-radius: 5px; padding-top: 4px; }"
            "#contrast_projection_group QGroupBox::title {"
            " subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #263238; font-weight: 600; }"
            "#contrast_projection_group QComboBox, #contrast_projection_group QLineEdit, "
            "#contrast_projection_group QDoubleSpinBox, #contrast_projection_group QSpinBox { min-height: 24px; }"
            "#contrast_projection_group QPushButton { min-height: 24px; }"
        )
        display_layout = QtWidgets.QGridLayout(display_group)
        display_layout.setContentsMargins(10, 10, 10, 10)
        display_layout.setHorizontalSpacing(10)
        display_layout.setVerticalSpacing(8)
        display_layout.setColumnStretch(2, 1)
        drow = 0

        self.vmin_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vmax_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vmin_slider.setRange(0, 100)
        self.vmax_slider.setRange(0, 100)
        self.vmin_slider.setValue(5)
        self.vmax_slider.setValue(95)
        self.vmin_slider.setSingleStep(1)
        self.vmax_slider.setSingleStep(1)
        self.vmin_minus_button = QtWidgets.QPushButton("-")
        self.vmin_plus_button = QtWidgets.QPushButton("+")
        self.vmax_minus_button = QtWidgets.QPushButton("-")
        self.vmax_plus_button = QtWidgets.QPushButton("+")
        self.vmin_minus_button.setToolTip("Step down lower contrast bound")
        self.vmin_plus_button.setToolTip("Step up lower contrast bound")
        self.vmax_minus_button.setToolTip("Step down upper contrast bound")
        self.vmax_plus_button.setToolTip("Step up upper contrast bound")
        for btn in [
            self.t_minus_button,
            self.t_plus_button,
            self.z_minus_button,
            self.z_plus_button,
            self.speed_minus_button,
            self.speed_plus_button,
            self.vmin_minus_button,
            self.vmin_plus_button,
            self.vmax_minus_button,
            self.vmax_plus_button,
        ]:
            btn.setFixedWidth(28)
        vmin_slider_box = QtWidgets.QHBoxLayout()
        vmin_slider_box.addWidget(self.vmin_minus_button)
        vmin_slider_box.addWidget(self.vmin_slider, stretch=1)
        vmin_slider_box.addWidget(self.vmin_plus_button)
        vmax_slider_box = QtWidgets.QHBoxLayout()
        vmax_slider_box.addWidget(self.vmax_minus_button)
        vmax_slider_box.addWidget(self.vmax_slider, stretch=1)
        vmax_slider_box.addWidget(self.vmax_plus_button)
        self.vmin_label = QtWidgets.QLabel("vmin: -")
        self.vmax_label = QtWidgets.QLabel("vmax: -")

        self.lut_combo = QtWidgets.QComboBox()
        self.lut_combo.addItems(lut_names())
        self.lut_invert_chk = QtWidgets.QCheckBox("Invert LUT")
        lut_box = QtWidgets.QHBoxLayout()
        lut_box.addWidget(self.lut_combo)
        lut_box.addWidget(self.lut_invert_chk)

        self.gamma_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(2, 50)
        self.gamma_slider.setValue(10)
        self.gamma_label = QtWidgets.QLabel("1.00")
        gamma_row = QtWidgets.QHBoxLayout()
        gamma_row.addWidget(self.gamma_slider, stretch=1)
        gamma_row.addWidget(self.gamma_label)
        self.log_chk = QtWidgets.QCheckBox("Log display")

        contrast_group = QtWidgets.QGroupBox("Contrast")
        contrast_layout = QtWidgets.QGridLayout(contrast_group)
        contrast_layout.setContentsMargins(10, 8, 10, 8)
        contrast_layout.setHorizontalSpacing(10)
        contrast_layout.setVerticalSpacing(8)
        contrast_layout.addWidget(QtWidgets.QLabel("Vmin"), 0, 0)
        contrast_layout.addWidget(self.vmin_label, 0, 1)
        contrast_layout.addLayout(vmin_slider_box, 0, 2)
        contrast_layout.addWidget(QtWidgets.QLabel("Vmax"), 1, 0)
        contrast_layout.addWidget(self.vmax_label, 1, 1)
        contrast_layout.addLayout(vmax_slider_box, 1, 2)
        contrast_layout.addWidget(QtWidgets.QLabel("LUT"), 2, 0)
        contrast_layout.addLayout(lut_box, 2, 2)
        contrast_layout.addWidget(QtWidgets.QLabel("Gamma"), 3, 0)
        contrast_layout.addLayout(gamma_row, 3, 2)
        contrast_layout.addWidget(self.log_chk, 4, 0, 1, 3)
        display_layout.addWidget(contrast_group, drow, 0, 1, 3)
        drow += 1

        self.auto_btn = QtWidgets.QPushButton("Auto")
        self.auto_set_btn = QtWidgets.QPushButton("Set…")
        self.auto_pct_label = QtWidgets.QLabel("0.35% / 99.65%")
        self.auto_scope_combo = QtWidgets.QComboBox()
        self.auto_scope_combo.addItems(["Current slice", "All frames", "Whole image"])
        self.auto_target_combo = QtWidgets.QComboBox()
        self.auto_target_combo.addItems(["Current panel", "All visible panels"])
        self.auto_roi_chk = QtWidgets.QCheckBox("Use ROI only")
        auto_group = QtWidgets.QGroupBox("Auto Contrast")
        auto_layout = QtWidgets.QGridLayout(auto_group)
        auto_layout.setContentsMargins(10, 8, 10, 8)
        auto_layout.setHorizontalSpacing(10)
        auto_layout.setVerticalSpacing(8)
        auto_controls = QtWidgets.QHBoxLayout()
        auto_controls.addWidget(self.auto_btn)
        auto_controls.addWidget(self.auto_set_btn)
        auto_controls.addWidget(self.auto_pct_label)
        auto_layout.addWidget(QtWidgets.QLabel("Action"), 0, 0)
        auto_layout.addLayout(auto_controls, 0, 1, 1, 2)
        auto_layout.addWidget(QtWidgets.QLabel("Scope"), 1, 0)
        auto_layout.addWidget(self.auto_scope_combo, 1, 1, 1, 2)
        auto_layout.addWidget(QtWidgets.QLabel("Target"), 2, 0)
        auto_layout.addWidget(self.auto_target_combo, 2, 1, 1, 2)
        auto_layout.addWidget(QtWidgets.QLabel("ROI"), 3, 0)
        auto_layout.addWidget(self.auto_roi_chk, 3, 1, 1, 2)
        self.auto_scope_combo.setToolTip("Data extent used to compute automatic contrast.")
        self.auto_target_combo.setToolTip("Where computed contrast mapping is applied.")
        self.auto_roi_chk.setToolTip("Restrict auto-contrast statistics to current ROI.")
        display_layout.addWidget(auto_group, drow, 0, 1, 3)
        drow += 1

        # Replace projection_axis_combo with full ProjectionSelectorWidget
        from phage_annotator.ui_qt.widgets.projection_selector import ProjectionSelectorWidget
        self.projection_selector = ProjectionSelectorWidget(self)
        projection_group = QtWidgets.QGroupBox("Projection")
        projection_layout = QtWidgets.QGridLayout(projection_group)
        projection_layout.setContentsMargins(10, 8, 10, 8)
        projection_layout.setHorizontalSpacing(10)
        projection_layout.setVerticalSpacing(8)
        projection_layout.addWidget(QtWidgets.QLabel("Mode"), 0, 0)
        projection_layout.addWidget(self.projection_selector, 0, 1)
        # Keep projection_axis_combo as alias for backward compatibility
        self.projection_axis_combo = self.projection_selector.axis_combo
        display_layout.addWidget(projection_group, drow, 0, 1, 3)
        drow += 1

        sync_group = QtWidgets.QGroupBox("Sync Target")
        sync_layout = QtWidgets.QGridLayout(sync_group)
        sync_layout.setContentsMargins(10, 8, 10, 8)
        sync_layout.setHorizontalSpacing(10)
        sync_layout.setVerticalSpacing(8)
        self.sync_intro_lbl = QtWidgets.QLabel(
            "Use one shared Sync Group target for contrast, zoom/pan, and playback."
        )
        self.sync_intro_lbl.setWordWrap(True)
        self.sync_intro_lbl.setStyleSheet("color: #455a64;")
        self.sync_scope_hint_lbl = QtWidgets.QLabel(
            "Sync source: active view group."
        )
        self.sync_scope_hint_lbl.setStyleSheet("color: #546e7a;")
        self.sync_keys_hint_lbl = QtWidgets.QLabel("Groups available: -")
        self.sync_keys_hint_lbl.setStyleSheet("color: #455a64; font-style: italic;")
        self.sync_source_hint_lbl = QtWidgets.QLabel(
            "Per-row checkboxes in Lazy Loading decide what syncs (contrast/zoom/playback)."
        )
        self.sync_source_hint_lbl.setStyleSheet("color: #546e7a;")
        sync_layout.addWidget(self.sync_intro_lbl, 0, 0, 1, 4)
        sync_layout.addWidget(
            QtWidgets.QLabel("Sync target controls are always visible in the bottom playback bar."),
            1,
            0,
            1,
            4,
        )
        sync_layout.addWidget(self.sync_scope_hint_lbl, 2, 0, 1, 4)
        sync_layout.addWidget(self.sync_keys_hint_lbl, 3, 0, 1, 4)
        sync_layout.addWidget(self.sync_source_hint_lbl, 4, 0, 1, 4)
        display_layout.addWidget(sync_group, drow, 0, 1, 3)
        drow += 1

        self.scalebar_chk = QtWidgets.QCheckBox("Show scale bar")
        self.scalebar_chk.setChecked(self.scale_bar_enabled)
        self.scalebar_length_spin = QtWidgets.QDoubleSpinBox()
        self.scalebar_length_spin.setRange(0.1, 1000.0)
        self.scalebar_length_spin.setDecimals(2)
        self.scalebar_length_spin.setValue(self.scale_bar_length_um)
        self.scalebar_thickness_spin = QtWidgets.QSpinBox()
        self.scalebar_thickness_spin.setRange(1, 20)
        self.scalebar_thickness_spin.setValue(self.scale_bar_thickness_px)
        self.scalebar_location_combo = QtWidgets.QComboBox()
        self.scalebar_location_combo.addItems(
            ["bottom_right", "bottom_left", "top_right", "top_left"]
        )
        self.scalebar_location_combo.setCurrentText(self.scale_bar_location)
        self.scalebar_text_chk = QtWidgets.QCheckBox("Show text")
        self.scalebar_text_chk.setChecked(self.scale_bar_show_text)
        self.scalebar_background_chk = QtWidgets.QCheckBox("Background box")
        self.scalebar_background_chk.setChecked(self.scale_bar_background_box)
        self.scalebar_export_chk = QtWidgets.QCheckBox("Include in export")
        self.scalebar_export_chk.setChecked(self.scale_bar_include_in_export)
        scalebar_group = QtWidgets.QGroupBox("Scale Bar")
        scalebar_layout = QtWidgets.QGridLayout(scalebar_group)
        scalebar_layout.setContentsMargins(8, 8, 8, 8)
        scalebar_layout.setHorizontalSpacing(8)
        scalebar_layout.setVerticalSpacing(6)
        scalebar_layout.addWidget(self.scalebar_chk, 0, 0, 1, 2)
        scalebar_layout.addWidget(QtWidgets.QLabel("Length (um)"), 1, 0)
        scalebar_layout.addWidget(self.scalebar_length_spin, 1, 1)
        scalebar_layout.addWidget(QtWidgets.QLabel("Thickness"), 2, 0)
        scalebar_layout.addWidget(self.scalebar_thickness_spin, 2, 1)
        scalebar_layout.addWidget(QtWidgets.QLabel("Location"), 3, 0)
        scalebar_layout.addWidget(self.scalebar_location_combo, 3, 1)
        scalebar_layout.addWidget(self.scalebar_text_chk, 4, 0)
        scalebar_layout.addWidget(self.scalebar_background_chk, 4, 1)
        scalebar_layout.addWidget(self.scalebar_export_chk, 5, 0, 1, 2)
        display_layout.addWidget(scalebar_group, drow, 0, 1, 3)
        drow += 1

        self.annotate_panel = self._build_annotate_panel()
        self._build_roi_controls_layout()

        # Advanced collapsible container
        self.settings_advanced_container = QtWidgets.QWidget()
        adv_container_layout = QtWidgets.QVBoxLayout(self.settings_advanced_container)
        adv_container_layout.setContentsMargins(0, 0, 0, 0)
        adv_container_layout.setSpacing(8)
        self.advanced_group = QtWidgets.QGroupBox("Advanced")
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        adv_layout = QtWidgets.QGridLayout()
        self.advanced_layout = adv_layout
        r = 0

        self.axis_mode_combo = QtWidgets.QComboBox()
        self.axis_mode_combo.addItems(["auto", "time", "depth"])
        adv_layout.addWidget(QtWidgets.QLabel("Interpret 3D axis as"), r, 0)
        adv_layout.addWidget(self.axis_mode_combo, r, 1)
        r += 1

        # Marker/click-radius controls.
        self.marker_size_spin = QtWidgets.QSpinBox()
        self.marker_size_spin.setRange(1, 100)
        self.marker_size_spin.setValue(self.marker_size)
        self.click_radius_spin = QtWidgets.QDoubleSpinBox()
        self.click_radius_spin.setRange(1, 50)
        self.click_radius_spin.setValue(self.click_radius_px)
        adv_layout.addWidget(QtWidgets.QLabel("Marker size"), r, 0)
        adv_layout.addWidget(self.marker_size_spin, r, 1)
        adv_layout.addWidget(QtWidgets.QLabel("Click radius (px)"), r, 2)
        adv_layout.addWidget(self.click_radius_spin, r, 3)
        r += 1

        # Profile controls.
        profile_controls = QtWidgets.QHBoxLayout()
        self.profile_clear_btn = QtWidgets.QPushButton("Clear profile")
        profile_controls.addWidget(self.profile_clear_btn)
        adv_layout.addWidget(QtWidgets.QLabel("Line profile actions"), r, 0)
        adv_layout.addLayout(profile_controls, r, 1, 1, 3)
        r += 1

        # Histogram controls.
        hist_controls = QtWidgets.QHBoxLayout()
        self.hist_region_combo = QtWidgets.QComboBox()
        self.hist_region_combo.addItems(["ROI", "Full"])
        self.hist_scope_combo = QtWidgets.QComboBox()
        self.hist_scope_combo.addItems(["Current slice", "All frames", "Whole image"])
        self.hist_bins_spin = QtWidgets.QSpinBox()
        self.hist_bins_spin.setRange(10, 512)
        self.hist_bins_spin.setValue(64)
        hist_controls.addWidget(QtWidgets.QLabel("Region:"))
        hist_controls.addWidget(self.hist_region_combo)
        hist_controls.addWidget(QtWidgets.QLabel("Scope:"))
        hist_controls.addWidget(self.hist_scope_combo)
        hist_controls.addWidget(QtWidgets.QLabel("Bins:"))
        hist_controls.addWidget(self.hist_bins_spin)
        adv_layout.addWidget(QtWidgets.QLabel("Histogram"), r, 0)
        adv_layout.addLayout(hist_controls, r, 1, 1, 3)
        r += 1

        # Correction toggles.
        corr_controls = QtWidgets.QHBoxLayout()
        self.illum_corr_chk = QtWidgets.QCheckBox("Illumination correction")
        self.bleach_corr_chk = QtWidgets.QCheckBox("Photobleaching correction")
        corr_controls.addWidget(self.illum_corr_chk)
        corr_controls.addWidget(self.bleach_corr_chk)
        adv_layout.addWidget(QtWidgets.QLabel("Corrections"), r, 0)
        adv_layout.addLayout(corr_controls, r, 1, 1, 3)
        r += 1

        # ROI shape controls.
        self.roi_shape_group = QtWidgets.QButtonGroup()
        roi_rect = QtWidgets.QRadioButton("Rectangle")
        roi_circle = QtWidgets.QRadioButton("Circle")
        roi_rect.setChecked(True)
        self.roi_shape_group.addButton(roi_rect)
        self.roi_shape_group.addButton(roi_circle)
        roi_shape_layout = QtWidgets.QHBoxLayout()
        roi_shape_layout.addWidget(roi_rect)
        roi_shape_layout.addWidget(roi_circle)
        adv_layout.addWidget(QtWidgets.QLabel("ROI shape"), r, 0)
        adv_layout.addLayout(roi_shape_layout, r, 1, 1, 3)
        r += 1

        self.cache_budget_spin = QtWidgets.QSpinBox()
        self.cache_budget_spin.setRange(64, 8192)
        self.cache_budget_spin.setValue(int(self._settings.value("cacheMaxMB", 1024, type=int)))
        adv_layout.addWidget(QtWidgets.QLabel("Projection cache (MB)"), r, 0)
        adv_layout.addWidget(self.cache_budget_spin, r, 1)
        r += 1

        self.downsample_factor_spin = QtWidgets.QSpinBox()
        self.downsample_factor_spin.setRange(1, 8)
        self.downsample_factor_spin.setValue(self.downsample_factor)
        adv_layout.addWidget(QtWidgets.QLabel("Interactive downsample"), r, 0)
        adv_layout.addWidget(self.downsample_factor_spin, r, 1)
        r += 1

        self.downsample_images_chk = QtWidgets.QCheckBox("Downsample images")
        self.downsample_hist_chk = QtWidgets.QCheckBox("Downsample histogram")
        self.downsample_profile_chk = QtWidgets.QCheckBox("Downsample profile")
        self.downsample_images_chk.setChecked(self.downsample_images)
        self.downsample_hist_chk.setChecked(self.downsample_hist)
        self.downsample_profile_chk.setChecked(self.downsample_profile)
        adv_layout.addWidget(self.downsample_images_chk, r, 0, 1, 2)
        r += 1
        adv_layout.addWidget(self.downsample_hist_chk, r, 0, 1, 2)
        r += 1
        adv_layout.addWidget(self.downsample_profile_chk, r, 0, 1, 2)
        r += 1

        self.pyramid_chk = QtWidgets.QCheckBox("Enable multi-resolution pyramid")
        self.pyramid_chk.setChecked(self.pyramid_enabled)
        adv_layout.addWidget(self.pyramid_chk, r, 0, 1, 2)
        r += 1

        self.pyramid_levels_spin = QtWidgets.QSpinBox()
        self.pyramid_levels_spin.setRange(1, 4)
        self.pyramid_levels_spin.setValue(self.pyramid_max_levels)
        adv_layout.addWidget(QtWidgets.QLabel("Pyramid levels"), r, 0)
        adv_layout.addWidget(self.pyramid_levels_spin, r, 1)
        r += 1

        self.apply_display_btn = QtWidgets.QPushButton("Apply display mapping to pixels…")
        self.apply_display_btn.setToolTip(
            "Destructively rescales pixel values using the current mapping."
        )
        adv_layout.addWidget(self.apply_display_btn, r, 0, 1, 2)
        r += 1

        r = build_assist_controls(self, adv_layout, r)
        self._advanced_layout_row = r

        self.settings_advanced_container.setLayout(adv_container_layout)
        self.advanced_group.setLayout(adv_layout)
        adv_container_layout.addWidget(self.advanced_group)
        self.axis_warning = QtWidgets.QLabel()
        self.axis_warning.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.axis_warning.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.axis_warning.setOpenExternalLinks(False)
        self.axis_warning.linkActivated.connect(self._focus_axis_mode_control)
        self.axis_warning.setVisible(False)
        self.axes_info_label = QtWidgets.QLabel("T: ?  Z: ?  Y: ?  X: ?  | Interpretation: auto")

        self.sidebar_pages = self._build_sidebar_pages(display_group)

        # Diagnostics panels (histogram/profile)
        self.hist_fig = Figure(figsize=(5, 3))
        self.hist_canvas = FigureCanvasQTAgg(self.hist_fig)
        self.ax_hist = self.hist_fig.add_subplot(111)
        self.profile_fig = Figure(figsize=(5, 3))
        self.profile_canvas = FigureCanvasQTAgg(self.profile_fig)
        self.ax_line = self.profile_fig.add_subplot(111)

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

        # Hooks for menus
        open_files_act.triggered.connect(self._open_files)
        open_folder_act.triggered.connect(self._open_folder)
        load_ann_current_act.triggered.connect(self._load_annotations_current)
        load_ann_multi_act.triggered.connect(self._load_annotations_multi)
        load_ann_all_act.triggered.connect(self._load_annotations_all)
        reload_ann_act.triggered.connect(self._reload_annotations_current)
        save_csv_act.triggered.connect(self._save_csv)
        save_json_act.triggered.connect(self._save_json)
        export_standard_act.triggered.connect(self._export_standard_bundle_dialog)
        export_view_act.triggered.connect(self._export_view_dialog)
        save_proj_act.triggered.connect(self._save_project)
        load_proj_act.triggered.connect(self._load_project)
        prefs_act.triggered.connect(self._show_preferences_dialog)
        reset_confirms_act.triggered.connect(self._reset_confirmations)
        about_act.triggered.connect(self._show_about)
        context_help_act.triggered.connect(self._show_contextual_help)
        shortcuts_act = actions.get("shortcuts")
        if shortcuts_act is not None:
            shortcuts_act.triggered.connect(self._show_keyboard_shortcuts)
            if DISABLE_SHORTCUTS:
                shortcuts_act.setEnabled(False)
                shortcuts_act.setVisible(False)
        if DISABLE_SHORTCUTS:
            try:
                self._disable_all_shortcuts()
            except Exception:
                pass
        exit_act.triggered.connect(self.close)
        show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
        clear_roi_act.triggered.connect(self._clear_roi)
        # P5.2: Multi-image ROI management
        if hasattr(self, "copy_roi_to_all_act"):
            self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
        if hasattr(self, "save_roi_template_act"):
            self.save_roi_template_act.triggered.connect(self._save_roi_template)
        if hasattr(self, "apply_roi_template_act"):
            self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
        if clear_hist_cache_act is not None:
            clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
        suggest_points_act.triggered.connect(self._suggest_points_current_slice)
        suggest_points_image_act.triggered.connect(self._suggest_points_current_image)
        select_suggestion_strategy_act.triggered.connect(self._select_suggestion_strategy_dialog)
        if getattr(self, "status_strategy_combo", None) is not None:
            self._sync_status_strategy_selector()
            self.status_strategy_combo.currentIndexChanged.connect(
                lambda _idx: self._set_suggestion_strategy(
                    str(self.status_strategy_combo.currentData() or self.status_strategy_combo.currentText()),
                    source="status_bar",
                )
            )
            self.status_strategy_combo.setToolTip(
                "Suggestion strategy:\n"
                "- Source Frame: peaks in unprocessed source signal\n"
                "- Corrected: peaks after correction\n"
                "- Evidence Consensus: strong across modalities\n"
                "- Evidence Contradiction: enforce positive/negative evidence rules"
            )
        if getattr(self, "status_modality_combo", None) is not None:
            self.status_modality_combo.currentIndexChanged.connect(
                lambda idx: self._set_primary_combo(int(idx))
            )
        if getattr(self, "status_assist_mode_btn", None) is not None:
            self.status_assist_mode_btn.toggled.connect(
                lambda checked: self._set_assist_mode(bool(checked), source="status_bar")
            )
            default_assist_mode = bool(self._settings.value("assistModeEnabled", False, type=bool))
            self._set_assist_mode(default_assist_mode, source="startup")
        load_suggestion_rule_config_act.triggered.connect(
            self._load_suggestion_rule_config_dialog
        )
        set_suggestion_score_threshold_act.triggered.connect(
            self._set_suggestion_score_threshold_dialog
        )
        accept_visible_suggestions_act.triggered.connect(self._accept_visible_suggestions)
        accept_green_suggestions_act.triggered.connect(self._accept_high_confidence_suggestions)
        accept_suggestions_in_roi_act.triggered.connect(self._accept_suggestions_in_roi)
        reject_visible_suggestions_act.triggered.connect(self._reject_visible_suggestions)
        clear_suggestions_act.triggered.connect(self._clear_suggestions_current_image)
        show_suggestion_patch_act.triggered.connect(self._show_current_suggestion_patch)
        if getattr(self, "show_all_predictions_act", None) is not None:
            self.show_all_predictions_act.triggered.connect(
                self._show_all_predictions_dialog
            )
        start_timed_session_assisted_act.triggered.connect(
            lambda: self._start_timed_annotation_session(True)
        )
        start_timed_session_manual_act.triggered.connect(
            lambda: self._start_timed_annotation_session(False)
        )
        stop_timed_session_act.triggered.connect(self._stop_timed_annotation_session)
        assist_warmup_act.triggered.connect(self._start_assist_warmup)
        train_ranker_now_act.triggered.connect(self._train_suggestion_ranker_now)
        if getattr(self, "show_calibration_visualizer_act", None) is not None:
            self.show_calibration_visualizer_act.triggered.connect(
                self._show_calibration_visualizer
            )
        if getattr(self, "compare_layer_presets_act", None) is not None:
            def _compare_from_panel() -> None:
                panel = getattr(self, "modality_layers_panel", None)
                if panel is None:
                    self._compare_modality_layer_presets("default", "default")
                    return
                a_name = str(panel.compare_a_edit.text() or "default")
                b_name = str(panel.compare_b_edit.text() or "default")
                self._compare_modality_layer_presets(a_name, b_name)

            self.compare_layer_presets_act.triggered.connect(_compare_from_panel)
        batch_correct_suggestions_act.triggered.connect(
            self._batch_correct_suggestions_dialog
        )
        propagate_suggestions_act.triggered.connect(
            self._propagate_suggestions_remaining_dialog
        )
        toggle_suggestions_overlay_act.triggered.connect(self._toggle_suggestions_overlay)
        if not DISABLE_QC:
            qc_validate_act.triggered.connect(self._trigger_qc_validation)
            qc_jump_next_act.triggered.connect(self._jump_to_next_qc_issue)
        set_current_user_act.triggered.connect(self._set_current_user_dialog)
        mark_selected_in_review_act.triggered.connect(
            lambda: self._set_selected_review_state("in_review")
        )
        mark_selected_approved_act.triggered.connect(
            lambda: self._set_selected_review_state("approved")
        )
        mark_selected_needs_changes_act.triggered.connect(
            lambda: self._set_selected_review_state("needs_changes")
        )
        assign_selected_act.triggered.connect(self._assign_selected_annotations_dialog)
        show_reviewer_analytics_act.triggered.connect(self._show_reviewer_analytics_dialog)
        queue_all_act.triggered.connect(lambda: self._set_review_queue_filter("all"))
        queue_my_act.triggered.connect(lambda: self._set_review_queue_filter("my_queue"))
        queue_needs_review_act.triggered.connect(
            lambda: self._set_review_queue_filter("needs_review")
        )
        queue_blocked_qc_act.triggered.connect(
            lambda: self._set_review_queue_filter("blocked_qc")
        )
        self.review_context_pack_act.triggered.connect(self._toggle_review_context_pack)

        self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
        self.toggle_hist_act.triggered.connect(self._toggle_hist_panel)
        self.toggle_left_act.triggered.connect(self._toggle_left_pane)
        self.toggle_settings_act.triggered.connect(self._toggle_settings_pane)
        self.link_zoom_act.triggered.connect(self._on_link_zoom_menu)
        self.reset_layout_act.triggered.connect(self._reset_layout)
        self.save_layout_act.triggered.connect(self._save_layout_default)
        self.toggle_overlay_act.triggered.connect(self._toggle_overlay)
        self.layout_preset_annotate_act.triggered.connect(lambda: self.apply_preset("Annotate"))
        self.layout_preset_analyze_act.triggered.connect(lambda: self.apply_preset("Analyze"))
        self.layout_preset_assist_expert_act.triggered.connect(
            lambda: self.apply_preset("Assist Expert")
        )
        self.layout_preset_minimal_act.triggered.connect(lambda: self.apply_preset("Minimal"))
        self.layout_preset_default_act.triggered.connect(lambda: self.apply_preset("Default"))
        if getattr(self, "advanced_panels_act", None) is not None:
            self.advanced_panels_act.triggered.connect(self._show_command_palette)
        if getattr(self, "undo_layout_change_act", None) is not None:
            self.undo_layout_change_act.triggered.connect(self._undo_layout_change)
        if getattr(self, "open_panel_policy_act", None) is not None:
            self.open_panel_policy_act.triggered.connect(
                lambda: self.open_preferences(section="panel_policy")
            )
        self.focus_canvas_mode_act.triggered.connect(
            lambda _checked=False: self._toggle_focus_canvas_mode()
        )
        self.command_palette_act.triggered.connect(self._show_command_palette)
        if not DISABLE_DIAGNOSTICS:
            self.toggle_logs_act.triggered.connect(
                lambda checked: self.set_panel_visible("logs", bool(checked), source="menu:layout")
            )
        self.toggle_overlay_act.setChecked(True)
        self.reset_view_act.triggered.connect(self.reset_all_view)
        self.show_profiles_act.triggered.connect(self._show_profile_dialog)
        self.show_bleach_act.triggered.connect(self._show_bleach_dialog)
        self.show_table_act.triggered.connect(self._show_table_dialog)
        if hasattr(self, "threshold_act"):
            self.threshold_act.triggered.connect(self._show_threshold_panel)
        if hasattr(self, "analyze_particles_act"):
            self.analyze_particles_act.triggered.connect(self._show_analyze_particles_panel)
        if hasattr(self, "smlm_act"):
            self.smlm_act.triggered.connect(self._show_smlm_panel)
        if hasattr(self, "deepstorm_act"):
            self.deepstorm_act.triggered.connect(self._show_deepstorm_panel)
        if hasattr(self, "rerun_smlm_act"):
            self.rerun_smlm_act.triggered.connect(self._rerun_last_smlm)
        if hasattr(self, "show_smlm_points_act"):
            self.show_smlm_points_act.triggered.connect(self._toggle_smlm_points)
        if hasattr(self, "show_smlm_sr_act"):
            self.show_smlm_sr_act.triggered.connect(self._toggle_smlm_sr)
        self.undo_act.triggered.connect(self.undo_last_action)
        self.redo_act.triggered.connect(self.redo_last_action)
        jump_to_frame_act.triggered.connect(self._jump_to_frame_dialog)
        jump_to_z_act.triggered.connect(self._jump_to_z_dialog)
        copy_display_act.triggered.connect(self._copy_display_settings)
        measure_act.triggered.connect(self._results_measure_current)
        self.show_recorder_act.triggered.connect(self._toggle_recorder)
        self.scalebar_chk.toggled.connect(self._on_scalebar_change)
        self.scalebar_length_spin.valueChanged.connect(self._on_scalebar_change)
        self.scalebar_thickness_spin.valueChanged.connect(self._on_scalebar_change)
        self.scalebar_location_combo.currentTextChanged.connect(self._on_scalebar_change)
        self.scalebar_text_chk.toggled.connect(self._on_scalebar_change)
        self.scalebar_background_chk.toggled.connect(self._on_scalebar_change)
        self.scalebar_export_chk.toggled.connect(self._on_scalebar_change)
        self.suggestion_auto_retrain_chk.toggled.connect(
            self._on_suggestion_auto_retrain_changed
        )
        self.suggestion_min_labels_spin.valueChanged.connect(
            self._on_suggestion_min_labels_changed
        )
        self.suggestion_train_now_btn.clicked.connect(self._train_suggestion_ranker_now)
        self.annotation_space_combo.currentTextChanged.connect(self._on_annotation_space_changed)
        self.generation_space_combo.currentTextChanged.connect(self._on_generation_space_changed)
        self.disable_bulk_accept_when_stale_chk.toggled.connect(
            self._on_disable_bulk_accept_when_stale_changed
        )
        self.interactive_learning_experimental_chk.toggled.connect(
            self._on_interactive_learning_experimental_changed
        )
        self.assist_min_total_spin.valueChanged.connect(self._on_assist_minima_changed)
        self.assist_min_positive_spin.valueChanged.connect(self._on_assist_minima_changed)
        self.assist_min_negative_spin.valueChanged.connect(self._on_assist_minima_changed)
        self.assist_min_context_spin.valueChanged.connect(self._on_assist_minima_changed)
        if not DISABLE_QC:
            self.qc_auto_show_chk.toggled.connect(self._on_qc_auto_show_changed)
        else:
            self.qc_auto_show_chk.setChecked(False)
            self.qc_auto_show_chk.setEnabled(False)
        self.assist_warmup_next_btn.clicked.connect(self._next_uncertain_suggestion)
        self.assist_warmup_refresh_btn.clicked.connect(self._refresh_assist_warmup_panel)
        if getattr(self, "review_queue_panel", None) is not None:
            self.review_queue_panel.accept_requested.connect(
                self._accept_current_uncertain_suggestion
            )
            self.review_queue_panel.accept_next_requested.connect(
                self._accept_and_next_uncertain_suggestion
            )
            self.review_queue_panel.accept_all_green_requested.connect(
                self._accept_high_confidence_suggestions
            )
            self.review_queue_panel.reject_requested.connect(
                self._reject_current_uncertain_suggestion
            )
            self.review_queue_panel.skip_requested.connect(self._next_uncertain_suggestion)
            self.review_queue_panel.next_uncertain_requested.connect(
                self._focus_current_uncertain_suggestion
            )
            self.review_queue_panel.apply_offset_requested.connect(
                self._apply_review_queue_offset
            )
            self.review_queue_panel.suggestion_row_selected.connect(
                self._on_review_queue_row_selected
            )
            self.review_queue_panel.decision_requested.connect(
                self._set_selected_suggestion_decision
            )
        if getattr(self, "modality_layers_panel", None) is not None:
            self.modality_layers_panel.layer_changed.connect(self._on_modality_layer_changed)
            self.modality_layers_panel.save_preset_requested.connect(
                self._save_modality_layer_preset
            )
            self.modality_layers_panel.load_preset_requested.connect(
                self._load_modality_layer_preset
            )
            self.modality_layers_panel.compare_presets_requested.connect(
                self._compare_modality_layer_presets
            )
            self._refresh_modality_layers_panel()
            if getattr(self, "_settings", None) is not None:
                show_hint = bool(self._settings.value("firstRunHintModalityLayers", True, type=bool))
                self.modality_layers_panel.first_run_hint_lbl.setVisible(show_hint)
                if show_hint:
                    self._settings.setValue("firstRunHintModalityLayers", False)
        self.quick_hist_act.triggered.connect(lambda _checked=False: self._toggle_hist_panel())
        self.quick_profile_act.triggered.connect(lambda _checked=False: self._toggle_profile_panel())
        if not DISABLE_QC:
            self.quick_qc_act.triggered.connect(
                lambda _checked=False: self.set_panel_visible(
                    "qc_issues", True, source="quick_button:qc"
                )
            )
        else:
            self.quick_qc_act.setEnabled(False)
            self.quick_qc_act.setVisible(False)
        for dock_attr in (
            "dock_hist",
            "dock_profile",
            "dock_qc_issues",
            "dock_density",
            "dock_modality_layers",
            "dock_logs",
            "dock_metadata",
            "dock_results",
            "dock_annotations",
            "dock_review_queue",
            "dock_suggestion_explain",
            "dock_advanced_analysis",
        ):
            dock = getattr(self, dock_attr, None)
            if dock is not None:
                dock.visibilityChanged.connect(lambda _v: self._sync_panel_visibility_state())
        if self.density_panel is not None:
            self.density_panel.model_browse_btn.clicked.connect(self._density_pick_model)
            self.density_panel.load_btn.clicked.connect(self._density_load_model)
            self.density_panel.run_btn.clicked.connect(self._density_run)
            self.density_panel.cancel_btn.clicked.connect(self._density_cancel)
            self.density_panel.export_map_btn.clicked.connect(self._density_export_map)
            self.density_panel.export_counts_btn.clicked.connect(self._density_export_counts)
            self.density_panel.overlay_chk.toggled.connect(self._density_overlay_toggle)
            self.density_panel.overlay_alpha.valueChanged.connect(self._density_overlay_changed)
            self.density_panel.overlay_cmap.currentTextChanged.connect(
                self._density_overlay_changed
            )
            self.density_panel.contours_chk.toggled.connect(self._density_overlay_changed)
        if getattr(self, "qc_issues_panel", None) is not None and not DISABLE_QC:
            self.qc_issues_panel.jump_to_location.connect(self._jump_to_qc_issue)
            self.qc_issues_panel.validation_requested.connect(self._trigger_qc_validation)
            self.qc_issues_panel.export_requested.connect(self._export_qc_report)
            self.qc_issues_panel.issue_status_changed.connect(self._on_qc_issue_status_changed)
        if hasattr(self, "annotation_meta_apply_btn"):
            self.annotation_meta_apply_btn.clicked.connect(self._apply_annotation_metadata)
            self.annotation_meta_close_btn.clicked.connect(self._dismiss_annotation_meta_banner)
        self._sync_panel_visibility_state()
        self._update_qc_button_highlight(0)
        self._refresh_panel_policy_controls()
        self._refresh_assist_warmup_panel()
        if hasattr(self, "_refresh_lazy_loader_tree"):
            self._refresh_lazy_loader_tree()
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
        if hasattr(self, "advanced_open_explain_btn"):
            self.advanced_open_explain_btn.clicked.connect(
                lambda: self._set_panel_visibility("suggestion_explain", True)
            )
        if hasattr(self, "advanced_open_training_btn"):
            self.advanced_open_training_btn.clicked.connect(
                lambda: self.open_preferences(section="training_controls")
            )
        if hasattr(self, "advanced_train_now_btn"):
            self.advanced_train_now_btn.clicked.connect(self._train_suggestion_ranker_now)
        if hasattr(self, "advanced_open_calib_btn"):
            self.advanced_open_calib_btn.clicked.connect(self._show_calibration_visualizer)
        if hasattr(self, "metadata_widget"):
            self.metadata_widget.load_full_requested.connect(self._load_full_metadata)
        if hasattr(self, "project_relink_panel"):
            self.project_relink_panel.retry_auto_requested.connect(
                lambda: self._retry_project_relink("auto")
            )
            self.project_relink_panel.retry_manual_requested.connect(
                lambda: self._retry_project_relink("manual")
            )
        if not DISABLE_QC:
            self.controller.annotations_changed.connect(
                lambda: self._schedule_qc_validation(self.controller.session_state.active_primary_id)
            )
        if DISABLE_QC:
            dock_qc = getattr(self, "dock_qc_issues", None)
            if dock_qc is not None:
                dock_qc.setVisible(False)
                dock_qc.toggleViewAction().setEnabled(False)
                dock_qc.toggleViewAction().setVisible(False)
        if DISABLE_DIAGNOSTICS:
            dock_logs = getattr(self, "dock_logs", None)
            if dock_logs is not None:
                dock_logs.setVisible(False)
                dock_logs.toggleViewAction().setEnabled(False)
                dock_logs.toggleViewAction().setVisible(False)
        self._rebuild_figure_layout()
        self._apply_default_layout()
        self._restore_layout()
        self._apply_default_preferences()
        QtCore.QTimer.singleShot(0, self._sync_channel_panel_for_active_image)
        QtCore.QTimer.singleShot(0, self._maybe_show_first_run_welcome)

    def _apply_default_preferences(self) -> None:
        """Apply startup preferences from QSettings without overwriting layouts."""
        preset = self._settings.value("defaultLayoutPreset", "Default", type=str)
        if preset and preset != "Default":
            if not self._settings.value("customState", type=QtCore.QByteArray):
                self.apply_preset(preset)
        default_cmap = self._settings.value("defaultColormap", lut_names()[0], type=str)
        if default_cmap in lut_names():
            self.current_cmap_idx = lut_names().index(default_cmap)
        default_fps = self._settings.value("defaultFPS", self.speed_slider.value(), type=int)
        self.speed_slider.setValue(int(default_fps))
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        if self.auto_pct_label is not None:
            self.auto_pct_label.setText(f"{low_pct:.2f}% / {high_pct:.2f}%")

    def _maybe_show_first_run_welcome(self) -> None:
        """Show a first-run quick guide for onboarding and discoverability."""
        if bool(self._settings.value("firstRunWelcomeShown", False, type=bool)):
            return
        self._settings.setValue("firstRunWelcomeShown", True)
        # Non-blocking onboarding: status message instead of modal popup.
        if hasattr(self, "_status_info"):
            self._status_info(
                "Welcome: A/R/N/P review suggestions | Check status bar | Layout menu has presets",
                timeout_ms=8000,
                source="setup.first_run",
            )
        elif hasattr(self, "_status_info"):
            self._status_info(
                "Welcome: A/R/N/P review suggestions | Check status bar | Layout menu has presets",
                timeout_ms=8000,
                source="setup.first_run",
            )

    def _init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
        ui_docks.init_panels(self, dock_menu)

    def _init_channel_panel_integration(self) -> None:
        """Wire channel panel signals to session state integration."""
        panel = getattr(self, "channel_panel", None)
        if panel is None:
            self.channel_integration = None
            return
        try:
            from phage_annotator.ui_qt.integration.channel_integration import (
                ChannelPanelIntegration,
            )
        except Exception:
            self.channel_integration = None
            return
        self.channel_integration = ChannelPanelIntegration(
            self.controller,
            refresh_request_callback=lambda: self._request_ui_refresh(
                "channel-integration", image=True, status=True
            ),
        )
        panel.channel_visibility_changed.connect(
            self.channel_integration.on_channel_visibility_changed
        )
        panel.channel_opacity_changed.connect(
            self.channel_integration.on_channel_opacity_changed
        )
        panel.channel_lut_changed.connect(self.channel_integration.on_channel_lut_changed)
        panel.blend_mode_changed.connect(self.channel_integration.on_blend_mode_changed)
        self._sync_channel_panel_for_active_image()

    def _sync_channel_panel_for_active_image(self) -> None:
        """Refresh channel panel visibility/settings for the active primary image."""
        panel = getattr(self, "channel_panel", None)
        integration = getattr(self, "channel_integration", None)
        if panel is None or integration is None or not self.images:
            return
        channel_count = int(getattr(self.primary_image, "channel_count", 1) or 1)
        dock = getattr(self, "dock_channels", None)
        hidden_for_single = bool(
            getattr(self, "_channel_panel_hidden_for_single_channel", False)
        )
        if channel_count <= 1:
            panel.setEnabled(False)
            if dock is not None:
                if hasattr(self, "set_panel_visible"):
                    self.set_panel_visible(
                        "channels", False, source="channel_panel:auto_single_channel"
                    )
                else:
                    dock.setVisible(False)
                self._channel_panel_hidden_for_single_channel = True
            return
        panel.setEnabled(True)
        settings = integration.initialize_from_session(channel_count)
        self.controller.set_channel_display_settings_value(settings.to_dict())
        panel.set_channel_settings(settings)
        should_show = (
            hidden_for_single
            or not getattr(self, "_channel_panel_autoshown", False)
            or (dock is not None and not dock.isVisible())
        )
        if dock is not None and should_show:
            if hasattr(self, "set_panel_visible"):
                self.set_panel_visible("channels", True, source="channel_panel:auto_multi_channel")
            else:
                dock.setVisible(True)
            try:
                dock.raise_()
            except Exception:
                pass
            self._channel_panel_autoshown = True
            self._channel_panel_hidden_for_single_channel = False

    def _build_sidebar_pages(
        self, display_group: QtWidgets.QGroupBox
    ) -> List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]]:
        pages: List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]] = []

        def _make_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            return scroll

        def _dock_button(text: str, dock_attr: str) -> QtWidgets.QPushButton:
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(
                lambda: self.set_panel_visible(
                    str(dock_attr).replace("dock_", ""),
                    True,
                    source="sidebar_button",
                )
            )
            return btn

        # Explore
        explore_panel = QtWidgets.QWidget()
        explore_layout = QtWidgets.QVBoxLayout(explore_panel)
        explore_layout.setContentsMargins(8, 8, 8, 8)
        explore_layout.setSpacing(8)
        explore_layout.addWidget(QtWidgets.QLabel("Lazy loading: enabled"))
        explore_layout.addWidget(self.explore_panel)
        explore_layout.addStretch(1)
        pages.append(("Explore", QtWidgets.QStyle.StandardPixmap.SP_DirIcon, _make_scroll(explore_panel)))

        # Annotate
        annotate_panel = QtWidgets.QWidget()
        annotate_layout = QtWidgets.QVBoxLayout(annotate_panel)
        annotate_layout.setContentsMargins(8, 8, 8, 8)
        annotate_layout.setSpacing(8)
        annotate_layout.addWidget(self.annotate_panel)
        annotate_layout.addStretch(1)
        pages.append(
            (
                "Annotate",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView,
                _make_scroll(annotate_panel),
            )
        )

        # Display
        display_panel = QtWidgets.QWidget()
        display_layout = QtWidgets.QVBoxLayout(display_panel)
        display_layout.setContentsMargins(8, 8, 8, 8)
        display_layout.setSpacing(8)
        self.reset_view_btn = QtWidgets.QPushButton("Reset view")
        self.reset_view_btn.setToolTip("Reset zoom and contrast")
        display_layout.addWidget(_dock_button("Show Histogram/B&C", "dock_hist"))
        display_layout.addWidget(_dock_button("Show Channels", "dock_channels"))
        display_layout.addWidget(self.reset_view_btn)
        display_layout.addWidget(display_group)
        display_layout.addStretch(1)
        pages.append(
            (
                "Display",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
                _make_scroll(display_panel),
            )
        )

        # Playback
        playback_panel = QtWidgets.QWidget()
        playback_layout = QtWidgets.QVBoxLayout(playback_panel)
        playback_layout.setContentsMargins(8, 8, 8, 8)
        playback_layout.setSpacing(8)
        playback_layout.addWidget(QtWidgets.QLabel("This page configures tools. Working views open as panels."))
        playback_layout.addWidget(QtWidgets.QLabel("Playback controls are in the fixed bottom bar."))
        open_playback_btn = QtWidgets.QPushButton("Open Playback Controls")
        open_playback_btn.clicked.connect(self._focus_playback_controls)
        playback_layout.addWidget(open_playback_btn)
        playback_layout.addWidget(self.axis_warning)
        playback_layout.addWidget(self.axes_info_label)
        playback_layout.addStretch(1)
        pages.append(("Playback Settings", QtWidgets.QStyle.StandardPixmap.SP_MediaPlay, _make_scroll(playback_panel)))

        # ROI/Crop
        roi_panel = QtWidgets.QWidget()
        roi_layout = QtWidgets.QVBoxLayout(roi_panel)
        roi_layout.setContentsMargins(8, 8, 8, 8)
        roi_layout.setSpacing(8)
        roi_layout.addWidget(_dock_button("Show ROI Controls", "dock_roi"))
        roi_layout.addWidget(_dock_button("Show ROI Manager", "dock_roi_manager"))
        clear_roi_btn = QtWidgets.QPushButton("Clear ROI")
        clear_roi_btn.clicked.connect(self._clear_roi)
        roi_layout.addWidget(clear_roi_btn)
        roi_layout.addWidget(QtWidgets.QLabel("ROI tools are available in the ROI dock."))
        roi_layout.addStretch(1)
        pages.append(("ROI/Crop", QtWidgets.QStyle.StandardPixmap.SP_ArrowUp, _make_scroll(roi_panel)))

        # Analysis
        analysis_panel = QtWidgets.QWidget()
        analysis_layout = QtWidgets.QVBoxLayout(analysis_panel)
        analysis_layout.setContentsMargins(8, 8, 8, 8)
        analysis_layout.setSpacing(8)
        analysis_layout.addWidget(_dock_button("Results", "dock_results"))
        analysis_layout.addWidget(_dock_button("Threshold", "dock_threshold"))
        analysis_layout.addWidget(_dock_button("Analyze Particles", "dock_particles"))
        analysis_layout.addWidget(_dock_button("SMLM", "dock_smlm"))
        analysis_layout.addWidget(_dock_button("Density", "dock_density"))
        analysis_layout.addWidget(_dock_button("Ortho Views", "dock_orthoview"))
        analysis_layout.addStretch(1)
        pages.append(("Analyze", QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon, _make_scroll(analysis_panel)))

        # Results
        results_panel = QtWidgets.QWidget()
        results_layout = QtWidgets.QVBoxLayout(results_panel)
        results_layout.setContentsMargins(8, 8, 8, 8)
        results_layout.setSpacing(8)
        results_layout.addWidget(QtWidgets.QLabel("This page configures tools. Working views open as panels."))
        open_results_btn = QtWidgets.QPushButton("Open Results Table")
        open_results_btn.clicked.connect(
            lambda: self.open_panel("results", reason="sidebar_button")
        )
        results_layout.addWidget(open_results_btn)
        results_layout.addWidget(_dock_button("Open Export Panel", "dock_results"))
        results_layout.addStretch(1)
        pages.append(("Results Hub", QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton, _make_scroll(results_panel)))

        # Project
        project_panel = QtWidgets.QWidget()
        project_layout = QtWidgets.QVBoxLayout(project_panel)
        project_layout.setContentsMargins(8, 8, 8, 8)
        project_layout.setSpacing(8)
        save_proj_btn = QtWidgets.QPushButton("Save Project")
        save_proj_btn.clicked.connect(self._save_project)
        project_layout.addWidget(save_proj_btn)
        load_proj_btn = QtWidgets.QPushButton("Load Project")
        load_proj_btn.clicked.connect(self._load_project)
        project_layout.addWidget(load_proj_btn)
        project_layout.addStretch(1)
        pages.append(("Project", QtWidgets.QStyle.StandardPixmap.SP_DirLinkIcon, _make_scroll(project_panel)))

        # Export
        export_panel = QtWidgets.QWidget()
        export_layout = QtWidgets.QVBoxLayout(export_panel)
        export_layout.setContentsMargins(8, 8, 8, 8)
        export_layout.setSpacing(8)
        export_csv_btn = QtWidgets.QPushButton("Save CSV")
        export_csv_btn.clicked.connect(self._save_csv)
        export_layout.addWidget(export_csv_btn)
        export_json_btn = QtWidgets.QPushButton("Save JSON")
        export_json_btn.clicked.connect(self._save_json)
        export_layout.addWidget(export_json_btn)
        export_view_btn = QtWidgets.QPushButton("Export View")
        export_view_btn.clicked.connect(self._export_view_dialog)
        export_layout.addWidget(export_view_btn)
        export_layout.addStretch(1)
        pages.append(("Export", QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton, _make_scroll(export_panel)))

        # Preferences / Debug
        prefs_panel = QtWidgets.QWidget()
        prefs_layout = QtWidgets.QVBoxLayout(prefs_panel)
        prefs_layout.setContentsMargins(8, 8, 8, 8)
        prefs_layout.setSpacing(8)
        self.pixel_size_spin = QtWidgets.QDoubleSpinBox()
        self.pixel_size_spin.setDecimals(4)
        self.pixel_size_spin.setRange(1e-4, 100.0)
        self.pixel_size_spin.setValue(self.pixel_size_um_per_px)
        pixel_row = QtWidgets.QHBoxLayout()
        pixel_row.addWidget(QtWidgets.QLabel("Pixel size (um/px)"))
        pixel_row.addWidget(self.pixel_size_spin)
        prefs_layout.addLayout(pixel_row)
        prefs_layout.addWidget(self.settings_advanced_container)
        prefs_btn = QtWidgets.QPushButton("Preferences…")
        prefs_btn.clicked.connect(self._show_preferences_dialog)
        prefs_layout.addWidget(prefs_btn)
        prefs_layout.addWidget(_dock_button("Logs", "dock_logs"))
        prefs_layout.addWidget(_dock_button("Performance", "dock_performance"))
        prefs_layout.addWidget(_dock_button("Metadata", "dock_metadata"))
        prefs_layout.addStretch(1)
        pages.append(("Preferences", QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView, _make_scroll(prefs_panel)))

        return pages

    def _build_roi_controls_layout(self) -> None:
        """Build ROI/crop controls used by the ROI dock."""
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row = 0

        shape_row = QtWidgets.QHBoxLayout()
        self.roi_shape_group = QtWidgets.QButtonGroup()
        roi_box = QtWidgets.QRadioButton("Box")
        roi_circle = QtWidgets.QRadioButton("Circle")
        self.roi_shape_group.addButton(roi_box)
        self.roi_shape_group.addButton(roi_circle)
        roi_box.setChecked(self.roi_shape == "box")
        roi_circle.setChecked(self.roi_shape == "circle")
        shape_row.addWidget(roi_box)
        shape_row.addWidget(roi_circle)
        layout.addWidget(QtWidgets.QLabel("ROI shape"), row, 0)
        layout.addLayout(shape_row, row, 1)
        row += 1

        self.roi_x_spin = QtWidgets.QDoubleSpinBox()
        self.roi_y_spin = QtWidgets.QDoubleSpinBox()
        self.roi_w_spin = QtWidgets.QDoubleSpinBox()
        self.roi_h_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.roi_x_spin, self.roi_y_spin, self.roi_w_spin, self.roi_h_spin):
            spin.setRange(0.0, 1_000_000.0)
            spin.setDecimals(2)
            spin.setSingleStep(1.0)
        rx, ry, rw, rh = self.roi_rect
        self.roi_x_spin.setValue(rx)
        self.roi_y_spin.setValue(ry)
        self.roi_w_spin.setValue(rw)
        self.roi_h_spin.setValue(rh)
        layout.addWidget(QtWidgets.QLabel("ROI X"), row, 0)
        layout.addWidget(self.roi_x_spin, row, 1)
        row += 1
        layout.addWidget(QtWidgets.QLabel("ROI Y"), row, 0)
        layout.addWidget(self.roi_y_spin, row, 1)
        row += 1
        layout.addWidget(QtWidgets.QLabel("ROI W"), row, 0)
        layout.addWidget(self.roi_w_spin, row, 1)
        row += 1
        layout.addWidget(QtWidgets.QLabel("ROI H"), row, 0)
        layout.addWidget(self.roi_h_spin, row, 1)
        row += 1

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(separator, row, 0, 1, 2)
        row += 1

        self.crop_x_spin = QtWidgets.QDoubleSpinBox()
        self.crop_y_spin = QtWidgets.QDoubleSpinBox()
        self.crop_w_spin = QtWidgets.QDoubleSpinBox()
        self.crop_h_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.crop_x_spin, self.crop_y_spin, self.crop_w_spin, self.crop_h_spin):
            spin.setRange(0.0, 1_000_000.0)
            spin.setDecimals(2)
            spin.setSingleStep(1.0)
        if self.crop_rect:
            cx, cy, cw, ch = self.crop_rect
        else:
            cx = cy = cw = ch = 0.0
        self.crop_x_spin.setValue(cx)
        self.crop_y_spin.setValue(cy)
        self.crop_w_spin.setValue(cw)
        self.crop_h_spin.setValue(ch)
        layout.addWidget(QtWidgets.QLabel("Crop X"), row, 0)
        layout.addWidget(self.crop_x_spin, row, 1)
        row += 1
        layout.addWidget(QtWidgets.QLabel("Crop Y"), row, 0)
        layout.addWidget(self.crop_y_spin, row, 1)
        row += 1
        layout.addWidget(QtWidgets.QLabel("Crop W"), row, 0)
        layout.addWidget(self.crop_w_spin, row, 1)
        row += 1
        layout.addWidget(QtWidgets.QLabel("Crop H"), row, 0)
        layout.addWidget(self.crop_h_spin, row, 1)
        row += 1

        auto_group = QtWidgets.QGroupBox("Auto ROI")
        auto_layout = QtWidgets.QGridLayout(auto_group)
        self.auto_roi_shape_combo = QtWidgets.QComboBox()
        self.auto_roi_shape_combo.addItems(["box", "circle", "auto"])
        self.auto_roi_mode_combo = QtWidgets.QComboBox()
        self.auto_roi_mode_combo.addItems(["W/H", "Area"])
        self.auto_roi_w_spin = QtWidgets.QSpinBox()
        self.auto_roi_h_spin = QtWidgets.QSpinBox()
        self.auto_roi_area_spin = QtWidgets.QSpinBox()
        for spin in (self.auto_roi_w_spin, self.auto_roi_h_spin, self.auto_roi_area_spin):
            spin.setRange(10, 1_000_000)
            spin.setSingleStep(10)
        default_shape = self._settings.value("autoRoiShape", "box", type=str)
        default_mode = self._settings.value("autoRoiMode", "W/H", type=str)
        default_w = self._settings.value("autoRoiW", 100, type=int)
        default_h = self._settings.value("autoRoiH", 100, type=int)
        default_area = self._settings.value("autoRoiArea", 100 * 100, type=int)
        self.auto_roi_shape_combo.setCurrentText(default_shape)
        self.auto_roi_mode_combo.setCurrentText(default_mode)
        self.auto_roi_w_spin.setValue(default_w)
        self.auto_roi_h_spin.setValue(default_h)
        self.auto_roi_area_spin.setValue(default_area)
        self.auto_roi_wh_widget = QtWidgets.QWidget()
        wh_layout = QtWidgets.QHBoxLayout(self.auto_roi_wh_widget)
        wh_layout.setContentsMargins(0, 0, 0, 0)
        wh_layout.setSpacing(6)
        wh_layout.addWidget(QtWidgets.QLabel("W"))
        wh_layout.addWidget(self.auto_roi_w_spin)
        wh_layout.addWidget(QtWidgets.QLabel("H"))
        wh_layout.addWidget(self.auto_roi_h_spin)
        self.auto_roi_area_widget = QtWidgets.QWidget()
        area_layout = QtWidgets.QHBoxLayout(self.auto_roi_area_widget)
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(6)
        area_layout.addWidget(QtWidgets.QLabel("Area"))
        area_layout.addWidget(self.auto_roi_area_spin)
        self.auto_roi_btn = QtWidgets.QPushButton("Auto ROI")

        auto_layout.addWidget(QtWidgets.QLabel("Shape"), 0, 0)
        auto_layout.addWidget(self.auto_roi_shape_combo, 0, 1)
        auto_layout.addWidget(QtWidgets.QLabel("Size mode"), 1, 0)
        auto_layout.addWidget(self.auto_roi_mode_combo, 1, 1)
        auto_layout.addWidget(self.auto_roi_wh_widget, 2, 0, 1, 2)
        auto_layout.addWidget(self.auto_roi_area_widget, 3, 0, 1, 2)
        auto_layout.addWidget(self.auto_roi_btn, 4, 0, 1, 2)
        layout.addWidget(auto_group, row, 0, 1, 2)

        self._roi_controls_layout = layout

    def _setup_status_bar(self) -> None:
        ui_docks.setup_status_bar(self)
        
        # Integrate Phase θ features (keyboard shortcuts and visual indicators)
        if HAS_BCONTRAST:
            try:
                integrate_b_contrast_features(self)
            except Exception as e:
                print(f"[B&C Integration] Warning: Failed to integrate B&C features: {e}")

    def _disable_all_shortcuts(self) -> None:
        """Disable keyboard shortcuts attached to Qt actions for this session."""
        # Menu/toolbar actions.
        for action in self.findChildren(QtWidgets.QAction):
            try:
                action.setShortcut("")
                action.setShortcuts([])
            except Exception:
                continue
