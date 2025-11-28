"""Matplotlib + Qt keypoint annotation GUI for microscopy TIFF stacks.

Five synchronized panels (Frame, Mean, Composite, Support, Std) with ROI, autoplay, and
annotation tools. The layout uses splitters to prioritize the image panels while keeping
settings resizable. Images are loaded on demand to reduce memory usage; folders can be opened
to populate the FOV list without eager loading.
"""

from __future__ import annotations

import itertools
import pathlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tifffile as tif
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from scipy.optimize import curve_fit

from phage_annotator.annotations import (
    Keypoint,
    keypoints_from_csv,
    keypoints_from_json,
    save_keypoints_csv,
    save_keypoints_json,
)
from phage_annotator.config import DEFAULT_CONFIG, SUPPORTED_SUFFIXES
from phage_annotator.io import load_images, standardize_axes

COLORMAPS = ["gray", "viridis", "magma", "plasma", "cividis"]


@dataclass
class LazyImage:
    """Metadata and optional pixel data for an image."""

    path: pathlib.Path
    name: str
    shape: Tuple[int, ...]
    dtype: str
    has_time: bool
    has_z: bool
    array: Optional[np.ndarray] = None
    id: int = -1
    interpret_3d_as: str = "auto"


def _read_metadata(path: pathlib.Path) -> LazyImage:
    """Read image metadata cheaply without loading full data."""
    with tif.TiffFile(path) as tf:
        page = tf.series[0]
        shape = page.shape
        dtype = str(page.dtype)
    # Rough heuristics; actual standardization happens when loading.
    if len(shape) == 3:
        interpret = "time"
    else:
        interpret = "auto"
    has_time = len(shape) == 4 or (len(shape) == 3 and interpret == "time")
    has_z = len(shape) == 4 or (len(shape) == 3 and interpret == "depth")
    return LazyImage(
        path=path,
        name=path.name,
        shape=tuple(shape),
        dtype=dtype,
        has_time=has_time,
        has_z=has_z,
        interpret_3d_as=interpret,
    )


def _load_array(path: pathlib.Path, interpret_3d_as: str = "auto") -> Tuple[np.ndarray, bool, bool]:
    """Load image data and standardize to (T, Z, Y, X)."""
    arr = tif.imread(str(path))
    std, has_time, has_z = standardize_axes(arr, interpret_3d_as=interpret_3d_as)
    return std, has_time, has_z


class KeypointAnnotator(QtWidgets.QMainWindow):
    """Matplotlib + Qt GUI for keypoint annotation on T/Z image stacks."""

    def __init__(self, images: List[LazyImage], labels: Sequence[str] | None = None) -> None:
        super().__init__()
        if not images:
            raise ValueError("No images provided.")
        self.images = images
        for idx, img in enumerate(self.images):
            img.id = idx
        self.labels = list(labels or DEFAULT_CONFIG.default_labels)
        self.current_image_idx = 0
        self.support_image_idx = 0 if len(images) == 1 else 1
        self.current_cmap_idx = 0
        self.current_label = self.labels[0]
        # Marker size controls visual size only; click_radius_px controls selection tolerance.
        self.marker_size = 40
        self.click_radius_px = 6.0
        self.annotations: Dict[int, List[Keypoint]] = {img.id: [] for img in images}
        self.play_timer = QtCore.QTimer()
        self.play_mode: str | None = None  # "t" or "z"
        self.loop_playback = False
        self.axis_mode: Dict[int, str] = {img.id: "auto" for img in images}
        self.profile_line: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self.profile_enabled = True
        self.hist_enabled = True
        self.hist_bins = 100
        self.hist_region = "roi"  # roi|full
        self.link_zoom = True
        self.roi_shape = "circle"  # box|circle
        self.roi_rect = (0.0, 0.0, 600.0, 600.0)  # x, y, w, h defaults
        self.crop_rect = (300.0, 300.0, 600.0, 600.0)  # default crop
        self.annotate_target = "mean"  # frame|mean|comp|support
        self.annotation_scope = "all"  # current|all
        self.show_ann_frame = True
        self.show_ann_mean = True
        self.show_ann_comp = True
        self._last_zoom_linked: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self._axis_zoom: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = {}
        self._left_sizes: Optional[List[int]] = None
        self._block_table = False
        self._table_rows: List[Keypoint] = []

        self._suppress_limits = False

        self._setup_ui()
        self._bind_events()
        self._ensure_loaded(self.current_image_idx)
        self._ensure_loaded(self.support_image_idx)
        self._reset_crop(initial=True)
        self._reset_roi()
        self._refresh_image()

    # --- UI creation -----------------------------------------------------
    def _setup_ui(self) -> None:
        self.setWindowTitle("Phage Annotator - Microscopy Keypoints")
        self.resize(1700, 1000)

        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        open_files_act = file_menu.addAction("Open files…")
        open_folder_act = file_menu.addAction("Open folder…")
        load_ann_act = file_menu.addAction("Load annotations…")
        save_csv_act = file_menu.addAction("Save annotations (CSV)")
        save_json_act = file_menu.addAction("Save annotations (JSON)")
        file_menu.addSeparator()
        exit_act = file_menu.addAction("Exit")

        view_menu = menubar.addMenu("&View")
        self.toggle_profile_act = view_menu.addAction("Toggle line profile")
        self.toggle_profile_act.setCheckable(True)
        self.toggle_profile_act.setChecked(True)
        self.toggle_hist_act = view_menu.addAction("Toggle histogram")
        self.toggle_hist_act.setCheckable(True)
        self.toggle_hist_act.setChecked(True)
        self.toggle_left_act = view_menu.addAction("Toggle FOV pane")
        self.toggle_left_act.setCheckable(True)
        self.toggle_left_act.setChecked(True)
        self.toggle_settings_act = view_menu.addAction("Toggle settings panel")
        self.toggle_settings_act.setCheckable(True)
        self.toggle_settings_act.setChecked(True)
        self.link_zoom_act = view_menu.addAction("Link zoom")
        self.link_zoom_act.setCheckable(True)
        self.link_zoom_act.setChecked(True)

        analyze_menu = menubar.addMenu("&Analyze")
        self.show_profiles_act = analyze_menu.addAction("Line profiles (raw vs corrected)")
        self.show_bleach_act = analyze_menu.addAction("ROI mean + bleaching fit")
        self.show_table_act = analyze_menu.addAction("ROI mean table (per file)")

        help_menu = menubar.addMenu("&Help")
        about_act = help_menu.addAction("About")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central_layout = QtWidgets.QVBoxLayout(central)

        # Splitters: vertical for main area and settings
        self.vertical_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        central_layout.addWidget(self.vertical_splitter)

        self.top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.vertical_splitter.addWidget(self.top_splitter)
        self.settings_widget = QtWidgets.QWidget()
        self.vertical_splitter.addWidget(self.settings_widget)
        self.vertical_splitter.setStretchFactor(0, 8)
        self.vertical_splitter.setStretchFactor(1, 1)

        # Left pane: FOV list + annotation table
        self.left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        self.fov_list = QtWidgets.QListWidget()
        for img in self.images:
            self.fov_list.addItem(img.name)
        self.fov_list.setCurrentRow(self.current_image_idx)
        left_layout.addWidget(QtWidgets.QLabel("FOVs"))
        left_layout.addWidget(self.fov_list)

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
        left_layout.addLayout(primary_box)

        self.annot_table = QtWidgets.QTableWidget(0, 5)
        self.annot_table.setHorizontalHeaderLabels(["T", "Z", "Y", "X", "Label"])
        self.annot_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.annot_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers)
        self.filter_current_chk = QtWidgets.QCheckBox("Show current slice only")
        left_layout.addWidget(self.filter_current_chk)
        left_layout.addWidget(self.annot_table)

        self.top_splitter.addWidget(self.left_panel)

        # Figure area
        fig_container = QtWidgets.QWidget()
        fig_layout = QtWidgets.QVBoxLayout(fig_container)
        self.figure = plt.figure(figsize=(13, 7))
        gs = self.figure.add_gridspec(2, 5, height_ratios=[2, 1])
        self.ax_frame = self.figure.add_subplot(gs[0, 0], sharex=None, sharey=None)
        self.ax_mean = self.figure.add_subplot(gs[0, 1], sharex=self.ax_frame, sharey=self.ax_frame)
        self.ax_comp = self.figure.add_subplot(gs[0, 2], sharex=self.ax_frame, sharey=self.ax_frame)
        self.ax_support = self.figure.add_subplot(gs[0, 3], sharex=self.ax_frame, sharey=self.ax_frame)
        self.ax_std = self.figure.add_subplot(gs[0, 4], sharex=self.ax_frame, sharey=self.ax_frame)
        self.ax_line = self.figure.add_subplot(gs[1, 0:2])
        self.ax_hist = self.figure.add_subplot(gs[1, 2:4])
        self.ax_blank = self.figure.add_subplot(gs[1, 4])
        self.ax_blank.axis("off")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        fig_layout.addWidget(self.toolbar)
        fig_layout.addWidget(self.canvas, stretch=1)

        self.top_splitter.addWidget(fig_container)
        self.top_splitter.setStretchFactor(0, 0)
        self.top_splitter.setStretchFactor(1, 4)

        # Settings pane
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)

        # Primary controls bar
        primary_controls = QtWidgets.QGridLayout()
        row = 0

        self.t_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.t_slider_label = QtWidgets.QLabel("T: 1")
        self.play_t_btn = QtWidgets.QPushButton("Play T")
        self.z_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.z_slider_label = QtWidgets.QLabel("Z: 1")
        self.play_z_btn = QtWidgets.QPushButton("Play Z")
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.loop_chk = QtWidgets.QCheckBox("Loop")
        primary_controls.addWidget(QtWidgets.QLabel("Time"), row, 0)
        primary_controls.addWidget(self.t_slider_label, row, 1)
        primary_controls.addWidget(self.t_slider, row, 2)
        primary_controls.addWidget(self.play_t_btn, row, 3)
        row += 1
        primary_controls.addWidget(QtWidgets.QLabel("Depth"), row, 0)
        primary_controls.addWidget(self.z_slider_label, row, 1)
        primary_controls.addWidget(self.z_slider, row, 2)
        primary_controls.addWidget(self.play_z_btn, row, 3)
        row += 1
        primary_controls.addWidget(QtWidgets.QLabel("Speed (fps)"), row, 0)
        primary_controls.addWidget(self.speed_slider, row, 2)
        primary_controls.addWidget(self.loop_chk, row, 3)
        row += 1

        self.vmin_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vmax_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vmin_slider.setRange(0, 100)
        self.vmax_slider.setRange(0, 100)
        self.vmin_slider.setValue(5)
        self.vmax_slider.setValue(95)
        self.vmin_label = QtWidgets.QLabel("vmin: -")
        self.vmax_label = QtWidgets.QLabel("vmax: -")
        primary_controls.addWidget(QtWidgets.QLabel("Vmin"), row, 0)
        primary_controls.addWidget(self.vmin_label, row, 1)
        primary_controls.addWidget(self.vmin_slider, row, 2)
        row += 1
        primary_controls.addWidget(QtWidgets.QLabel("Vmax"), row, 0)
        primary_controls.addWidget(self.vmax_label, row, 1)
        primary_controls.addWidget(self.vmax_slider, row, 2)
        row += 1

        cmap_box = QtWidgets.QHBoxLayout()
        self.cmap_group = QtWidgets.QButtonGroup()
        for cmap in COLORMAPS:
            btn = QtWidgets.QRadioButton(cmap)
            if cmap == COLORMAPS[0]:
                btn.setChecked(True)
            self.cmap_group.addButton(btn)
            cmap_box.addWidget(btn)
        primary_controls.addWidget(QtWidgets.QLabel("Colormap"), row, 0)
        primary_controls.addLayout(cmap_box, row, 2)
        row += 1

        label_box = QtWidgets.QHBoxLayout()
        self.label_group = QtWidgets.QButtonGroup()
        for lbl in self.labels:
            btn = QtWidgets.QRadioButton(lbl)
            if lbl == self.current_label:
                btn.setChecked(True)
            self.label_group.addButton(btn)
            label_box.addWidget(btn)
        primary_controls.addWidget(QtWidgets.QLabel("Label"), row, 0)
        primary_controls.addLayout(label_box, row, 2)
        row += 1

        target_opts = QtWidgets.QHBoxLayout()
        self.scope_group = QtWidgets.QButtonGroup()
        scope_current = QtWidgets.QRadioButton("Current frame")
        scope_all = QtWidgets.QRadioButton("All frames")
        scope_all.setChecked(True)
        self.scope_group.addButton(scope_current)
        self.scope_group.addButton(scope_all)
        self.target_group = QtWidgets.QButtonGroup()
        t_frame = QtWidgets.QRadioButton("Annotate Frame")
        t_mean = QtWidgets.QRadioButton("Annotate Mean")
        t_mean.setChecked(True)
        self.target_group.addButton(t_frame)
        self.target_group.addButton(t_mean)
        t_comp = QtWidgets.QRadioButton("Annotate Composite")
        t_support = QtWidgets.QRadioButton("Annotate Support")
        self.target_group.addButton(t_comp)
        self.target_group.addButton(t_support)
        target_opts.addWidget(scope_current)
        target_opts.addWidget(scope_all)
        target_opts.addWidget(t_frame)
        target_opts.addWidget(t_mean)
        target_opts.addWidget(t_comp)
        target_opts.addWidget(t_support)
        primary_controls.addWidget(QtWidgets.QLabel("Annotation"), row, 0)
        primary_controls.addLayout(target_opts, row, 2)
        row += 1

        settings_layout.addLayout(primary_controls)

        # Advanced collapsible container
        self.settings_advanced_container = QtWidgets.QWidget()
        adv_container_layout = QtWidgets.QVBoxLayout(self.settings_advanced_container)
        advanced_group = QtWidgets.QGroupBox("Advanced")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(True)
        adv_layout = QtWidgets.QGridLayout()
        r = 0

        self.axis_mode_combo = QtWidgets.QComboBox()
        self.axis_mode_combo.addItems(["auto", "time", "depth"])
        adv_layout.addWidget(QtWidgets.QLabel("Interpret 3D axis as"), r, 0)
        adv_layout.addWidget(self.axis_mode_combo, r, 1)
        r += 1

        self.marker_size_spin = QtWidgets.QSpinBox()
        self.marker_size_spin.setRange(1, 100)
        self.marker_size_spin.setValue(self.marker_size)
        self.click_radius_spin = QtWidgets.QDoubleSpinBox()
        self.click_radius_spin.setRange(1, 50)
        self.click_radius_spin.setValue(self.click_radius_px)
        # Marker size is visual only; click radius is interaction tolerance.
        adv_layout.addWidget(QtWidgets.QLabel("Marker size"), r, 0)
        adv_layout.addWidget(self.marker_size_spin, r, 1)
        adv_layout.addWidget(QtWidgets.QLabel("Click radius (px)"), r, 2)
        adv_layout.addWidget(self.click_radius_spin, r, 3)
        r += 1

        vis_opts = QtWidgets.QHBoxLayout()
        self.show_ann_master_chk = QtWidgets.QCheckBox("Show annotations")
        self.show_ann_master_chk.setChecked(True)
        self.show_frame_chk = QtWidgets.QCheckBox("Show on Frame")
        self.show_mean_chk = QtWidgets.QCheckBox("Show on Mean")
        self.show_comp_chk = QtWidgets.QCheckBox("Show on Composite")
        self.show_support_chk = QtWidgets.QCheckBox("Show on Support")
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

        profile_controls = QtWidgets.QHBoxLayout()
        self.profile_chk = QtWidgets.QCheckBox("Show profile")
        self.profile_chk.setChecked(True)
        self.profile_mode_chk = QtWidgets.QCheckBox("Profile mode (click two points)")
        self.profile_clear_btn = QtWidgets.QPushButton("Clear profile")
        profile_controls.addWidget(self.profile_chk)
        profile_controls.addWidget(self.profile_mode_chk)
        profile_controls.addWidget(self.profile_clear_btn)
        adv_layout.addWidget(QtWidgets.QLabel("Line profile"), r, 0)
        adv_layout.addLayout(profile_controls, r, 1, 1, 3)
        r += 1

        hist_controls = QtWidgets.QHBoxLayout()
        self.hist_chk = QtWidgets.QCheckBox("Show histogram")
        self.hist_chk.setChecked(True)
        self.hist_region_group = QtWidgets.QButtonGroup()
        hist_roi = QtWidgets.QRadioButton("ROI")
        hist_full = QtWidgets.QRadioButton("Full")
        hist_roi.setChecked(True)
        self.hist_region_group.addButton(hist_roi)
        self.hist_region_group.addButton(hist_full)
        self.hist_bins_spin = QtWidgets.QSpinBox()
        self.hist_bins_spin.setRange(10, 512)
        self.hist_bins_spin.setValue(self.hist_bins)
        hist_controls.addWidget(self.hist_chk)
        hist_controls.addWidget(hist_roi)
        hist_controls.addWidget(hist_full)
        hist_controls.addWidget(QtWidgets.QLabel("Bins"))
        hist_controls.addWidget(self.hist_bins_spin)
        adv_layout.addWidget(QtWidgets.QLabel("Histogram"), r, 0)
        adv_layout.addLayout(hist_controls, r, 1, 1, 3)
        r += 1

        corr_controls = QtWidgets.QHBoxLayout()
        self.illum_corr_chk = QtWidgets.QCheckBox("Apply illumination correction")
        self.bleach_corr_chk = QtWidgets.QCheckBox("Apply photobleaching correction")
        corr_controls.addWidget(self.illum_corr_chk)
        corr_controls.addWidget(self.bleach_corr_chk)
        adv_layout.addWidget(QtWidgets.QLabel("Corrections"), r, 0)
        adv_layout.addLayout(corr_controls, r, 1, 1, 3)
        r += 1

        roi_controls = QtWidgets.QGridLayout()
        self.roi_x_spin = QtWidgets.QDoubleSpinBox()
        self.roi_y_spin = QtWidgets.QDoubleSpinBox()
        self.roi_w_spin = QtWidgets.QDoubleSpinBox()
        self.roi_h_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.roi_x_spin, self.roi_y_spin, self.roi_w_spin, self.roi_h_spin):
            spin.setRange(0, 1e6)
            spin.setDecimals(2)
        self.roi_shape_group = QtWidgets.QButtonGroup()
        roi_box = QtWidgets.QRadioButton("Box")
        roi_circle = QtWidgets.QRadioButton("Circle")
        roi_box.setChecked(True)
        self.roi_shape_group.addButton(roi_box)
        self.roi_shape_group.addButton(roi_circle)
        roi_controls.addWidget(QtWidgets.QLabel("ROI X"), 0, 0)
        roi_controls.addWidget(self.roi_x_spin, 0, 1)
        roi_controls.addWidget(QtWidgets.QLabel("ROI Y"), 0, 2)
        roi_controls.addWidget(self.roi_y_spin, 0, 3)
        roi_controls.addWidget(QtWidgets.QLabel("ROI W"), 1, 0)
        roi_controls.addWidget(self.roi_w_spin, 1, 1)
        roi_controls.addWidget(QtWidgets.QLabel("ROI H"), 1, 2)
        roi_controls.addWidget(self.roi_h_spin, 1, 3)
        roi_controls.addWidget(roi_box, 0, 4)
        roi_controls.addWidget(roi_circle, 1, 4)
        self.roi_reset_btn = QtWidgets.QPushButton("Reset ROI")
        roi_controls.addWidget(self.roi_reset_btn, 0, 5, 2, 1)
        adv_layout.addWidget(QtWidgets.QLabel("ROI (X, Y, W, H)"), r, 0)
        adv_layout.addLayout(roi_controls, r, 1, 1, 3)
        r += 1

        crop_controls = QtWidgets.QGridLayout()
        self.crop_x_spin = QtWidgets.QDoubleSpinBox()
        self.crop_y_spin = QtWidgets.QDoubleSpinBox()
        self.crop_w_spin = QtWidgets.QDoubleSpinBox()
        self.crop_h_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.crop_x_spin, self.crop_y_spin, self.crop_w_spin, self.crop_h_spin):
            spin.setRange(0, 1e6)
            spin.setDecimals(2)
        self.crop_reset_btn = QtWidgets.QPushButton("Reset crop")
        crop_controls.addWidget(QtWidgets.QLabel("Crop X"), 0, 0)
        crop_controls.addWidget(self.crop_x_spin, 0, 1)
        crop_controls.addWidget(QtWidgets.QLabel("Crop Y"), 0, 2)
        crop_controls.addWidget(self.crop_y_spin, 0, 3)
        crop_controls.addWidget(QtWidgets.QLabel("Crop W"), 1, 0)
        crop_controls.addWidget(self.crop_w_spin, 1, 1)
        crop_controls.addWidget(QtWidgets.QLabel("Crop H"), 1, 2)
        crop_controls.addWidget(self.crop_h_spin, 1, 3)
        crop_controls.addWidget(self.crop_reset_btn, 0, 4, 2, 1)
        adv_layout.addWidget(QtWidgets.QLabel("Display crop (X, Y, W, H)"), r, 0)
        adv_layout.addLayout(crop_controls, r, 1, 1, 3)
        r += 1

        self.save_csv_btn = QtWidgets.QPushButton("Save CSV")
        self.save_json_btn = QtWidgets.QPushButton("Save JSON")
        adv_layout.addWidget(self.save_csv_btn, r, 0)
        adv_layout.addWidget(self.save_json_btn, r, 1)

        advanced_group.setLayout(adv_layout)
        adv_container_layout.addWidget(advanced_group)
        settings_layout.addWidget(self.settings_advanced_container)

        self.status = QtWidgets.QLabel("")
        settings_layout.addWidget(self.status)

        # Menu connections
        open_files_act.triggered.connect(self._open_files)
        open_folder_act.triggered.connect(self._open_folder)
        load_ann_act.triggered.connect(self._load_annotations)
        save_csv_act.triggered.connect(self._save_csv)
        save_json_act.triggered.connect(self._save_json)
        exit_act.triggered.connect(self.close)
        self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
        self.toggle_hist_act.triggered.connect(self._toggle_hist_panel)
        self.toggle_left_act.triggered.connect(self._toggle_left_pane)
        self.toggle_settings_act.triggered.connect(self._toggle_settings_pane)
        self.link_zoom_act.triggered.connect(self._on_link_zoom_menu)
        about_act.triggered.connect(self._show_about)
        self.show_profiles_act.triggered.connect(self._show_profile_dialog)
        self.show_bleach_act.triggered.connect(self._show_bleach_dialog)
        self.show_table_act.triggered.connect(self._show_table_dialog)

    # --- Events and data helpers ----------------------------------------
    def _bind_events(self) -> None:
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("key_press_event", self._on_key)
        for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
            ax.callbacks.connect("xlim_changed", self._on_limits_changed)
            ax.callbacks.connect("ylim_changed", self._on_limits_changed)

        self.prev_btn = None  # kept for compatibility; buttons are managed in menu now

        self.fov_list.currentRowChanged.connect(self._set_fov)
        self.primary_combo.currentIndexChanged.connect(self._set_primary_combo)
        self.support_combo.currentIndexChanged.connect(self._set_support_combo)
        self.t_slider.valueChanged.connect(self._refresh_image)
        self.z_slider.valueChanged.connect(self._refresh_image)
        self.play_t_btn.clicked.connect(lambda: self._toggle_play("t"))
        self.play_z_btn.clicked.connect(lambda: self._toggle_play("z"))
        self.play_timer.timeout.connect(self._on_play_tick)
        self.speed_slider.valueChanged.connect(self._update_status)
        self.loop_chk.stateChanged.connect(self._on_loop_change)
        self.axis_mode_combo.currentTextChanged.connect(self._on_axis_mode_change)
        self.vmin_slider.valueChanged.connect(self._on_vminmax_change)
        self.vmax_slider.valueChanged.connect(self._on_vminmax_change)
        self.cmap_group.buttonToggled.connect(self._on_cmap_change)
        self.label_group.buttonToggled.connect(self._on_label_change)
        self.scope_group.buttonToggled.connect(self._on_scope_change)
        self.target_group.buttonToggled.connect(self._on_target_change)
        self.show_frame_chk.stateChanged.connect(self._refresh_image)
        self.show_mean_chk.stateChanged.connect(self._refresh_image)
        self.show_comp_chk.stateChanged.connect(self._refresh_image)
        self.marker_size_spin.valueChanged.connect(self._on_marker_size_change)
        self.click_radius_spin.valueChanged.connect(self._on_click_radius_change)
        self.roi_reset_btn.clicked.connect(self._reset_roi)
        self.roi_x_spin.valueChanged.connect(self._on_roi_change)
        self.roi_y_spin.valueChanged.connect(self._on_roi_change)
        self.roi_w_spin.valueChanged.connect(self._on_roi_change)
        self.roi_h_spin.valueChanged.connect(self._on_roi_change)
        self.roi_shape_group.buttonToggled.connect(self._on_roi_shape_change)
        self.profile_chk.stateChanged.connect(self._refresh_image)
        self.profile_mode_chk.stateChanged.connect(self._on_profile_mode)
        self.profile_clear_btn.clicked.connect(self._clear_profile)
        self.hist_chk.stateChanged.connect(self._refresh_image)
        self.hist_region_group.buttonToggled.connect(self._on_hist_region)
        self.hist_bins_spin.valueChanged.connect(self._refresh_image)
        self.save_csv_btn.clicked.connect(self._save_csv)
        self.save_json_btn.clicked.connect(self._save_json)
        self.filter_current_chk.stateChanged.connect(self._populate_table)
        self.crop_reset_btn.clicked.connect(self._reset_crop)
        self.crop_x_spin.valueChanged.connect(self._on_crop_change)
        self.crop_y_spin.valueChanged.connect(self._on_crop_change)
        self.crop_w_spin.valueChanged.connect(self._on_crop_change)
        self.crop_h_spin.valueChanged.connect(self._on_crop_change)
        self.annot_table.itemSelectionChanged.connect(self._on_table_selection)
        self.annot_table.itemChanged.connect(self._on_table_item_changed)
        self.show_ann_master_chk.stateChanged.connect(self._refresh_image)

    def _on_key(self, event) -> None:
        """Handle keyboard shortcuts for reset zoom, colormap cycle, and quick-save."""
        if event.key == "r":
            for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
                ax.set_xlim(auto=True)
                ax.set_ylim(auto=True)
            self.canvas.draw_idle()
        elif event.key == "c":
            self.current_cmap_idx = (self.current_cmap_idx + 1) % len(COLORMAPS)
            self._refresh_image()
        elif event.key == "s":
            self._quick_save_csv()

    @property
    def primary_image(self) -> LazyImage:
        return self.images[self.current_image_idx]

    @property
    def support_image(self) -> LazyImage:
        return self.images[self.support_image_idx]

    def _ensure_loaded(self, idx: int) -> None:
        img = self.images[idx]
        if img.array is None:
            arr, has_time, has_z = _load_array(img.path, interpret_3d_as=img.interpret_3d_as)
            img.array = arr
            img.has_time = has_time
            img.has_z = has_z
        # Drop others to save memory (keep primary and support)
        for j, other in enumerate(self.images):
            if j not in (self.current_image_idx, self.support_image_idx):
                other.array = None

    def _effective_axes(self, img: LazyImage) -> Tuple[bool, bool]:
        mode = img.interpret_3d_as
        if mode == "time":
            return True, img.has_z
        if mode == "depth":
            return False, True
        return img.has_time, img.has_z

    def _slice_indices(self, img: LazyImage) -> Tuple[int, int]:
        has_time, has_z = self._effective_axes(img)
        t_idx = self.t_slider.value() if has_time else 0
        z_idx = self.z_slider.value() if has_z else 0
        if not has_time and has_z:
            z_idx = self.t_slider.value()
            t_idx = 0
        return t_idx, z_idx

    def _slice_data(self, img: LazyImage) -> np.ndarray:
        t_idx, z_idx = self._slice_indices(img)
        assert img.array is not None
        return img.array[t_idx, z_idx, :, :]

    def _projection(self, img: LazyImage) -> np.ndarray:
        assert img.array is not None
        return img.array.mean(axis=(0, 1))

    def _std_projection(self, img: LazyImage) -> np.ndarray:
        assert img.array is not None
        return img.array.std(axis=(0, 1))

    # --- Rendering -------------------------------------------------------
    def _refresh_image(self) -> None:
        # Preserve current zoom before redraw
        self._capture_zoom_state()
        self._ensure_loaded(self.current_image_idx)
        self._ensure_loaded(self.support_image_idx)
        prim = self.primary_image
        has_time, has_z = self._effective_axes(prim)
        t_max = (prim.array.shape[0] - 1) if prim.array is not None else 0
        z_max = (prim.array.shape[1] - 1) if prim.array is not None else 0
        self.t_slider.setEnabled(has_time or has_z)
        self.z_slider.setEnabled(has_z)
        self.t_slider.setMaximum(max(t_max, 0))
        self.z_slider.setMaximum(max(z_max, 0))
        if self.t_slider.value() > t_max:
            self.t_slider.blockSignals(True)
            self.t_slider.setValue(t_max)
            self.t_slider.blockSignals(False)
        if self.z_slider.value() > z_max:
            self.z_slider.blockSignals(True)
            self.z_slider.setValue(z_max)
            self.z_slider.blockSignals(False)
        self.t_slider_label.setText(f"T: {self.t_slider.value() + 1}/{t_max + 1}")
        self.z_slider_label.setText(f"Z: {self.z_slider.value() + 1}/{z_max + 1}")

        vmin, vmax = self._current_vmin_vmax()
        cmap = COLORMAPS[self.current_cmap_idx]

        slice_data = self._apply_crop(self._slice_data(prim))
        mean_data = self._apply_crop(self._projection(prim))
        std_data = self._apply_crop(self._std_projection(prim))
        support_slice = self._apply_crop(self._slice_data(self.support_image))

        for ax, title in [
            (self.ax_frame, f"Frame (T {self.t_slider.value()+1}/{t_max+1})"),
            (self.ax_mean, "Mean IMG"),
            (self.ax_comp, "Composite / GT IMG"),
            (self.ax_support, "Support (epi)"),
            (self.ax_std, "STD IMG"),
        ]:
            ax.clear()
            ax.set_title(title)

        self.ax_frame.imshow(slice_data, cmap=cmap, vmin=vmin, vmax=vmax)
        self.ax_mean.imshow(mean_data, cmap=cmap, vmin=vmin, vmax=vmax)
        self.ax_comp.imshow(mean_data, cmap=cmap, vmin=vmin, vmax=vmax)
        self.ax_support.imshow(support_slice, cmap=cmap, vmin=vmin, vmax=vmax)
        # Auto-contrast std projection based on its own data (zoomed/cropped region).
        std_vmin = float(np.percentile(std_data, self.vmin_slider.value()))
        std_vmax = float(np.percentile(std_data, self.vmax_slider.value()))
        if std_vmin >= std_vmax:
            std_vmax = std_vmin + 1e-3
        self.ax_std.imshow(std_data, cmap=cmap, vmin=std_vmin, vmax=std_vmax)

        self._draw_roi()
        self._draw_points()
        self._draw_diagnostics(slice_data, vmin, vmax)
        self._restore_zoom(slice_data.shape)
        self.canvas.draw_idle()
        self._populate_table()
        self._update_status()

    def _draw_roi(self) -> None:
        x, y, w, h = self.roi_rect
        cx, cy = x + w / 2, y + h / 2
        r = min(w, h) / 2
        active_color = "#ff9800" if self.annotate_target == "frame" else "#00acc1"
        neutral_color = "#cccccc"
        for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
            is_target = (
                (self.annotate_target == "frame" and ax is self.ax_frame)
                or (self.annotate_target == "mean" and ax is self.ax_mean)
                or (self.annotate_target == "comp" and ax is self.ax_comp)
                or (self.annotate_target == "support" and ax is self.ax_support)
            )
            color = active_color if is_target else neutral_color
            if self.roi_shape == "box":
                rect = plt.Rectangle((x, y), w, h, color=color, fill=False, linewidth=1.5, alpha=0.9)
                ax.add_patch(rect)
            else:
                circ = plt.Circle((cx, cy), r, color=color, fill=False, linewidth=1.5, alpha=0.9)
                ax.add_patch(circ)

    def _draw_points(self) -> None:
        t, z = self.t_slider.value(), self.z_slider.value()
        pts = self._current_keypoints()
        selected_rows = [idx.row() for idx in self.annot_table.selectionModel().selectedRows()] if self.annot_table.selectionModel() else []
        selected_pts: List[Keypoint] = []
        if self._table_rows:
            for row in selected_rows:
                if 0 <= row < len(self._table_rows):
                    selected_pts.append(self._table_rows[row])

        def scatter_on(ax, predicate, faded=False):
            pts_sel = [(kp.y, kp.x, kp.label) for kp in pts if predicate(kp)]
            if not pts_sel:
                return
            ys, xs, labels = zip(*pts_sel)
            colors = [self._label_color(lbl, faded=faded) for lbl in labels]
            ax.scatter(xs, ys, c=colors, s=self.marker_size, marker="o", edgecolors="k" if not faded else "none")

        if self.show_ann_master_chk.isChecked() and self.show_ann_frame:
            scatter_on(self.ax_frame, lambda kp: (kp.t in (t, -1)) and (kp.z in (z, -1)))
        if self.show_ann_master_chk.isChecked() and self.show_ann_mean:
            scatter_on(self.ax_mean, lambda kp: True, faded=False)
        if self.show_ann_master_chk.isChecked() and self.show_ann_comp:
            scatter_on(self.ax_comp, lambda kp: True, faded=False)
        if self.show_ann_master_chk.isChecked() and self.show_support_chk.isChecked():
            scatter_on(self.ax_support, lambda kp: (kp.t in (t, -1)) and (kp.z in (z, -1)), faded=True)

        # Highlight selected points in red across all image axes
        if selected_pts and self.show_ann_master_chk.isChecked():
            for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
                ys = [kp.y for kp in selected_pts]
                xs = [kp.x for kp in selected_pts]
                ax.scatter(xs, ys, c="red", s=self.marker_size * 1.3, marker="o", edgecolors="k")

    def _draw_diagnostics(self, slice_data: np.ndarray, vmin: float, vmax: float) -> None:
        if self.profile_enabled and self.profile_chk.isChecked():
            self.ax_line.clear()
            if self.profile_line:
                (y1, x1), (y2, x2) = self.profile_line
                yy, xx = np.linspace(y1, y2, 200), np.linspace(x1, x2, 200)
                vals = slice_data[yy.astype(int).clip(0, slice_data.shape[0] - 1), xx.astype(int).clip(0, slice_data.shape[1] - 1)]
                self.ax_line.plot(vals)
                self.ax_line.set_title("Line profile (user)")
            else:
                y_center = slice_data.shape[0] // 2
                profile = slice_data[y_center, :]
                self.ax_line.plot(profile)
                self.ax_line.set_title("Line profile (center row)")
            self.ax_line.set_xlabel("X")
            self.ax_line.set_ylabel("Intensity")
            self.ax_line.axis("on")
        else:
            self.ax_line.clear()
            self.ax_line.axis("off")

        if self.hist_enabled and self.hist_chk.isChecked():
            self.ax_hist.clear()
            vals = self._roi_values(slice_data) if self.hist_region == "roi" else slice_data.flatten()
            bins = self.hist_bins_spin.value()
            self.ax_hist.hist(vals, bins=bins, range=(vmin, vmax), color="#5555aa")
            self.ax_hist.set_title("Intensity histogram")
            self.ax_hist.set_xlabel("Intensity")
            self.ax_hist.set_ylabel("Count")
            if vals.size:
                stats = f"Min {vals.min():.3f} | Max {vals.max():.3f} | Mean {vals.mean():.3f} | Std {vals.std():.3f} | Bins {bins}"
                self.ax_hist.text(0.02, 0.95, stats, transform=self.ax_hist.transAxes, va="top", fontsize=8)
            self.ax_hist.axis("on")
        else:
            self.ax_hist.clear()
            self.ax_hist.axis("off")

    # --- ROI helpers -----------------------------------------------------
    def _roi_mask(self, shape: Tuple[int, int]) -> np.ndarray:
        h, w = shape
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        rx, ry, rw, rh = self.roi_rect
        if self.roi_shape == "box":
            return (x >= rx) & (x <= rx + rw) & (y >= ry) & (y <= ry + rh)
        cx, cy = rx + rw / 2, ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2

    def _roi_values(self, slice_data: np.ndarray) -> np.ndarray:
        mask = self._roi_mask(slice_data.shape)
        return slice_data[mask]

    def _reset_roi(self) -> None:
        self._ensure_loaded(self.current_image_idx)
        prim = self.primary_image
        if prim.array is None:
            return
        if self.crop_rect:
            _, _, rw_full, rh_full = self.crop_rect
            w, h = rw_full, rh_full
        else:
            h, w = prim.array.shape[2], prim.array.shape[3]
        # Default ROI values if unset
        rx, ry, rw, rh = self.roi_rect
        if rw == 0 or rh == 0:
            rx, ry, rw, rh = w / 4, h / 4, w / 2, h / 2
        self.roi_rect = (rx, ry, rw, rh)
        self.roi_x_spin.setValue(rx)
        self.roi_y_spin.setValue(ry)
        self.roi_w_spin.setValue(rw)
        self.roi_h_spin.setValue(rh)

    def _on_roi_change(self) -> None:
        self.roi_rect = (
            self.roi_x_spin.value(),
            self.roi_y_spin.value(),
            self.roi_w_spin.value(),
            self.roi_h_spin.value(),
        )
        self._refresh_image()

    def _on_roi_shape_change(self) -> None:
        btns = self.roi_shape_group.buttons()
        self.roi_shape = "box" if btns[0].isChecked() else "circle"
        self._refresh_image()

    # --- Crop helpers ----------------------------------------------------
    def _reset_crop(self, initial: bool = False) -> None:
        self._ensure_loaded(self.current_image_idx)
        prim = self.primary_image
        if prim.array is None:
            return
        h, w = prim.array.shape[2], prim.array.shape[3]
        if initial and self.crop_rect:
            cx, cy, cw, ch = self.crop_rect
        else:
            cx, cy, cw, ch = 0.0, 0.0, float(w), float(h)
        self.crop_rect = (cx, cy, cw, ch)
        self.crop_x_spin.setValue(cx)
        self.crop_y_spin.setValue(cy)
        self.crop_w_spin.setValue(cw)
        self.crop_h_spin.setValue(ch)
        self._last_zoom_linked = None
        self._refresh_image()

    def _on_crop_change(self) -> None:
        self.crop_rect = (
            self.crop_x_spin.value(),
            self.crop_y_spin.value(),
            self.crop_w_spin.value(),
            self.crop_h_spin.value(),
        )
        self._last_zoom_linked = None
        self._refresh_image()

    def _apply_crop(self, data: np.ndarray) -> np.ndarray:
        if self.crop_rect is None:
            return data
        x, y, w, h = self.crop_rect
        x0, y0 = int(max(0, x)), int(max(0, y))
        x1, y1 = int(min(data.shape[1], x0 + max(1, int(w)))), int(min(data.shape[0], y0 + max(1, int(h))))
        return data[y0:y1, x0:x1]

    # --- Annotation logic ------------------------------------------------
    def _on_click(self, event) -> None:
        target_map = {
            "frame": self.ax_frame,
            "mean": self.ax_mean,
            "comp": self.ax_comp,
            "support": self.ax_support,
        }
        target_ax = target_map.get(self.annotate_target, self.ax_frame)
        if event.inaxes not in set(target_map.values()):
            if self.profile_mode_chk.isChecked() and event.inaxes in {self.ax_frame, self.ax_mean}:
                self._handle_profile_click(event)
            return
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return
        if event.inaxes is not target_ax:
            return
        # ROI gate
        if not self._point_in_roi(event.xdata, event.ydata):
            self._set_status("Click outside ROI ignored")
            return
        t, z = self.t_slider.value(), self.z_slider.value()
        if self._remove_annotation_near(target_ax, t, z, event.xdata, event.ydata):
            self._refresh_image()
            return
        self._add_annotation(self.primary_image.id, t, z, event.ydata, event.xdata, self.current_label, self.annotation_scope)
        self._refresh_image()

    def _add_annotation(self, image_id: int, t: int, z: int, y: float, x: float, label: str, scope: str) -> None:
        pts = self.annotations.setdefault(image_id, [])
        pts.append(
            Keypoint(
                image_id=image_id,
                image_name=self.primary_image.name,
                t=t if scope == "current" else -1,
                z=z if scope == "current" else -1,
                y=float(y),
                x=float(x),
                label=label,
            )
        )

    def _remove_annotation_near(self, ax, t: int, z: int, x: float, y: float) -> bool:
        pts = self._current_keypoints()
        if not pts:
            return False
        click_disp = ax.transData.transform((x, y))
        for idx, kp in enumerate(list(pts)):
            if kp.t not in (t, -1) or kp.z not in (z, -1):
                continue
            kp_disp = ax.transData.transform((kp.x, kp.y))
            dist = np.hypot(kp_disp[0] - click_disp[0], kp_disp[1] - click_disp[1])
            if dist <= self.click_radius_px:
                del pts[idx]
                return True
        return False

    def _handle_profile_click(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return
        if self.profile_line is None:
            self.profile_line = ((event.ydata, event.xdata), (event.ydata, event.xdata))
        else:
            self.profile_line = (self.profile_line[0], (event.ydata, event.xdata))
        self._refresh_image()

    # --- Menu actions ----------------------------------------------------
    def _open_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Open TIFF/OME-TIFF files",
            str(pathlib.Path.cwd()),
            "TIFF Files (*.tif *.tiff *.ome.tif *.ome.tiff)",
        )
        if not paths:
            return
        for p in paths:
            meta = _read_metadata(pathlib.Path(p))
            meta.id = len(self.images)
            self.images.append(meta)
            self.annotations[meta.id] = []
            self.fov_list.addItem(meta.name)
            self.primary_combo.addItem(meta.name)
            self.support_combo.addItem(meta.name)
        self._refresh_image()

    def _open_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open folder")
        if not folder:
            return
        folder_path = pathlib.Path(folder)
        candidates = sorted(
            [p for p in folder_path.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")]
        )
        if not candidates:
            return
        for p in candidates:
            meta = _read_metadata(p)
            meta.id = len(self.images)
            self.images.append(meta)
            self.annotations[meta.id] = []
            self.fov_list.addItem(meta.name)
            self.primary_combo.addItem(meta.name)
            self.support_combo.addItem(meta.name)
        self._refresh_image()

    def _load_annotations(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load annotations (CSV/JSON)", str(pathlib.Path.cwd()), "CSV/JSON Files (*.csv *.json)"
        )
        if not path:
            return
        path_obj = pathlib.Path(path)
        if path_obj.suffix.lower() == ".csv":
            kps = keypoints_from_csv(path_obj)
        else:
            kps = keypoints_from_json(path_obj)
        for kp in kps:
            match = next((img for img in self.images if img.name == kp.image_name), None)
            if match:
                kp.image_id = match.id
                self.annotations.setdefault(match.id, []).append(kp)
        self._refresh_image()

    def _toggle_profile_panel(self) -> None:
        self.profile_chk.setChecked(not self.profile_chk.isChecked())
        self._refresh_image()

    def _toggle_hist_panel(self) -> None:
        self.hist_chk.setChecked(not self.hist_chk.isChecked())
        self._refresh_image()

    def _toggle_left_pane(self) -> None:
        if self.left_panel.isVisible():
            self._left_sizes = self.top_splitter.sizes()
            self.left_panel.setVisible(False)
            self.top_splitter.setSizes([0, max(self._left_sizes[1] if self._left_sizes else 1, 1)])
        else:
            self.left_panel.setVisible(True)
            if self._left_sizes:
                self.top_splitter.setSizes(self._left_sizes)
            self.top_splitter.setStretchFactor(0, 0)
            self.top_splitter.setStretchFactor(1, 4)

    def _toggle_settings_pane(self) -> None:
        visible = not self.settings_advanced_container.isVisible()
        self.settings_advanced_container.setVisible(visible)
        self.toggle_settings_act.setChecked(visible)

    def _on_link_zoom_menu(self) -> None:
        self.link_zoom = self.link_zoom_act.isChecked()
        if not self.link_zoom:
            # reset last linked to avoid forcing 0-1 ranges
            self._last_zoom_linked = None
        self._refresh_image()

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "About Phage Annotator",
            "Phage Annotator\nMatplotlib + Qt GUI for microscopy keypoint annotation.\nFive synchronized panels, ROI, autoplay, lazy loading.",
        )

    def _show_profile_dialog(self) -> None:
        """Open a dialog showing line profiles (vertical, horizontal, diagonals) raw vs corrected."""
        if self.primary_image.array is None:
            return
        data = self._apply_crop(self._slice_data(self.primary_image))
        h, w = data.shape
        cy, cx = h // 2, w // 2
        vertical = data[:, cx]
        horizontal = data[cy, :]
        diag1 = np.diag(data)
        diag2 = np.diag(np.fliplr(data))

        def _correct(arr: np.ndarray) -> np.ndarray:
            if self.illum_corr_chk.isChecked():
                arr = arr - arr.min()
            if arr.max() > 0:
                arr = arr / arr.max()
            return arr

        fig, axes = plt.subplots(2, 2, figsize=(10, 6))
        axes = axes.ravel()
        for ax, arr, title in [
            (axes[0], vertical, "Vertical"),
            (axes[1], horizontal, "Horizontal"),
            (axes[2], diag1, "Diag TL-BR"),
            (axes[3], diag2, "Diag TR-BL"),
        ]:
            ax.plot(arr, label="raw")
            ax.plot(_correct(arr), label="corrected")
            ax.set_title(title)
            ax.legend()
            ax.set_xlabel("Pixel")
            ax.set_ylabel("Intensity")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Line profiles")
        layout = QtWidgets.QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.resize(900, 600)
        dlg.show()
        dlg.exec()

    def _show_bleach_dialog(self) -> None:
        """Open a dialog showing ROI mean over T with exponential fit."""
        if self.primary_image.array is None:
            return
        arr = self.primary_image.array
        roi_mask = self._roi_mask(arr.shape[2:])
        means = []
        for t in range(arr.shape[0]):
            frame = self._apply_crop(arr[t, 0, :, :]) if arr.shape[1] == 1 else self._apply_crop(arr[t, 0, :, :])
            means.append(float(frame[roi_mask].mean()))
        xs = np.arange(len(means))

        def exp_decay(x, a, b, c):
            return a * np.exp(-b * x) + c

        try:
            popt, _ = curve_fit(exp_decay, xs, means, maxfev=10000)
            fit = exp_decay(xs, *popt)
            eq = f"y = {popt[0]:.3f}*exp(-{popt[1]:.3f}*x)+{popt[2]:.3f}"
        except Exception:
            fit = None
            eq = "fit failed"

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(xs, means, "o-", label="ROI mean")
        if fit is not None:
            ax.plot(xs, fit, "--", label=eq)
        ax.set_xlabel("Frame")
        ax.set_ylabel("Mean intensity")
        ax.set_title("ROI mean vs frame")
        ax.legend()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Bleaching analysis")
        layout = QtWidgets.QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.resize(800, 500)
        dlg.show()
        dlg.exec()

    def _show_table_dialog(self) -> None:
        """Open a dialog with a table of file names and ROI mean; allow CSV export."""
        progress = QtWidgets.QProgressDialog("Computing ROI means...", None, 0, 0, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        progress.show()
        QtWidgets.QApplication.processEvents()

        rows = []
        for img in self.images:
            if img.array is None:
                self._ensure_loaded(img.id)
            if img.array is None:
                continue
            # Apply crop then ROI mask on the cropped shape to avoid shape mismatch.
            frame = img.array[0, 0, :, :]
            frame_cropped = self._apply_crop(frame)
            roi = self._roi_mask(frame_cropped.shape)
            roi_vals = frame_cropped[roi]
            roi_mean = float(roi_vals.mean()) if roi_vals.size else float("nan")
            rows.append({"file": img.name, "roi_mean": roi_mean})

        progress.close()
        df = pd.DataFrame(rows)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("ROI mean table")
        layout = QtWidgets.QVBoxLayout(dlg)
        table = QtWidgets.QTableWidget(len(df), 2)
        table.setHorizontalHeaderLabels(["File", "ROI mean"])
        for i, row in df.iterrows():
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(row["file"])))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{row['roi_mean']:.3f}"))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        export_btn = QtWidgets.QPushButton("Export CSV")
        layout.addWidget(export_btn)

        def _export():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export ROI means", str(pathlib.Path.cwd() / "roi_means.csv"), "CSV Files (*.csv)")
            if path:
                df.to_csv(path, index=False)

        export_btn.clicked.connect(_export)
        dlg.resize(500, 300)
        dlg.show()
        dlg.exec()

    # --- Controls handlers -----------------------------------------------
    def _set_fov(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.images):
            return
        self.current_image_idx = idx
        self.primary_combo.setCurrentIndex(idx)
        self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
        self._refresh_image()

    def _set_primary_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.current_image_idx = idx
            self.fov_list.setCurrentRow(idx)
            self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
            self._refresh_image()

    def _set_support_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.support_image_idx = idx
            self._refresh_image()

    def _toggle_play(self, axis: str) -> None:
        if self.play_timer.isActive() and self.play_mode == axis:
            self.play_timer.stop()
            self.play_mode = None
            self._set_status("Stopped playback")
            return
        self.play_mode = axis
        interval_ms = int(1000 / max(1, self.speed_slider.value()))
        self.play_timer.start(interval_ms)
        self._set_status(f"Playing {axis.upper()} at {self.speed_slider.value()} fps")

    def _on_play_tick(self) -> None:
        if self.play_mode == "t":
            max_val = self.t_slider.maximum()
            if self.t_slider.value() >= max_val:
                if self.loop_chk.isChecked():
                    self.t_slider.setValue(0)
                else:
                    self.play_timer.stop()
                    self.play_mode = None
                return
            self.t_slider.setValue(self.t_slider.value() + 1)
        elif self.play_mode == "z":
            max_val = self.z_slider.maximum()
            if self.z_slider.value() >= max_val:
                if self.loop_chk.isChecked():
                    self.z_slider.setValue(0)
                else:
                    self.play_timer.stop()
                    self.play_mode = None
                return
            self.z_slider.setValue(self.z_slider.value() + 1)

    def _on_loop_change(self) -> None:
        self.loop_playback = self.loop_chk.isChecked()

    def _on_axis_mode_change(self, mode: str) -> None:
        self.primary_image.interpret_3d_as = mode
        # Force reload for current primary to honor new interpretation.
        self.primary_image.array = None
        self._refresh_image()

    def _on_vminmax_change(self) -> None:
        if self.vmin_slider.value() > self.vmax_slider.value():
            self.vmax_slider.setValue(self.vmin_slider.value())
        self._refresh_image()

    def _current_vmin_vmax(self) -> Tuple[float, float]:
        prim = self.primary_image
        if prim.array is None:
            return 0.0, 1.0
        vmin = float(np.percentile(prim.array, self.vmin_slider.value()))
        vmax = float(np.percentile(prim.array, self.vmax_slider.value()))
        if vmin > vmax:
            vmin, vmax = vmax, vmin
        self.vmin_label.setText(f"vmin: {vmin:.3f}")
        self.vmax_label.setText(f"vmax: {vmax:.3f}")
        return vmin, vmax

    def _on_cmap_change(self, button, checked: bool) -> None:
        if checked:
            self.current_cmap_idx = COLORMAPS.index(button.text())
            self._refresh_image()

    def _on_label_change(self, button, checked: bool) -> None:
        if checked:
            self.current_label = button.text()
            self._update_status()

    def _on_scope_change(self) -> None:
        self.annotation_scope = "current" if self.scope_group.buttons()[0].isChecked() else "all"

    def _on_target_change(self) -> None:
        buttons = self.target_group.buttons()
        if buttons[0].isChecked():
            self.annotate_target = "frame"
        elif buttons[1].isChecked():
            self.annotate_target = "mean"
        elif buttons[2].isChecked():
            self.annotate_target = "comp"
        else:
            self.annotate_target = "support"

    def _on_marker_size_change(self, val: int) -> None:
        self.marker_size = val
        self._refresh_image()

    def _on_click_radius_change(self, val: float) -> None:
        self.click_radius_px = float(val)

    def _on_profile_mode(self) -> None:
        if not self.profile_mode_chk.isChecked():
            self.profile_line = None
        self._refresh_image()

    def _clear_profile(self) -> None:
        self.profile_line = None
        self.profile_mode_chk.setChecked(False)
        self._refresh_image()

    def _on_hist_region(self) -> None:
        btns = self.hist_region_group.buttons()
        self.hist_region = "roi" if btns[0].isChecked() else "full"
        self._refresh_image()

    def _on_limits_changed(self, ax) -> None:
        if ax not in {self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std}:
            return
        if self._suppress_limits:
            return
        if self.link_zoom:
            self._last_zoom_linked = (ax.get_xlim(), ax.get_ylim())
            # shared axes handle propagation automatically

    def _on_link_zoom_menu(self) -> None:
        self.link_zoom = self.link_zoom_act.isChecked()
        self._refresh_image()

    # --- Table and status -----------------------------------------------
    def _populate_table(self) -> None:
        self._block_table = True
        pts = self._current_keypoints()
        t_sel, z_sel = self.t_slider.value(), self.z_slider.value()
        if self.filter_current_chk.isChecked():
            pts = [kp for kp in pts if kp.t in (t_sel, -1) and kp.z in (z_sel, -1)]
        self._table_rows = pts
        self.annot_table.setRowCount(len(pts))
        for row, kp in enumerate(pts):
            for col, val in enumerate([kp.t, kp.z, kp.y, kp.x, kp.label]):
                item = QtWidgets.QTableWidgetItem(str(val))
                self.annot_table.setItem(row, col, item)
        self.annot_table.resizeColumnsToContents()
        self._block_table = False

    def _on_table_selection(self) -> None:
        self._refresh_image()

    def _on_table_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._block_table:
            return
        row, col = item.row(), item.column()
        if not (0 <= row < len(self._table_rows)):
            return
        kp = self._table_rows[row]
        text = item.text()
        try:
            if col == 0:
                kp.t = int(text)
            elif col == 1:
                kp.z = int(text)
            elif col == 2:
                kp.y = float(text)
            elif col == 3:
                kp.x = float(text)
            elif col == 4:
                kp.label = text
        except ValueError:
            return
        # Persist edits back to master annotations list
        pts = self.annotations.get(self.primary_image.id, [])
        try:
            master_idx = pts.index(kp)
            pts[master_idx] = kp
        except ValueError:
            pass
        self._refresh_image()

    def _update_status(self) -> None:
        total = sum(len(v) for v in self.annotations.values())
        current = len(self._current_keypoints())
        self._set_status(
            f"Label: {self.current_label} | Current slice pts: {current} | Total pts: {total} | Speed {self.speed_slider.value()} fps"
        )

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def _label_color(self, label: str, faded: bool = False) -> str:
        palette = {
            "phage": "#1f77b4",
            "artifact": "#d62728",
            "other": "#2ca02c",
        }
        color = palette.get(label, "#9467bd")
        if faded:
            return matplotlib.colors.to_hex(matplotlib.colors.to_rgba(color, alpha=0.4))
        return color

    def _point_in_roi(self, x: float, y: float) -> bool:
        rx, ry, rw, rh = self.roi_rect
        if self.roi_shape == "box":
            return (rx <= x <= rx + rw) and (ry <= y <= ry + rh)
        cx, cy = rx + rw / 2, ry + rh / 2
        r = min(rw, rh) / 2
        return (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2

    def _current_keypoints(self) -> List[Keypoint]:
        return self.annotations.get(self.primary_image.id, [])

    def _restore_zoom(self, data_shape: Tuple[int, int]) -> None:
        """Restore zoom using shared axes; defaults to full extent when none stored."""
        default_xlim = (0, data_shape[1])
        default_ylim = (data_shape[0], 0)
        if self.link_zoom:
            if self._last_zoom_linked is None:
                self._last_zoom_linked = (default_xlim, default_ylim)
            xlim, ylim = self._last_zoom_linked
            for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
        else:
            # independent zoom preserved by shared axes; fallback to defaults
            for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
                if ax.get_xlim() == (0.0, 1.0) or ax.get_ylim() == (0.0, 1.0):
                    ax.set_xlim(default_xlim)
                    ax.set_ylim(default_ylim)

    def _capture_zoom_state(self) -> None:
        """Capture current zoom from frame axis to preserve during redraws/playback."""
        xlim, ylim = self.ax_frame.get_xlim(), self.ax_frame.get_ylim()
        if self._valid_zoom(xlim, ylim):
            self._last_zoom_linked = (xlim, ylim)

    @staticmethod
    def _valid_zoom(xlim: Tuple[float, float], ylim: Tuple[float, float]) -> bool:
        return abs(xlim[1] - xlim[0]) > 1 and abs(ylim[1] - ylim[0]) > 1

    # --- Export ----------------------------------------------------------
    def _save_csv(self) -> None:
        csv_path, _ = self._default_export_paths()
        all_points = list(itertools.chain.from_iterable(self.annotations.values()))
        save_keypoints_csv(all_points, csv_path)
        self._set_status(f"Saved CSV to {csv_path}")

    def _save_json(self) -> None:
        _, json_path = self._default_export_paths()
        all_points = list(itertools.chain.from_iterable(self.annotations.values()))
        save_keypoints_json(all_points, json_path)
        self._set_status(f"Saved JSON to {json_path}")

    def _default_export_paths(self) -> Tuple[pathlib.Path, pathlib.Path]:
        first = self.primary_image.path
        csv_path = first.with_suffix(".annotations.csv")
        json_path = first.with_suffix(".annotations.json")
        return csv_path, json_path


def run_gui(image_paths: List[pathlib.Path]) -> None:
    """Launch the Qt keypoint GUI for one or more TIFF/OME-TIFF stacks."""
    win = create_app([pathlib.Path(p) for p in image_paths])
    win.show()
    QtWidgets.QApplication.instance().exec()


def create_app(image_paths: List[pathlib.Path]) -> KeypointAnnotator:
    """Create the Qt application and main window without starting the event loop."""
    if not matplotlib.get_backend().lower().startswith("qt"):
        matplotlib.use("Qt5Agg", force=True)
    metas = [_read_metadata(p) for p in image_paths]
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _ = app
    win = KeypointAnnotator(metas)
    return win
