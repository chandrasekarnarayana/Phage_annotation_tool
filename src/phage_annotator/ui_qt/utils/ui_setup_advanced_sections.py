"""Advanced setup, sidebar, and diagnostics panel helpers."""

from __future__ import annotations

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils.ui_setup_assist import build_assist_controls


def build_advanced_sidebar_sections(self: object, display_group: QtWidgets.QGroupBox) -> None:
    """Build advanced controls, sidebar pages, and diagnostic figures."""
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
    if not bool(getattr(self, "_annotate_roi_embedded", False)):
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
