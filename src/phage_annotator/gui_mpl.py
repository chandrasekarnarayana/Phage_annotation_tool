"""Matplotlib + Qt keypoint annotation GUI for microscopy TIFF stacks.

Five synchronized panels (Frame, Mean, Composite, Support, Std) with ROI, autoplay, and
annotation tools. The layout uses splitters to prioritize the image panels while keeping
settings resizable. Images are loaded on demand to reduce memory usage; folders can be opened
to populate the FOV list without eager loading.
"""

from __future__ import annotations

import gc
import itertools
import pathlib
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tifffile as tif
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from PyQt5.QtWidgets import QSizePolicy
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
from phage_annotator.project_io import load_project, save_project

COLORMAPS = ["gray", "viridis", "magma", "plasma", "cividis"]
# Avoid pulling multi-GB TIFFs fully into RAM; switch to memmap beyond this.
BIG_TIFF_BYTES_THRESHOLD = 512 * 1024 * 1024  # 512 MB
# Toggle verbose cache logging for debugging (loading, projection caching, clearing).
DEBUG_CACHE = False
# Optional FPS overlay for playback diagnostics.
DEBUG_FPS = False
# Small ring buffer size for playback prefetch; trades memory vs latency.
PLAYBACK_BUFFER_SIZE = 5
# Only compute FPS every N frames to keep overhead small.
FPS_UPDATE_STRIDE = 5
# Target FPS for high-speed playback; speed slider sets the requested rate.
DEFAULT_PLAYBACK_FPS = 30

# Dev notes:
# - Sliders have +/- buttons, high-FPS playback uses a ring buffer + prefetch thread.
# - Undo/redo stacks record add/delete annotation actions (symmetry between forward/inverse).
# - Keyboard shortcuts: arrows for T/Z, space toggles Play T, Delete removes selected annotation,
#   R resets view+contrast, A/N prompt add guidance.
# - Reset view = zoom to full extent; reset contrast recomputes percentiles; reset_all does both.
# - Project files (.phageproj) store image paths + annotation paths + basic settings; see project_io.

# Dev notes:
# - Sliders now have +/- step buttons to mirror ImageJ-style nudge controls.
# - Large TIFFs are memmapped and projections are cached to emulate Fiji's virtual stack behavior.
# - See tests/stress_test_memory.py for a headless stress harness that exercises loading, navigation, and cache clearing.


def _debug_log(msg: str) -> None:
    if DEBUG_CACHE:
        print(msg)


@dataclass
class LazyImage:
    """Metadata and optional pixel data for an image.

    A LazyImage may hold the array in memory, be backed by a memmap, or have no
    array loaded at all (virtual). Mean/std projections are cached once
    computed to keep refreshes responsive.
    """

    path: pathlib.Path
    name: str
    shape: Tuple[int, ...]
    dtype: str
    has_time: bool
    has_z: bool
    array: Optional[np.ndarray] = None
    id: int = -1
    interpret_3d_as: str = "auto"
    mean_proj: Optional[np.ndarray] = None
    std_proj: Optional[np.ndarray] = None


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
    """
    Load image data and standardize to (T, Z, Y, X).

    Large stacks are memory-mapped to keep RAM usage manageable; smaller files
    are read eagerly for speed.
    """
    with tif.TiffFile(path) as tf:
        page = tf.series[0]
        shape = page.shape
        dtype = np.dtype(page.dtype)
        nbytes = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
    use_memmap = nbytes > BIG_TIFF_BYTES_THRESHOLD
    if use_memmap:
        _debug_log(f"Memmap loading {path} ({nbytes/1e6:.1f} MB)")
        arr = tif.memmap(str(path))
    else:
        _debug_log(f"Loading into memory {path} ({nbytes/1e6:.1f} MB)")
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
        self._last_folder: Optional[pathlib.Path] = None

        self._suppress_limits = False

        # Playback helpers (high-FPS path)
        self._playback_mode = False
        self._playback_buffer: Deque[np.ndarray] = deque()
        self._playback_buffer_indices: Deque[int] = deque()
        self._playback_buffer_lock = threading.Lock()
        self._playback_stop_event = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_buffer_size = PLAYBACK_BUFFER_SIZE
        self._playback_direction = 1
        self._playback_overlay_stride = 3
        self._playback_frame_counter = 0
        self._fps_times: Deque[float] = deque(maxlen=120)
        self._fps_text = None
        self._last_vmin = 0.0
        self._last_vmax = 1.0
        self._playback_cursor = 0
        self._last_frame_time: Optional[float] = None
        # Undo/redo stacks of annotation actions (add/delete).
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        # Panel visibility controls which axes exist; at least one must remain visible.
        self._panel_visibility = {"frame": True, "mean": True, "composite": True, "support": True, "std": True}
        # Skip the next zoom capture when layout is rebuilt to preserve previous zoom.
        self._skip_capture_once = False
        # Pixel size (um per pixel) for density calculations.
        self.pixel_size_um_per_px = 0.069
        self._status_base = ""
        self._status_extra = ""

        # Matplotlib image artists reused across refreshes to avoid recreation.
        self.im_frame = None
        self.im_mean = None
        self.im_comp = None
        self.im_support = None
        self.im_std = None

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
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            target_w = min(max(int(geom.width() * 0.9), 1200), geom.width())
            target_h = min(max(int(geom.height() * 0.9), 800), geom.height())
            self.resize(target_w, target_h)
        else:
            self.resize(1700, 1000)

        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        open_files_act = file_menu.addAction("Open files…")
        open_folder_act = file_menu.addAction("Open folder…")
        load_ann_act = file_menu.addAction("Load annotations…")
        save_csv_act = file_menu.addAction("Save annotations (CSV)")
        save_json_act = file_menu.addAction("Save annotations (JSON)")
        save_proj_act = file_menu.addAction("Save project…")
        load_proj_act = file_menu.addAction("Load project…")
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
        panels_menu = view_menu.addMenu("Panels")
        self.panel_actions = {}
        for key, label in [
            ("frame", "Show Frame"),
            ("mean", "Show Mean"),
            ("composite", "Show Composite"),
            ("support", "Show Support"),
            ("std", "Show STD"),
        ]:
            act = panels_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(True)
            act.toggled.connect(lambda checked, k=key: self._on_panel_toggle(k, checked))
            self.panel_actions[key] = act

        edit_menu = menubar.addMenu("&Edit")
        self.undo_act = edit_menu.addAction("Undo")
        self.redo_act = edit_menu.addAction("Redo")
        self.undo_act.setShortcut("Ctrl+Z")
        self.redo_act.setShortcut("Ctrl+Shift+Z")
        self.undo_act.setEnabled(False)
        self.redo_act.setEnabled(False)

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
        self.clear_fovs_btn = QtWidgets.QPushButton("Clear FOV list")
        left_layout.addWidget(self.clear_fovs_btn)

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
        self.ax_frame = None
        self.ax_mean = None
        self.ax_comp = None
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

        self.top_splitter.addWidget(fig_container)
        self.top_splitter.setStretchFactor(0, 0)
        self.top_splitter.setStretchFactor(1, 6)

        # Settings pane
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)

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

        self.vmin_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vmax_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vmin_slider.setRange(0, 100)
        self.vmax_slider.setRange(0, 100)
        self.vmin_slider.setValue(5)
        self.vmax_slider.setValue(95)
        self.vmin_slider.setSingleStep(1)
        self.vmax_slider.setSingleStep(1)
        self.vmin_slider.setPageStep(1)
        self.vmax_slider.setPageStep(1)
        self.vmin_slider.setTickInterval(1)
        self.vmax_slider.setTickInterval(1)
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
        primary_controls.addWidget(QtWidgets.QLabel("Vmin"), row, 0)
        primary_controls.addWidget(self.vmin_label, row, 1)
        primary_controls.addLayout(vmin_slider_box, row, 2)
        row += 1
        primary_controls.addWidget(QtWidgets.QLabel("Vmax"), row, 0)
        primary_controls.addWidget(self.vmax_label, row, 1)
        primary_controls.addLayout(vmax_slider_box, row, 2)
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
        self.clear_cache_btn = QtWidgets.QPushButton("Clear cache")
        adv_layout.addWidget(self.save_csv_btn, r, 0)
        adv_layout.addWidget(self.save_json_btn, r, 1)
        adv_layout.addWidget(self.clear_cache_btn, r, 2)

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
        save_proj_act.triggered.connect(self._save_project)
        load_proj_act.triggered.connect(self._load_project)
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
        self.undo_act.triggered.connect(self.undo_last_action)
        self.redo_act.triggered.connect(self.redo_last_action)
        self._rebuild_figure_layout()

    # --- Events and data helpers ----------------------------------------
    def _bind_events(self) -> None:
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("key_press_event", self._on_key)
        self._bind_axis_callbacks()

        self.prev_btn = None  # kept for compatibility; buttons are managed in menu now

        self.fov_list.currentRowChanged.connect(self._set_fov)
        self.primary_combo.currentIndexChanged.connect(self._set_primary_combo)
        self.support_combo.currentIndexChanged.connect(self._set_support_combo)
        self.t_slider.valueChanged.connect(self._refresh_image)
        self.z_slider.valueChanged.connect(self._refresh_image)
        self.t_minus_button.clicked.connect(lambda: self._step_slider(self.t_slider, -1))
        self.t_plus_button.clicked.connect(lambda: self._step_slider(self.t_slider, 1))
        self.z_minus_button.clicked.connect(lambda: self._step_slider(self.z_slider, -1))
        self.z_plus_button.clicked.connect(lambda: self._step_slider(self.z_slider, 1))
        self.speed_minus_button.clicked.connect(lambda: self._step_slider(self.speed_slider, -1))
        self.speed_plus_button.clicked.connect(lambda: self._step_slider(self.speed_slider, 1))
        self.play_t_btn.clicked.connect(lambda: self._toggle_play("t"))
        self.play_z_btn.clicked.connect(lambda: self._toggle_play("z"))
        self.play_timer.timeout.connect(self._on_play_tick)
        self.speed_slider.valueChanged.connect(self._update_status)
        self.loop_chk.stateChanged.connect(self._on_loop_change)
        self.axis_mode_combo.currentTextChanged.connect(self._on_axis_mode_change)
        self.vmin_slider.valueChanged.connect(self._on_vminmax_change)
        self.vmax_slider.valueChanged.connect(self._on_vminmax_change)
        self.vmin_minus_button.clicked.connect(lambda: self._step_slider(self.vmin_slider, -1))
        self.vmin_plus_button.clicked.connect(lambda: self._step_slider(self.vmin_slider, 1))
        self.vmax_minus_button.clicked.connect(lambda: self._step_slider(self.vmax_slider, -1))
        self.vmax_plus_button.clicked.connect(lambda: self._step_slider(self.vmax_slider, 1))
        self.cmap_group.buttonToggled.connect(self._on_cmap_change)
        self.label_group.buttonToggled.connect(self._on_label_change)
        self.scope_group.buttonToggled.connect(self._on_scope_change)
        self.target_group.buttonToggled.connect(self._on_target_change)
        self.reset_view_btn.clicked.connect(self.reset_all_view)
        self.pixel_size_spin.valueChanged.connect(self._on_pixel_size_change)
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
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.filter_current_chk.stateChanged.connect(self._populate_table)
        self.crop_reset_btn.clicked.connect(self._reset_crop)
        self.crop_x_spin.valueChanged.connect(self._on_crop_change)
        self.crop_y_spin.valueChanged.connect(self._on_crop_change)
        self.crop_w_spin.valueChanged.connect(self._on_crop_change)
        self.crop_h_spin.valueChanged.connect(self._on_crop_change)
        self.annot_table.itemSelectionChanged.connect(self._on_table_selection)
        self.annot_table.itemChanged.connect(self._on_table_item_changed)
        self.show_ann_master_chk.stateChanged.connect(self._refresh_image)
        self.clear_fovs_btn.clicked.connect(self._clear_fov_list)

    def _bind_axis_callbacks(self) -> None:
        """Bind zoom callbacks for current axes to keep zoom synced."""
        axes = [ax for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std] if ax is not None]
        for ax in axes:
            ax.callbacks.connect("xlim_changed", self._on_limits_changed)
            ax.callbacks.connect("ylim_changed", self._on_limits_changed)

    def reset_view(self) -> None:
        """Reset zoom/pan to full extent of current frame."""
        self._last_zoom_linked = None
        for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
            if ax is None:
                continue
            ax.set_xlim(auto=True)
            ax.set_ylim(auto=True)
        self._refresh_image()

    def reset_contrast(self) -> None:
        """Reset vmin/vmax to default percentiles of the primary image."""
        prim = self.primary_image
        if prim.array is None:
            self.vmin_slider.setValue(5)
            self.vmax_slider.setValue(95)
            return
        vmin = float(np.percentile(prim.array, 5))
        vmax = float(np.percentile(prim.array, 95))
        self._last_vmin, self._last_vmax = vmin, vmax
        self.vmin_slider.setValue(5)
        self.vmax_slider.setValue(95)
        self.vmin_label.setText(f"vmin: {vmin:.3f}")
        self.vmax_label.setText(f"vmax: {vmax:.3f}")
        self._refresh_image()

    def reset_all_view(self) -> None:
        """Reset zoom and contrast (ImageJ-like reset)."""
        self.reset_contrast()
        self.reset_view()

    def _on_key(self, event) -> None:
        """Handle keyboard shortcuts for reset zoom, colormap cycle, and quick-save."""
        if event.key == "r":
            self.reset_all_view()
        elif event.key == "c":
            self.current_cmap_idx = (self.current_cmap_idx + 1) % len(COLORMAPS)
            self._refresh_image()
        elif event.key == "s":
            self._quick_save_csv()

    def keyPressEvent(self, event) -> None:
        """Qt-level shortcuts for fast navigation; ignored when editing text fields."""
        focused = QtWidgets.QApplication.focusWidget()
        if isinstance(focused, (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)):
            return super().keyPressEvent(event)
        key = event.key()
        if key == QtCore.Qt.Key_Left:
            self._step_slider(self.t_slider, -1)
        elif key == QtCore.Qt.Key_Right:
            self._step_slider(self.t_slider, 1)
        elif key == QtCore.Qt.Key_Up:
            self._step_slider(self.z_slider, -1)
        elif key == QtCore.Qt.Key_Down:
            self._step_slider(self.z_slider, 1)
        elif key == QtCore.Qt.Key_Space:
            self._toggle_play("t")
        elif key in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            self._delete_selected_annotations()
        elif key in (QtCore.Qt.Key_A, QtCore.Qt.Key_N):
            self._set_status("Click on the image to add an annotation point.")
        elif key == QtCore.Qt.Key_R:
            self.reset_all_view()
        else:
            super().keyPressEvent(event)

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
            img.mean_proj = None
            img.std_proj = None
            _debug_log(f"Loaded image {img.name} (id={img.id})")
        # Drop others to save memory (keep primary and support)
        for j, other in enumerate(self.images):
            if j not in (self.current_image_idx, self.support_image_idx):
                self._evict_image_cache(other)

    def _evict_image_cache(self, img: LazyImage) -> None:
        """Remove array and projection caches for an image to free memory."""
        if img.array is not None or img.mean_proj is not None or img.std_proj is not None:
            _debug_log(f"Evicting cache for {img.name} (id={img.id})")
        img.array = None
        img.mean_proj = None
        img.std_proj = None

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
        if img.array is not None:
            t_idx = max(0, min(t_idx, img.array.shape[0] - 1))
            z_idx = max(0, min(z_idx, img.array.shape[1] - 1))
        return t_idx, z_idx

    def _slice_data(self, img: LazyImage, t_override: Optional[int] = None, z_override: Optional[int] = None) -> np.ndarray:
        t_idx, z_idx = self._slice_indices(img)
        if t_override is not None:
            t_idx = max(0, t_override if img.array is None else min(t_override, img.array.shape[0] - 1))
        if z_override is not None:
            z_idx = max(0, z_override if img.array is None else min(z_override, img.array.shape[1] - 1))
        assert img.array is not None
        return img.array[t_idx, z_idx, :, :]

    def _ensure_projections(self, img: LazyImage) -> None:
        """
        Compute and cache mean/std projections for an image.

        Projections are taken over (T, Z) axes in float32. Cache is invalidated
        when the image array is evicted from memory.
        """
        if img.mean_proj is not None and img.std_proj is not None:
            return
        if img.array is None:
            self._ensure_loaded(img.id)
        if img.array is None:
            return
        if img.mean_proj is None:
            img.mean_proj = img.array.mean(axis=(0, 1)).astype(np.float32, copy=False)
            _debug_log(f"Computed mean projection for {img.name}")
        if img.std_proj is None:
            img.std_proj = img.array.std(axis=(0, 1)).astype(np.float32, copy=False)
            _debug_log(f"Computed std projection for {img.name}")

    def _projection(self, img: LazyImage) -> np.ndarray:
        self._ensure_projections(img)
        assert img.mean_proj is not None
        return img.mean_proj

    def _std_projection(self, img: LazyImage) -> np.ndarray:
        self._ensure_projections(img)
        assert img.std_proj is not None
        return img.std_proj

    def _update_image_artist(self, artist, data: np.ndarray, cmap: str, vmin: float, vmax: float) -> None:
        """Reuse an AxesImage instead of recreating it for every refresh."""
        artist.set_data(data)
        artist.set_cmap(cmap)
        artist.set_clim(vmin, vmax)
        artist.set_extent((0, data.shape[1], data.shape[0], 0))

    def _clear_image_overlays(self) -> None:
        """Clear scatter/ROI overlays while keeping base images intact."""
        for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std]:
            if ax is None:
                continue
            # Matplotlib ArtistList inconsistencies: fall back to manual removal.
            for artist in list(ax.patches):
                artist.remove()
            for artist in list(ax.lines):
                artist.remove()
            # Keep the image artist (AxesImage) but remove other collections (e.g., scatter).
            for artist in list(ax.collections):
                if artist is getattr(self, "im_frame", None):
                    continue
                if artist is getattr(self, "im_mean", None):
                    continue
                if artist is getattr(self, "im_comp", None):
                    continue
                if artist is getattr(self, "im_support", None):
                    continue
                if artist is getattr(self, "im_std", None):
                    continue
                artist.remove()

    # --- High-FPS playback helpers --------------------------------------
    def start_playback_t(self, fps: Optional[int] = None) -> None:
        """Start high-FPS playback along the time axis with prefetch buffer."""
        self._ensure_loaded(self.current_image_idx)
        # Heavy refresh once to ensure artists/vmin/vmax exist.
        if self.im_frame is None:
            self._refresh_image()
        self._playback_mode = True
        self.play_mode = "t"
        self._playback_stop_event.clear()
        with self._playback_buffer_lock:
            self._playback_buffer.clear()
            self._playback_buffer_indices.clear()
        if fps is None:
            fps = max(1, int(self.speed_slider.value()))
        self._playback_direction = 1
        self._playback_cursor = self.t_slider.value()
        self._playback_frame_counter = 0
        self._last_frame_time = None
        self._start_playback_thread()
        interval_ms = int(1000 / max(1, fps))
        self.play_timer.setInterval(interval_ms)
        self.play_timer.start()
        self._set_status(f"Playing T at {fps} fps (buffer {self._playback_buffer_size})")

    def stop_playback_t(self) -> None:
        """Stop playback and return to interactive mode."""
        if not self._playback_mode:
            return
        self._playback_mode = False
        self.play_mode = None
        self.play_timer.stop()
        self._playback_stop_event.set()
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=0.2)
        self._playback_thread = None
        with self._playback_buffer_lock:
            self._playback_buffer.clear()
            self._playback_buffer_indices.clear()
        self._fps_times.clear()
        self._set_status("Stopped playback")
        self._refresh_image()

    def _start_playback_thread(self) -> None:
        if self._playback_thread and self._playback_thread.is_alive():
            return
        self._playback_stop_event.clear()
        self._playback_thread = threading.Thread(target=self._playback_prefetch, daemon=True)
        self._playback_thread.start()

    def _playback_prefetch(self) -> None:
        """Background loader that keeps a small buffer of frames ready."""
        while not self._playback_stop_event.is_set():
            prim = self.primary_image
            if prim.array is None:
                time.sleep(0.005)
                continue
            t_max = prim.array.shape[0] - 1
            z_idx = self._slice_indices(prim)[1]
            with self._playback_buffer_lock:
                if len(self._playback_buffer) >= self._playback_buffer_size:
                    pass
                else:
                    t_idx = self._playback_cursor
                    # Pure slicing path to avoid copies; returns a view on memmap.
                    frame_view = prim.array[t_idx, z_idx, :, :]
                    frame_view = self._apply_crop(frame_view)
                    if DEBUG_FPS and frame_view.base is None:
                        _debug_log("Playback frame copy detected (crop may have forced a copy)")
                    self._playback_buffer.append(frame_view)
                    self._playback_buffer_indices.append(t_idx)
                    self._playback_cursor = t_idx + self._playback_direction
                    if self._playback_cursor > t_max:
                        if self.loop_chk.isChecked():
                            self._playback_cursor = 0
                        else:
                            self._playback_cursor = t_max
                            self._playback_stop_event.set()
            time.sleep(0.002)

    def _playback_tick(self) -> None:
        """Called from timer; display the next prefetched frame if available."""
        if not self._playback_mode:
            return
        frame = None
        t_idx = None
        with self._playback_buffer_lock:
            if self._playback_buffer:
                frame = self._playback_buffer.popleft()
                t_idx = self._playback_buffer_indices.popleft()
        if frame is None or t_idx is None:
            if self._playback_stop_event.is_set():
                self.stop_playback_t()
            return
        self._update_frame_only(frame, t_idx)

    def _update_frame_only(self, frame: np.ndarray, t_idx: int) -> None:
        """Lightweight per-frame update for playback without recomputing projections."""
        if self.im_frame is None:
            self._refresh_image()
        if self.im_frame is None or self.ax_frame is None:
            return
        self.im_frame.set_data(frame)
        self.im_frame.set_clim(self._last_vmin, self._last_vmax)
        # Update support panel in sync (clamped to its own length).
        if self.im_support is not None and self.ax_support is not None and self.support_image.array is not None:
            support_slice = self._apply_crop(self._slice_data(self.support_image, t_override=t_idx))
            self._update_image_artist(self.im_support, support_slice, COLORMAPS[self.current_cmap_idx], self._last_vmin, self._last_vmax)
        prim = self.primary_image
        t_max = prim.array.shape[0] if prim.array is not None else 0
        # Title update is cheap but skip every few frames to reduce churn.
        if self._playback_frame_counter % FPS_UPDATE_STRIDE == 0:
            self.ax_frame.set_title(f"Frame (T {t_idx+1}/{t_max})")
        # Keep slider in sync without triggering heavy refresh.
        self.t_slider.blockSignals(True)
        self.t_slider.setValue(t_idx)
        self.t_slider.blockSignals(False)
        self.t_slider_label.setText(f"T: {t_idx + 1}/{t_max}")
        now = time.perf_counter()
        if self._last_frame_time is not None:
            self._fps_times.append(now - self._last_frame_time)
        self._last_frame_time = now
        self._playback_frame_counter += 1
        if DEBUG_FPS and (self._playback_frame_counter % FPS_UPDATE_STRIDE == 0):
            self._update_fps_meter()
        self.canvas.draw_idle()

    def _update_fps_meter(self) -> None:
        if not self._fps_times:
            return
        fps = 1.0 / (sum(self._fps_times) / len(self._fps_times))
        if self._fps_text is None:
            self._fps_text = self.ax_frame.text(
                0.98, 0.02, f"FPS: {fps:.1f}", color="yellow", ha="right", va="bottom", transform=self.ax_frame.transAxes
            )
        else:
            self._fps_text.set_text(f"FPS: {fps:.1f}")
        self._set_status(f"FPS ~ {fps:.1f}")
    def _step_slider(self, slider: QtWidgets.QSlider, direction: int) -> None:
        """Nudge a slider by its single step, clamped to bounds."""
        step = slider.singleStep() or 1
        target = slider.value() + direction * step
        target = max(slider.minimum(), min(slider.maximum(), target))
        slider.setValue(target)

    # --- Rendering -------------------------------------------------------
    def _refresh_image(self) -> None:
        # Preserve current zoom before redraw
        if self._skip_capture_once:
            self._skip_capture_once = False
        else:
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

        # Auto-contrast std projection based on its own data (zoomed/cropped region).
        std_vmin = float(np.percentile(std_data, self.vmin_slider.value()))
        std_vmax = float(np.percentile(std_data, self.vmax_slider.value()))
        if std_vmin >= std_vmax:
            std_vmax = std_vmin + 1e-3

        titles = [
            (self.ax_frame, f"Frame (T {self.t_slider.value()+1}/{t_max+1})"),
            (self.ax_mean, "Mean IMG"),
            (self.ax_comp, "Composite / GT IMG"),
            (self.ax_support, "Support (epi)"),
            (self.ax_std, "STD IMG"),
        ]
        for ax, title in titles:
            if ax is not None:
                ax.set_title(title)

        if self.im_frame is None and self.ax_frame is not None:
            self.im_frame = self.ax_frame.imshow(slice_data, cmap=cmap, vmin=vmin, vmax=vmax)
        elif self.im_frame is not None:
            self._update_image_artist(self.im_frame, slice_data, cmap, vmin, vmax)

        if self.im_mean is None and self.ax_mean is not None:
            self.im_mean = self.ax_mean.imshow(mean_data, cmap=cmap, vmin=vmin, vmax=vmax)
        elif self.im_mean is not None:
            self._update_image_artist(self.im_mean, mean_data, cmap, vmin, vmax)

        if self.im_comp is None and self.ax_comp is not None:
            self.im_comp = self.ax_comp.imshow(mean_data, cmap=cmap, vmin=vmin, vmax=vmax)
        elif self.im_comp is not None:
            self._update_image_artist(self.im_comp, mean_data, cmap, vmin, vmax)

        if self.im_support is None and self.ax_support is not None:
            self.im_support = self.ax_support.imshow(support_slice, cmap=cmap, vmin=vmin, vmax=vmax)
        elif self.im_support is not None:
            self._update_image_artist(self.im_support, support_slice, cmap, vmin, vmax)

        if self.im_std is None and self.ax_std is not None:
            self.im_std = self.ax_std.imshow(std_data, cmap=cmap, vmin=std_vmin, vmax=std_vmax)
        elif self.im_std is not None:
            self._update_image_artist(self.im_std, std_data, cmap, std_vmin, std_vmax)

        self._clear_image_overlays()
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
            if ax is None:
                continue
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
            if ax is None:
                return
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
                if ax is None:
                    continue
                ys = [kp.y for kp in selected_pts]
                xs = [kp.x for kp in selected_pts]
                ax.scatter(xs, ys, c="red", s=self.marker_size * 1.3, marker="o", edgecolors="k")
        # Refresh status to reflect view density after drawing points.
        self._update_status()

    def _draw_diagnostics(self, slice_data: np.ndarray, vmin: float, vmax: float) -> None:
        if self.profile_enabled and self.profile_chk.isChecked() and self.ax_line is not None:
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
            if self.ax_line is not None:
                self.ax_line.clear()
                self.ax_line.axis("off")

        if self.hist_enabled and self.hist_chk.isChecked() and self.ax_hist is not None:
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
            if self.ax_hist is not None:
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

    def _on_panel_toggle(self, key: str, checked: bool) -> None:
        """Toggle panel visibility; ensure at least one panel stays on."""
        # Capture current zoom before layout rebuild so we can restore it.
        self._capture_zoom_state()
        self._panel_visibility[key] = checked
        if not any(self._panel_visibility.values()):
            # Prevent hiding all; re-enable the current key.
            self._panel_visibility[key] = True
            self.panel_actions[key].setChecked(True)
            return
        self._skip_capture_once = True
        self._rebuild_figure_layout()
        # Re-render content on the new layout so remaining panels show current data.
        self._refresh_image()

    def _panel_grid_shape(self, n: int) -> Tuple[int, int]:
        """Map number of visible panels to a compact grid."""
        if n <= 1:
            return 1, 1
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        return rows, cols

    def _rebuild_figure_layout(self) -> None:
        """
        Recreate axes based on visible panels (images + diagnostics) so remaining panels grow.

        Called at init and when panel visibility toggles; avoids touching playback/memmap logic.
        """
        ordered = ["frame", "mean", "composite", "support", "std"]
        visible_images = [p for p in ordered if self._panel_visibility.get(p, False)]
        diag_panels = []
        if getattr(self, "profile_chk", None) is None or getattr(self, "hist_chk", None) is None:
            # During early init, default to showing diagnostics.
            diag_panels = ["line", "hist"]
        else:
            if self.profile_chk.isChecked():
                diag_panels.append("line")
            if self.hist_chk.isChecked():
                diag_panels.append("hist")
        if not visible_images and not diag_panels:
            return
        # Images occupy the first row in a single row; diagnostics go to a second row.
        img_cols = max(1, len(visible_images))
        diag_cols = len(diag_panels)
        nrows = 1 + (1 if diag_panels else 0)
        ncols = max(img_cols, diag_cols if diag_cols else img_cols)
        self.figure.clear()
        self.figure.set_constrained_layout(True)
        gs = self.figure.add_gridspec(nrows, ncols)
        # Reset axes references
        self.ax_frame = self.ax_mean = self.ax_comp = self.ax_support = self.ax_std = None
        self.ax_line = self.ax_hist = None
        ax_map = {}
        base_ax = None
        for idx, panel in enumerate(visible_images):
            r, c = 0, idx  # first row only
            # Share axes with first visible panel to keep zoom/pan synced.
            share_ax = base_ax if panel in visible_images else None
            ax = self.figure.add_subplot(gs[r, c], sharex=share_ax, sharey=share_ax)
            if panel in visible_images and base_ax is None:
                base_ax = ax
            ax.set_aspect("auto")
            ax_map[panel] = ax
        # Diagnostics on second row, no sharing needed.
        for idx, panel in enumerate(diag_panels):
            ax = self.figure.add_subplot(gs[1, idx])
            ax.set_aspect("auto")
            if panel == "line":
                self.ax_line = ax
            elif panel == "hist":
                self.ax_hist = ax
        self.ax_frame = ax_map.get("frame")
        self.ax_mean = ax_map.get("mean")
        self.ax_comp = ax_map.get("composite")
        self.ax_support = ax_map.get("support")
        self.ax_std = ax_map.get("std")
        self.ax_blank = None
        # Reset image artists; they will be recreated on next refresh
        self.im_frame = self.im_mean = self.im_comp = self.im_support = self.im_std = None
        self._bind_axis_callbacks()
        self.canvas.draw_idle()

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
        self._push_undo({"type": "add_point", "point": pts[-1], "image_id": image_id})
        self._update_status()

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
                removed = pts.pop(idx)
                self._push_undo({"type": "delete_point", "point": removed, "image_id": removed.image_id})
                self._update_status()
                return True
        return False

    def _push_undo(self, action: dict) -> None:
        """Record an action and clear redo stack."""
        self._undo_stack.append(action)
        self._redo_stack.clear()
        self.undo_act.setEnabled(bool(self._undo_stack))
        self.redo_act.setEnabled(bool(self._redo_stack))

    def undo_last_action(self) -> None:
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        inverse = self._apply_action(action, undo=True)
        if inverse:
            self._redo_stack.append(inverse)
        self.undo_act.setEnabled(bool(self._undo_stack))
        self.redo_act.setEnabled(bool(self._redo_stack))
        self._refresh_image()

    def redo_last_action(self) -> None:
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        inverse = self._apply_action(action, undo=False)
        if inverse:
            self._undo_stack.append(inverse)
        self.undo_act.setEnabled(bool(self._undo_stack))
        self.redo_act.setEnabled(bool(self._redo_stack))
        self._refresh_image()

    def _apply_action(self, action: dict, undo: bool) -> Optional[dict]:
        """
        Apply an action and return the inverse action for redo/undo symmetry.

        Supported types:
          - add_point: point => remove on undo; inverse is delete_point.
          - delete_point: point => add on undo; inverse is add_point.
        """
        atype = action.get("type")
        point: Keypoint = action.get("point")
        image_id = action.get("image_id")
        if atype == "add_point":
            if undo:
                self._remove_point(point, image_id)
                return {"type": "delete_point", "point": point, "image_id": image_id}
            else:
                self.annotations.setdefault(image_id, []).append(point)
                return {"type": "add_point", "point": point, "image_id": image_id}
        if atype == "delete_point":
            if undo:
                self.annotations.setdefault(image_id, []).append(point)
                return {"type": "add_point", "point": point, "image_id": image_id}
            else:
                self._remove_point(point, image_id)
                return {"type": "delete_point", "point": point, "image_id": image_id}
        return None

    def _remove_point(self, point: Keypoint, image_id: int) -> None:
        pts = self.annotations.get(image_id, [])
        try:
            pts.remove(point)
        except ValueError:
            pass

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
        self.stop_playback_t()
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Open TIFF/OME-TIFF files",
            str(pathlib.Path.cwd()),
            "TIFF Files (*.tif *.tiff *.ome.tif *.ome.tiff)",
        )
        if not paths:
            return
        # Remember folder of last open
        self._last_folder = pathlib.Path(paths[0]).parent
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
        self.stop_playback_t()
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open folder")
        if not folder:
            return
        folder_path = pathlib.Path(folder)
        self._last_folder = folder_path
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
        self._rebuild_figure_layout()
        self._refresh_image()

    def _toggle_hist_panel(self) -> None:
        self.hist_chk.setChecked(not self.hist_chk.isChecked())
        self._rebuild_figure_layout()
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
        # Apply crop first, then build ROI mask on the cropped shape.
        means = []
        for t in range(arr.shape[0]):
            frame = self._apply_crop(arr[t, 0, :, :])
            roi_mask = self._roi_mask(frame.shape)
            roi_vals = frame[roi_mask]
            means.append(float(roi_vals.mean()) if roi_vals.size else float("nan"))
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
        # Prefer last opened folder; otherwise use currently loaded images.
        candidates: List[pathlib.Path] = []
        if self._last_folder and self._last_folder.exists():
            candidates = sorted(
                [p for p in self._last_folder.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")]
            )
        if not candidates:
            candidates = [img.path for img in self.images]

        for p in candidates:
            roi_mean = self._compute_roi_mean_for_path(p)
            rows.append({"file": p.name, "roi_mean": roi_mean})

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
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export ROI means", str(pathlib.Path.cwd() / "roi_means.csv"), "CSV Files (*.csv)"
            )
            if path:
                df.to_csv(path, index=False)

        export_btn.clicked.connect(_export)
        dlg.resize(500, 300)
        dlg.show()
        dlg.exec()

    def _compute_roi_mean_for_path(self, path: pathlib.Path) -> float:
        """Compute ROI mean for the given TIFF path with minimal memory use."""
        try:
            arr = tif.imread(str(path), maxworkers=1)
            std, _, _ = standardize_axes(arr)
            frame = std[0, 0, :, :]
            frame_cropped = self._apply_crop(frame)
            roi = self._roi_mask(frame_cropped.shape)
            vals = frame_cropped[roi]
            return float(vals.mean()) if vals.size else float("nan")
        except Exception:
            return float("nan")

    def _clear_cache(self) -> None:
        """Clear all lazy image data (arrays + projections) and refresh the view."""
        self.stop_playback_t()
        cleared = 0
        for img in self.images:
            if img.array is not None or img.mean_proj is not None or img.std_proj is not None:
                cleared += 1
            self._evict_image_cache(img)
        gc.collect()
        _debug_log(f"Cleared cached data for {cleared} images")
        self._set_status(f"Cleared cached image data for {cleared} images.")
        # Will lazily reload the active images after purge.
        self._refresh_image()

    def _clear_fov_list(self) -> None:
        """Remove all FOVs except the current primary to reset the list."""
        if not self.images:
            return
        self.stop_playback_t()
        keep_idx = self.current_image_idx
        keep_img = self.images[keep_idx]
        self.images = [keep_img]
        self.annotations = {keep_img.id: self.annotations.get(keep_img.id, [])}
        self.fov_list.clear()
        self.primary_combo.clear()
        self.support_combo.clear()
        keep_img.id = 0
        self.fov_list.addItem(keep_img.name)
        self.primary_combo.addItem(keep_img.name)
        self.support_combo.addItem(keep_img.name)
        self.current_image_idx = 0
        self.support_image_idx = 0
        self._set_status("Cleared FOV list; kept current image.")
        self._refresh_image()

    # --- Controls handlers -----------------------------------------------
    def _set_fov(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.images):
            return
        self.stop_playback_t()
        self.current_image_idx = idx
        self.primary_combo.setCurrentIndex(idx)
        self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
        self._refresh_image()

    def _set_primary_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self.current_image_idx = idx
            self.fov_list.setCurrentRow(idx)
            self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
            self._refresh_image()

    def _set_support_combo(self, idx: int) -> None:
        if 0 <= idx < len(self.images):
            self.stop_playback_t()
            self.support_image_idx = idx
            self._refresh_image()

    def _toggle_play(self, axis: str) -> None:
        if axis == "t":
            if self._playback_mode:
                self.stop_playback_t()
            else:
                self.start_playback_t(fps=self.speed_slider.value())
            return
        # legacy Z playback uses the existing lightweight timer stepping
        if self.play_timer.isActive() and self.play_mode == axis:
            self.play_timer.stop()
            self.play_mode = None
            self._set_status("Stopped playback")
            return
        self.stop_playback_t()
        self.play_mode = axis
        interval_ms = int(1000 / max(1, self.speed_slider.value()))
        self.play_timer.start(interval_ms)
        self._set_status(f"Playing {axis.upper()} at {self.speed_slider.value()} fps")

    def _on_play_tick(self) -> None:
        if self._playback_mode and self.play_mode == "t":
            self._playback_tick()
            return
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
        self.stop_playback_t()
        self.primary_image.interpret_3d_as = mode
        # Force reload for current primary to honor new interpretation.
        self._evict_image_cache(self.primary_image)
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
        self._last_vmin, self._last_vmax = vmin, vmax
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

    def _on_pixel_size_change(self, val: float) -> None:
        self.pixel_size_um_per_px = float(val)
        self._update_status()

    def _on_limits_changed(self, ax) -> None:
        if ax not in {self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std}:
            return
        if self._suppress_limits:
            return
        if self.link_zoom:
            self._last_zoom_linked = (ax.get_xlim(), ax.get_ylim())
        self._update_status()
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

    def _delete_selected_annotations(self) -> None:
        """Delete selected rows from the annotation table."""
        rows = sorted({idx.row() for idx in self.annot_table.selectionModel().selectedRows()}) if self.annot_table.selectionModel() else []
        if not rows or not self._table_rows:
            return
        removed_any = False
        for row in reversed(rows):
            if 0 <= row < len(self._table_rows):
                kp = self._table_rows[row]
                self._remove_point(kp, kp.image_id)
                self._push_undo({"type": "delete_point", "point": kp, "image_id": kp.image_id})
                removed_any = True
        if removed_any:
            self._refresh_image()
            self._update_status()

    def _update_status(self) -> None:
        total = sum(len(v) for v in self.annotations.values())
        current = len(self._current_keypoints())
        density_txt = ""
        pts_view, area_um2 = self._view_density_stats()
        if area_um2 > 0:
            density = pts_view / area_um2 if area_um2 > 0 else 0.0
            density_txt = f" | View pts: {pts_view} | Area: {area_um2:.2f} um^2 | Density: {density:.3f} /um^2"
        self._status_base = (
            f"Label: {self.current_label} | Current slice pts: {current} | Total pts: {total} | Speed {self.speed_slider.value()} fps{density_txt}"
        )
        self._render_status()

    def _set_status(self, text: str) -> None:
        """Set a transient status message; base status persists during playback."""
        self._status_extra = text
        self._render_status()

    def _render_status(self) -> None:
        if self._status_extra:
            self.status.setText(f"{self._status_base} | {self._status_extra}")
        else:
            self.status.setText(self._status_base)

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

    def _view_density_stats(self) -> Tuple[int, float]:
        """Compute number of points and area (um^2) in current view extent."""
        axes = [ax for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std] if ax is not None]
        if not axes:
            return 0, 0.0
        xlim, ylim = axes[0].get_xlim(), axes[0].get_ylim()
        # Limit density area to ROI if set, otherwise use current view extents.
        circle_mode = self.roi_shape == "circle"
        circle_center = None
        circle_r = None
        if self.roi_rect and self.roi_rect[2] > 0 and self.roi_rect[3] > 0:
            rx, ry, rw, rh = self.roi_rect
            x0, x1 = max(min(xlim), rx), min(max(xlim), rx + rw)
            y0, y1 = max(min(ylim), ry), min(max(ylim), ry + rh)
            width_px = max(0, x1 - x0)
            height_px = max(0, y1 - y0)
            x_bounds = (x0, x1)
            y_bounds = (y0, y1)
            if circle_mode:
                circle_center = (rx + rw / 2, ry + rh / 2)
                circle_r = min(rw, rh) / 2
        else:
            width_px = abs(xlim[1] - xlim[0])
            height_px = abs(ylim[1] - ylim[0])
            x_bounds = xlim
            y_bounds = ylim
        area_px = width_px * height_px
        # If circle ROI is partially in view, approximate overlap area via sampling.
        if circle_mode and circle_center is not None and width_px > 0 and height_px > 0:
            cx, cy = circle_center
            # If view contains full circle bounding box, use exact circle area.
            full_contained = (
                x_bounds[0] <= cx - circle_r
                and x_bounds[1] >= cx + circle_r
                and y_bounds[0] <= cy - circle_r
                and y_bounds[1] >= cy + circle_r
            )
            if full_contained:
                area_px = np.pi * (circle_r ** 2)
            else:
                # Sample overlap rectangle to estimate circular overlap fraction.
                nx = max(1, min(256, int(width_px)))
                ny = max(1, min(256, int(height_px)))
                xs = np.linspace(x_bounds[0], x_bounds[1], nx)
                ys = np.linspace(y_bounds[0], y_bounds[1], ny)
                xx, yy = np.meshgrid(xs, ys)
                inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= circle_r ** 2
                frac = inside.mean()
                area_px = area_px * frac
        area_um2 = area_px * (self.pixel_size_um_per_px ** 2)
        t_sel, z_sel = self.t_slider.value(), self.z_slider.value()
        def _inside_circle(kp_x: float, kp_y: float) -> bool:
            if not circle_mode or circle_center is None or circle_r is None:
                return True
            cx, cy = circle_center
            return (kp_x - cx) ** 2 + (kp_y - cy) ** 2 <= circle_r ** 2
        pts = [
            kp
            for kp in self._current_keypoints()
            if kp.t in (t_sel, -1)
            and kp.z in (z_sel, -1)
            and x_bounds[0] <= kp.x <= x_bounds[1]
            and y_bounds[0] <= kp.y <= y_bounds[1]
            and _inside_circle(kp.x, kp.y)
        ]
        return len(pts), area_um2

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
        axes = [ax for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std] if ax is not None]
        if not axes:
            return
        if self.link_zoom:
            if self._last_zoom_linked is None:
                self._last_zoom_linked = (default_xlim, default_ylim)
            xlim, ylim = self._last_zoom_linked
            for ax in axes:
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
        else:
            # independent zoom preserved by shared axes; fallback to defaults
            for ax in axes:
                if ax.get_xlim() == (0.0, 1.0) or ax.get_ylim() == (0.0, 1.0):
                    ax.set_xlim(default_xlim)
                    ax.set_ylim(default_ylim)

    def _capture_zoom_state(self) -> None:
        """Capture current zoom from frame axis to preserve during redraws/playback."""
        anchor_axes = [ax for ax in [self.ax_frame, self.ax_mean, self.ax_comp, self.ax_support, self.ax_std] if ax is not None]
        if not anchor_axes:
            return
        xlim, ylim = anchor_axes[0].get_xlim(), anchor_axes[0].get_ylim()
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

    def _save_project(self) -> None:
        """Persist a lightweight project (.phageproj) with images + annotation paths + settings."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save project", str(pathlib.Path.cwd() / "session.phageproj"), "Phage project (*.phageproj)"
        )
        if not path:
            return
        settings = {
            "fps_default": int(self.speed_slider.value()),
            "lut": COLORMAPS[self.current_cmap_idx],
            "last_fov_index": self.current_image_idx,
            "last_support_index": self.support_image_idx,
        }
        save_project(pathlib.Path(path), self.images, self.annotations, settings)
        self._set_status(f"Saved project to {path}")

    def _load_project(self) -> None:
        """Load a .phageproj and rebuild images/annotations minimally."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load project", str(pathlib.Path.cwd()), "Phage project (*.phageproj)"
        )
        if not path:
            return
        try:
            image_entries, settings, ann_map = load_project(pathlib.Path(path))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Load project failed", str(exc))
            return
        self.stop_playback_t()
        self.images.clear()
        self.annotations.clear()
        self.fov_list.clear()
        self.primary_combo.clear()
        self.support_combo.clear()
        for idx, entry in enumerate(image_entries):
            meta = _read_metadata(pathlib.Path(entry["path"]))
            meta.id = idx
            self.images.append(meta)
            self.annotations[idx] = []
            self.fov_list.addItem(meta.name)
            self.primary_combo.addItem(meta.name)
            self.support_combo.addItem(meta.name)
        for idx, ann_path in ann_map.items():
            if ann_path.exists():
                kps = keypoints_from_json(ann_path)
                for kp in kps:
                    kp.image_id = idx
                    self.annotations[idx].append(kp)
        self.current_image_idx = int(settings.get("last_fov_index", 0))
        self.support_image_idx = int(settings.get("last_support_index", min(1, len(self.images) - 1)))
        self.fov_list.setCurrentRow(self.current_image_idx)
        self.primary_combo.setCurrentIndex(self.current_image_idx)
        self.support_combo.setCurrentIndex(self.support_image_idx)
        lut = settings.get("lut")
        if lut in COLORMAPS:
            self.current_cmap_idx = COLORMAPS.index(lut)
        self.speed_slider.setValue(int(settings.get("fps_default", self.speed_slider.value())))
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.undo_act.setEnabled(False)
        self.redo_act.setEnabled(False)
        self._refresh_image()


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
