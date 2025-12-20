"""UI construction helpers for the main window."""

from __future__ import annotations

from typing import List, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from PyQt5.QtWidgets import QSizePolicy

from phage_annotator import ui_actions, ui_docks
from phage_annotator.gui_constants import DEFAULT_PLAYBACK_FPS
from phage_annotator.lut_manager import LUTS, cmap_for, lut_names
from phage_annotator.panels import PanelSpec
from phage_annotator.performance_panel import PerformancePanel
from phage_annotator.render_mpl import Renderer


class UiSetupMixin:
    """Mixin containing UI construction and dock wiring."""

    def _setup_ui(self) -> None:
        """Create menus, toolbars, dock panels, and central widgets.
        
        ARCHITECTURAL FLOW (fragile due to ordering):
        1. _setup_ui() called from __init__ of parent
        2. Calls _setup_status_bar() -> creates self.status and progress widgets
        3. Calls _init_panels() -> builds dock panel factories
        4. Panel factories (make_logs_widget, etc.) reference self.status, self.hist_chk, etc.
        
        ISSUE: If _init_panels() called BEFORE _setup_status_bar(), self.status=None,
        causing make_logs_widget() to skip adding status widget (defensive guard exists).
        
        PHASE 2D FIX:
        Create RenderContext and ViewState dataclasses that encapsulate all UI state.
        Instead of:
            def make_logs_widget(self) -> QWidget:
                if self.status is not None:  # <-- defensive guard due to ordering fragility
                    logs_layout.addWidget(self.status)
        
        Do:
            def make_logs_widget(self, ctx: RenderContext) -> QWidget:
                logs_layout.addWidget(ctx.status)  # <-- guaranteed to exist by type system
        
        This eliminates the need for defensive guards and makes dependencies explicit.
        """
        self.setWindowTitle("Phage Annotator - Microscopy Keypoints")
        self.resize(1700, 1000)
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AnimatedDocks
        )
        self.setStyleSheet(
            "QToolBar { spacing: 6px; }"
            "QDockWidget::title { padding: 4px 6px; }"
            "QGroupBox { margin-top: 8px; }"
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
        export_view_act = actions["export_view"]
        save_proj_act = actions["save_proj"]
        load_proj_act = actions["load_proj"]
        prefs_act = actions["prefs"]
        reset_confirms_act = actions["reset_confirms"]
        reload_ann_act = actions["reload_ann"]
        clear_hist_cache_act = actions.get("clear_hist_cache")
        exit_act = actions["exit"]
        about_act = actions["about"]
        copy_display_act = actions["copy_display"]
        measure_act = actions["measure"]
        show_roi_handles_act = self.show_roi_handles_act
        clear_roi_act = self.clear_roi_act

        # ===== ORDERING FIX: _setup_status_bar() MUST run BEFORE _init_panels() =====
        # RATIONALE: make_logs_widget() called from init_panels() checks if self.status exists.
        # If _setup_status_bar() hasn't run yet, self.status=None and logs widget lacks status bar.
        # By forcing this order, we ensure self.status exists when panel factories need it.
        # 
        # ARCHITECTURAL DEBT: This is a symptom of implicit state dependencies.
        # Phase 2D solution: Pass RenderContext(status, progress_bar, etc.) to _init_panels()
        # instead of having _init_panels() reach into self.* attributes.
        self._setup_status_bar()
        
        self._init_tool_bar()
        show_roi_handles_act.setChecked(bool(self.show_roi_handles))

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.setSpacing(10)

        # Explore pane: FOV list + primary/support (sidebar page)
        self.explore_panel = QtWidgets.QWidget()
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
        primary_box.addWidget(QtWidgets.QLabel("Primary"))
        self.primary_combo = QtWidgets.QComboBox()
        self.support_combo = QtWidgets.QComboBox()
        for img in self.images:
            self.primary_combo.addItem(img.name)
            self.support_combo.addItem(img.name)
        self.primary_combo.setCurrentIndex(self.current_image_idx)
        self.support_combo.setCurrentIndex(self.support_image_idx)
        primary_box.addWidget(self.primary_combo)
        primary_box.addWidget(QtWidgets.QLabel("Support"))
        primary_box.addWidget(self.support_combo)
        explore_layout.addLayout(primary_box)

        # Annotation table (own dock)
        self.annot_table = QtWidgets.QTableWidget(0, 5)
        self.annot_table.setHorizontalHeaderLabels(["T", "Z", "Y", "X", "Label"])
        self.annot_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.annot_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers)
        self.filter_current_chk = QtWidgets.QCheckBox("Show current slice only")
        self.annotation_table_panel = QtWidgets.QWidget()
        annot_layout = QtWidgets.QVBoxLayout(self.annotation_table_panel)
        annot_layout.setContentsMargins(8, 8, 8, 8)
        annot_layout.setSpacing(8)
        annot_layout.addWidget(self.filter_current_chk)
        annot_layout.addWidget(self.annot_table)

        # Figure area
        fig_container = QtWidgets.QWidget()
        fig_layout = QtWidgets.QVBoxLayout(fig_container)
        fig_layout.setContentsMargins(8, 8, 8, 8)
        fig_layout.setSpacing(6)
        self.figure = plt.figure(figsize=(13, 7))
        self.ax_frame = None
        self.ax_mean = None
        self.ax_comp = None
        self.ax_composite = None  # Alias for ax_comp
        self.ax_support = None
        self.ax_std = None
        self.ax_line = None
        self.ax_hist = None
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.updateGeometry()
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        fig_layout.addWidget(self.toolbar)
        fig_layout.addWidget(self.canvas, stretch=1)
        fallback_cmaps = [cmap_for(spec, False) for spec in LUTS]
        self.renderer = Renderer(self.figure, self.canvas, fallback_cmaps)
        self.renderer.set_roi_callback(self._on_roi_interactor_change)

        # Settings pane
        self.settings_widget = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(10)

        self.axis_warning = QtWidgets.QLabel()
        self.axis_warning.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.axis_warning.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.axis_warning.setOpenExternalLinks(False)
        self.axis_warning.linkActivated.connect(self._focus_axis_mode_control)
        self.axis_warning.setVisible(False)
        settings_layout.addWidget(self.axis_warning)

        axes_group = QtWidgets.QGroupBox("Axes")
        axes_layout = QtWidgets.QVBoxLayout(axes_group)
        self.axes_info_label = QtWidgets.QLabel("T: ?  Z: ?  Y: ?  X: ?  | Interpretation: auto")
        axes_layout.addWidget(self.axes_info_label)
        settings_layout.addWidget(axes_group)

        self.central_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.central_splitter.addWidget(fig_container)
        self.central_splitter.addWidget(self.settings_widget)
        self.central_splitter.setStretchFactor(0, 8)
        self.central_splitter.setStretchFactor(1, 2)
        central_layout.addWidget(self.central_splitter)

        # Primary controls bar
        primary_controls = QtWidgets.QGridLayout()
        row = 0

        self.t_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.t_slider_label = QtWidgets.QLabel("T: 1")
        self.t_slider.setSingleStep(1)
        self.t_minus_button = QtWidgets.QPushButton("-")
        self.t_plus_button = QtWidgets.QPushButton("+")
        self.t_minus_button.setToolTip("Previous time frame")
        self.t_plus_button.setToolTip("Next time frame")
        t_slider_box = QtWidgets.QHBoxLayout()
        t_slider_box.addWidget(self.t_minus_button)
        t_slider_box.addWidget(self.t_slider, stretch=1)
        t_slider_box.addWidget(self.t_plus_button)
        self.play_t_btn = QtWidgets.QPushButton("Play T")
        self.z_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.z_slider_label = QtWidgets.QLabel("Z: 1")
        self.z_slider.setSingleStep(1)
        self.z_minus_button = QtWidgets.QPushButton("-")
        self.z_plus_button = QtWidgets.QPushButton("+")
        self.z_minus_button.setToolTip("Previous Z plane")
        self.z_plus_button.setToolTip("Next Z plane")
        z_slider_box = QtWidgets.QHBoxLayout()
        z_slider_box.addWidget(self.z_minus_button)
        z_slider_box.addWidget(self.z_slider, stretch=1)
        z_slider_box.addWidget(self.z_plus_button)
        self.play_z_btn = QtWidgets.QPushButton("Play Z")
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, DEFAULT_PLAYBACK_FPS)
        self.speed_slider.setValue(DEFAULT_PLAYBACK_FPS)
        self.speed_slider.setSingleStep(1)
        self.speed_minus_button = QtWidgets.QPushButton("-")
        self.speed_plus_button = QtWidgets.QPushButton("+")
        self.speed_minus_button.setToolTip("Slow down playback")
        self.speed_plus_button.setToolTip("Speed up playback")
        speed_slider_box = QtWidgets.QHBoxLayout()
        speed_slider_box.addWidget(self.speed_minus_button)
        speed_slider_box.addWidget(self.speed_slider, stretch=1)
        speed_slider_box.addWidget(self.speed_plus_button)
        self.loop_chk = QtWidgets.QCheckBox("Loop")
        primary_controls.addWidget(QtWidgets.QLabel("Time"), row, 0)
        primary_controls.addWidget(self.t_slider_label, row, 1)
        primary_controls.addLayout(t_slider_box, row, 2)
        primary_controls.addWidget(self.play_t_btn, row, 3)
        row += 1
        primary_controls.addWidget(QtWidgets.QLabel("Depth"), row, 0)
        primary_controls.addWidget(self.z_slider_label, row, 1)
        primary_controls.addLayout(z_slider_box, row, 2)
        primary_controls.addWidget(self.play_z_btn, row, 3)
        row += 1
        primary_controls.addWidget(QtWidgets.QLabel("Speed (fps)"), row, 0)
        primary_controls.addLayout(speed_slider_box, row, 2)
        primary_controls.addWidget(self.loop_chk, row, 3)
        row += 1

        self.pixel_size_spin = QtWidgets.QDoubleSpinBox()
        self.pixel_size_spin.setDecimals(4)
        self.pixel_size_spin.setRange(1e-4, 100.0)
        self.pixel_size_spin.setValue(self.pixel_size_um_per_px)
        primary_controls.addWidget(QtWidgets.QLabel("Pixel size (um/px)"), row, 0)
        primary_controls.addWidget(self.pixel_size_spin, row, 1)
        row += 1

        self.reset_view_btn = QtWidgets.QPushButton("Reset view")
        self.reset_view_btn.setToolTip("Reset zoom and contrast")
        primary_controls.addWidget(self.reset_view_btn, row, 0, 1, 2)
        row += 1

        settings_layout.addLayout(primary_controls)

        display_group = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QGridLayout(display_group)
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
        display_layout.addWidget(QtWidgets.QLabel("Vmin"), drow, 0)
        display_layout.addWidget(self.vmin_label, drow, 1)
        display_layout.addLayout(vmin_slider_box, drow, 2)
        drow += 1
        display_layout.addWidget(QtWidgets.QLabel("Vmax"), drow, 0)
        display_layout.addWidget(self.vmax_label, drow, 1)
        display_layout.addLayout(vmax_slider_box, drow, 2)
        drow += 1
        # Percentile sliders are applied when data is available in _on_vminmax_change.

        auto_row = QtWidgets.QHBoxLayout()
        self.auto_btn = QtWidgets.QPushButton("Auto")
        self.auto_set_btn = QtWidgets.QPushButton("Set…")
        self.auto_pct_label = QtWidgets.QLabel("0.35% / 99.65%")
        auto_row.addWidget(self.auto_btn)
        auto_row.addWidget(self.auto_set_btn)
        auto_row.addWidget(self.auto_pct_label)
        display_layout.addWidget(QtWidgets.QLabel("Auto"), drow, 0)
        display_layout.addLayout(auto_row, drow, 2)
        drow += 1

        self.auto_scope_combo = QtWidgets.QComboBox()
        self.auto_scope_combo.addItems(["Current slice", "All frames", "Whole image"])
        self.auto_target_combo = QtWidgets.QComboBox()
        self.auto_target_combo.addItems(["Current panel", "All visible panels"])
        self.auto_roi_chk = QtWidgets.QCheckBox("Use ROI only")
        auto_opt_row = QtWidgets.QHBoxLayout()
        auto_opt_row.addWidget(self.auto_scope_combo)
        auto_opt_row.addWidget(self.auto_target_combo)
        auto_opt_row.addWidget(self.auto_roi_chk)
        display_layout.addWidget(QtWidgets.QLabel("Auto options"), drow, 0)
        display_layout.addLayout(auto_opt_row, drow, 2)
        drow += 1

        self.lut_combo = QtWidgets.QComboBox()
        self.lut_combo.addItems(lut_names())
        self.lut_invert_chk = QtWidgets.QCheckBox("Invert LUT")
        lut_box = QtWidgets.QHBoxLayout()
        lut_box.addWidget(self.lut_combo)
        lut_box.addWidget(self.lut_invert_chk)
        display_layout.addWidget(QtWidgets.QLabel("LUT"), drow, 0)
        display_layout.addLayout(lut_box, drow, 2)
        drow += 1

        self.gamma_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(2, 50)
        self.gamma_slider.setValue(10)
        self.gamma_label = QtWidgets.QLabel("1.00")
        gamma_row = QtWidgets.QHBoxLayout()
        gamma_row.addWidget(self.gamma_slider, stretch=1)
        gamma_row.addWidget(self.gamma_label)
        display_layout.addWidget(QtWidgets.QLabel("Gamma"), drow, 0)
        display_layout.addLayout(gamma_row, drow, 2)
        drow += 1

        self.log_chk = QtWidgets.QCheckBox("Log display")
        display_layout.addWidget(self.log_chk, drow, 0, 1, 2)
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
        scalebar_row = QtWidgets.QHBoxLayout()
        scalebar_row.addWidget(self.scalebar_chk)
        scalebar_row.addWidget(QtWidgets.QLabel("Length (um)"))
        scalebar_row.addWidget(self.scalebar_length_spin)
        display_layout.addWidget(QtWidgets.QLabel("Scale bar"), drow, 0)
        display_layout.addLayout(scalebar_row, drow, 2)
        drow += 1
        scalebar_opts = QtWidgets.QHBoxLayout()
        scalebar_opts.addWidget(QtWidgets.QLabel("Thickness"))
        scalebar_opts.addWidget(self.scalebar_thickness_spin)
        scalebar_opts.addWidget(QtWidgets.QLabel("Location"))
        scalebar_opts.addWidget(self.scalebar_location_combo)
        display_layout.addWidget(QtWidgets.QLabel("Scale options"), drow, 0)
        display_layout.addLayout(scalebar_opts, drow, 2)
        drow += 1
        scalebar_flags = QtWidgets.QHBoxLayout()
        scalebar_flags.addWidget(self.scalebar_text_chk)
        scalebar_flags.addWidget(self.scalebar_background_chk)
        scalebar_flags.addWidget(self.scalebar_export_chk)
        display_layout.addWidget(QtWidgets.QLabel("Scale flags"), drow, 0)
        display_layout.addLayout(scalebar_flags, drow, 2)
        drow += 1

        settings_layout.addWidget(display_group)

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
        r = 0

        self.axis_mode_combo = QtWidgets.QComboBox()
        self.axis_mode_combo.addItems(["auto", "time", "depth"])
        adv_layout.addWidget(QtWidgets.QLabel("Interpret 3D axis as"), r, 0)
        adv_layout.addWidget(self.axis_mode_combo, r, 1)
        r += 1

        # PHASE 2D FIX: Add marker and click radius controls (were missing, causing AttributeError)
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

        # PHASE 2D FIX: Add annotation visibility controls
        vis_opts = QtWidgets.QHBoxLayout()
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        self.show_frame_chk = QtWidgets.QCheckBox("Frame")
        self.show_mean_chk = QtWidgets.QCheckBox("Mean")
        self.show_comp_chk = QtWidgets.QCheckBox("Composite")
        self.show_support_chk = QtWidgets.QCheckBox("Support")
        self.show_frame_chk.setChecked(True)
        self.show_mean_chk.setChecked(True)
        self.show_comp_chk.setChecked(True)
        self.show_support_chk.setChecked(False)
        vis_opts.addWidget(self.show_ann_master_chk)
        vis_opts.addWidget(self.show_frame_chk)
        vis_opts.addWidget(self.show_mean_chk)
        vis_opts.addWidget(self.show_comp_chk)
        vis_opts.addWidget(self.show_support_chk)
        adv_layout.addWidget(QtWidgets.QLabel("Annotation visibility"), r, 0)
        adv_layout.addLayout(vis_opts, r, 1, 1, 3)
        r += 1

        # PHASE 2D FIX: Add profile controls (profile_clear_btn was missing)
        profile_controls = QtWidgets.QHBoxLayout()
        # Note: self.profile_chk already created in make_profile_widget(), but we need profile_clear_btn
        self.profile_clear_btn = QtWidgets.QPushButton("Clear profile")
        profile_controls.addWidget(self.profile_clear_btn)
        adv_layout.addWidget(QtWidgets.QLabel("Line profile actions"), r, 0)
        adv_layout.addLayout(profile_controls, r, 1, 1, 3)
        r += 1

        # PHASE 2D FIX: Add histogram controls (hist_region_combo, hist_scope_combo were missing)
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

        # PHASE 2D FIX: Add correction checkboxes
        corr_controls = QtWidgets.QHBoxLayout()
        self.illum_corr_chk = QtWidgets.QCheckBox("Illumination correction")
        self.bleach_corr_chk = QtWidgets.QCheckBox("Photobleaching correction")
        corr_controls.addWidget(self.illum_corr_chk)
        corr_controls.addWidget(self.bleach_corr_chk)
        adv_layout.addWidget(QtWidgets.QLabel("Corrections"), r, 0)
        adv_layout.addLayout(corr_controls, r, 1, 1, 3)
        r += 1

        # PHASE 2D FIX: Add ROI shape controls (roi_shape_group was missing)
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

        self.settings_advanced_container.setLayout(adv_container_layout)
        self.advanced_group.setLayout(adv_layout)
        adv_container_layout.addWidget(self.advanced_group)
        settings_layout.addWidget(self.annotate_panel)
        settings_layout.addWidget(self.settings_advanced_container)
        settings_layout.addStretch(1)

        # Diagnostics panels (histogram/profile)
        self.hist_fig = plt.figure(figsize=(5, 3))
        self.hist_canvas = FigureCanvasQTAgg(self.hist_fig)
        self.ax_hist = self.hist_fig.add_subplot(111)
        self.profile_fig = plt.figure(figsize=(5, 3))
        self.profile_canvas = FigureCanvasQTAgg(self.profile_fig)
        self.ax_line = self.profile_fig.add_subplot(111)

        # Panels/docks + sidebar (status bar must be set up first for logs widget)
        self._setup_status_bar()
        self._init_panels(dock_panels_menu)

        left_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        left_splitter.addWidget(self._build_sidebar_stack())
        left_splitter.addWidget(self.central_splitter)
        left_splitter.setStretchFactor(0, 0)
        left_splitter.setStretchFactor(1, 1)
        central_layout.addWidget(left_splitter)

        # Hooks for menus
        open_files_act.triggered.connect(self._open_files)
        open_folder_act.triggered.connect(self._open_folder)
        load_ann_current_act.triggered.connect(self._load_annotations_current)
        load_ann_multi_act.triggered.connect(self._load_annotations_multi)
        load_ann_all_act.triggered.connect(self._load_annotations_all)
        reload_ann_act.triggered.connect(self._reload_annotations_current)
        save_csv_act.triggered.connect(self._save_csv)
        save_json_act.triggered.connect(self._save_json)
        export_view_act.triggered.connect(self._export_view_dialog)
        save_proj_act.triggered.connect(self._save_project)
        load_proj_act.triggered.connect(self._load_project)
        prefs_act.triggered.connect(self._show_preferences_dialog)
        reset_confirms_act.triggered.connect(self._reset_confirmations)
        about_act.triggered.connect(self._show_about)
        shortcuts_act = actions.get("shortcuts")
        if shortcuts_act is not None:
            shortcuts_act.triggered.connect(self._show_keyboard_shortcuts)
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
        self.layout_preset_minimal_act.triggered.connect(lambda: self.apply_preset("Minimal"))
        self.layout_preset_default_act.triggered.connect(lambda: self.apply_preset("Default"))
        self.command_palette_act.triggered.connect(self._show_command_palette)
        self.toggle_logs_act.triggered.connect(
            lambda checked: (self.dock_logs.setVisible(checked) if self.dock_logs else None)
        )
        self.overlay_act.triggered.connect(self._toggle_overlay)
        self.view_overlay_act.triggered.connect(self._toggle_overlay)
        self.view_overlay_act.setChecked(True)
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
        if hasattr(self, "annotation_meta_apply_btn"):
            self.annotation_meta_apply_btn.clicked.connect(self._apply_annotation_metadata)
            self.annotation_meta_close_btn.clicked.connect(self._dismiss_annotation_meta_banner)
        if hasattr(self, "metadata_widget"):
            self.metadata_widget.load_full_requested.connect(self._load_full_metadata)
        self._rebuild_figure_layout()
        self._apply_default_layout()
        self._restore_layout()
        self._apply_default_preferences()

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

    def _init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
        ui_docks.init_panels(self, dock_menu)

    def _build_panel_registry(self) -> List[PanelSpec]:
        return ui_docks.build_panel_registry(self)

    def _apply_panel_defaults(self) -> None:
        ui_docks.apply_panel_defaults(self)

    def _create_dock(
        self, name: str, title: str, widget: QtWidgets.QWidget
    ) -> QtWidgets.QDockWidget:
        return ui_docks.create_dock(self, name, title, widget)

    def _wire_dock_action(
        self,
        dock: QtWidgets.QDockWidget,
        action: QtWidgets.QAction,
        checkbox: Optional[QtWidgets.QCheckBox] = None,
    ) -> None:
        ui_docks.wire_dock_action(self, dock, action, checkbox)

    def _make_sidebar_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_sidebar_widget(self)

    def _make_annotations_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_annotations_widget(self)

    def _make_roi_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_roi_widget(self)

    def _make_roi_manager_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_roi_manager_widget(self)

    def _make_results_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_results_widget(self)

    def _make_recorder_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_recorder_widget(self)

    def _make_hist_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_hist_widget(self)

    def _make_profile_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_profile_widget(self)

    def _make_orthoview_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_orthoview_widget(self)

    def _make_smlm_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_smlm_widget(self)

    def _make_threshold_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_threshold_widget(self)

    def _make_particles_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_particles_widget(self)

    def _make_density_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_density_widget(self)

    def _make_logs_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_logs_widget(self)

    def _make_metadata_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_metadata_widget(self)

    def _make_performance_widget(self) -> QtWidgets.QWidget:
        """Create the performance monitoring panel (P5.1)."""
        panel = PerformancePanel(parent=self)
        panel.set_cache(self.proj_cache)
        panel.set_ring_buffer(self._playback_ring)
        self.performance_panel = panel
        return panel

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
