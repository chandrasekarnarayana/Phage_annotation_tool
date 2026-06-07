"""Display, contrast, projection, sync, and scale-bar setup helpers."""

from __future__ import annotations

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.rendering.lut_manager import lut_names


def build_display_controls(self: object) -> QtWidgets.QGroupBox:
    """Build the contrast/projection display controls group."""
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

    self.contrast_hist_region_combo = QtWidgets.QComboBox()
    self.contrast_hist_region_combo.addItems(["Full image", "ROI", "Crop area"])
    self.contrast_hist_scope_combo = QtWidgets.QComboBox()
    self.contrast_hist_scope_combo.addItems(["Current slice", "Sampled stack"])
    self.contrast_hist_bins_spin = QtWidgets.QSpinBox()
    self.contrast_hist_bins_spin.setRange(16, 512)
    self.contrast_hist_bins_spin.setValue(int(getattr(self, "hist_bins", 64)))
    if getattr(self, "hist_region", "full") == "roi":
        self.contrast_hist_region_combo.setCurrentText("ROI")
    elif getattr(self, "hist_region", "full") == "crop":
        self.contrast_hist_region_combo.setCurrentText("Crop area")
    else:
        self.contrast_hist_region_combo.setCurrentText("Full image")
    self.contrast_hist_scope_combo.setCurrentText(str(getattr(self, "_hist_scope_mode", "Current slice")))
    self.contrast_hist_fig = Figure(figsize=(5, 2.6))
    self.contrast_hist_canvas = FigureCanvasQTAgg(self.contrast_hist_fig)
    self.ax_contrast_hist = self.contrast_hist_fig.add_subplot(111)
    self.contrast_hist_canvas.setMinimumHeight(180)
    hist_group = QtWidgets.QGroupBox("Histogram")
    hist_layout = QtWidgets.QVBoxLayout(hist_group)
    hist_layout.setContentsMargins(10, 8, 10, 8)
    hist_layout.setSpacing(6)
    hist_controls = QtWidgets.QHBoxLayout()
    hist_controls.addWidget(QtWidgets.QLabel("Region"))
    hist_controls.addWidget(self.contrast_hist_region_combo)
    hist_controls.addWidget(QtWidgets.QLabel("Scope"))
    hist_controls.addWidget(self.contrast_hist_scope_combo)
    hist_controls.addWidget(QtWidgets.QLabel("Bins"))
    hist_controls.addWidget(self.contrast_hist_bins_spin)
    hist_controls.addStretch(1)
    hist_layout.addLayout(hist_controls)
    hist_hint = QtWidgets.QLabel("Orange markers show the active min and max contrast limits.")
    hist_hint.setWordWrap(True)
    hist_hint.setStyleSheet("color: #546e7a;")
    hist_layout.addWidget(hist_hint)
    hist_layout.addWidget(self.contrast_hist_canvas)
    display_layout.addWidget(hist_group, drow, 0, 1, 3)
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

    return display_group
