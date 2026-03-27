"""Canvas and table workspace builders for the main UI."""

from __future__ import annotations

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.ui_qt.utils.constants import DEFAULT_PLAYBACK_FPS
from phage_annotator.ui_qt.widgets.modality_canvas import ModalityCanvasManager
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, cmap_for
from phage_annotator.rendering.mpl import Renderer


def build_annotation_table_panel(owner) -> QtWidgets.QWidget:
    """Build the annotation table side panel."""
    headers = [
        "ID",
        "Label",
        "T",
        "Z",
        "X",
        "Y",
        "Source",
        "Status",
        "Confidence",
        "Candidate Class",
        "ROI",
        "Notes",
        "Actions",
    ]
    owner.annot_table = QtWidgets.QTableWidget(0, len(headers))
    owner.annot_table.setStyleSheet(
        "QTableWidget { border: 1px solid #d0d0d0; alternate-background-color: #f8f8f8; }"
        "QTableWidget::item { padding: 2px; border-right: 1px solid #e8e8e8; }"
    )
    owner.annot_table.setHorizontalHeaderLabels(headers)
    owner.annot_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    owner.annot_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers)
    owner.annot_table.setSortingEnabled(True)
    owner.annot_table.setAlternatingRowColors(True)
    owner.filter_current_chk = QtWidgets.QCheckBox("Show current slice only")
    owner.auto_follow_table_chk = QtWidgets.QCheckBox("Auto-follow T/Z")
    owner.auto_follow_table_chk.setChecked(
        bool(owner._settings.value("annotationTableAutoFollow", True, type=bool))
    )
    if owner.auto_follow_table_chk.isChecked():
        owner.filter_current_chk.setChecked(True)
    owner.annotation_table_panel = QtWidgets.QWidget()
    owner.annotation_table_panel.setStyleSheet(
        "QWidget { border: 1px solid #d8d8d8; border-radius: 3px; background: #fafafa; }"
    )
    annot_layout = QtWidgets.QVBoxLayout(owner.annotation_table_panel)
    annot_layout.setContentsMargins(8, 8, 8, 8)
    annot_layout.setSpacing(8)
    owner.review_queue_hint_lbl = None
    owner.annotation_table_mode_combo = QtWidgets.QComboBox()
    owner.annotation_table_mode_combo.addItem("Truth mode", "truth")
    owner.annotation_table_mode_combo.addItem("Review mode", "review")
    owner.annotation_table_source_filter = QtWidgets.QComboBox()
    owner.annotation_table_source_filter.addItem("All sources", "all")
    owner.annotation_table_status_filter = QtWidgets.QComboBox()
    owner.annotation_table_status_filter.addItem("All status", "all")
    owner.annotation_table_candidate_filter = QtWidgets.QComboBox()
    owner.annotation_table_candidate_filter.addItem("All classes", "all")
    owner.annotation_table_roi_filter = QtWidgets.QComboBox()
    owner.annotation_table_roi_filter.addItem("All ROI / frame", "all")
    table_filter_row = QtWidgets.QHBoxLayout()
    table_filter_row.addWidget(owner.annotation_table_mode_combo)
    table_filter_row.addWidget(owner.filter_current_chk)
    table_filter_row.addWidget(owner.auto_follow_table_chk)
    table_filter_row.addStretch(1)
    annot_layout.addLayout(table_filter_row)
    review_filter_row = QtWidgets.QHBoxLayout()
    review_filter_row.addWidget(owner.annotation_table_source_filter, 1)
    review_filter_row.addWidget(owner.annotation_table_status_filter, 1)
    review_filter_row.addWidget(owner.annotation_table_candidate_filter, 1)
    review_filter_row.addWidget(owner.annotation_table_roi_filter, 1)
    annot_layout.addLayout(review_filter_row)
    annot_layout.addWidget(owner.annot_table)
    return owner.annotation_table_panel


def build_canvas_workspace(owner) -> tuple[QtWidgets.QWidget, QtWidgets.QWidget]:
    """Build the main figure area and playback bar."""
    fig_container = QtWidgets.QWidget()
    fig_container.setStyleSheet(
        "QWidget { border: 1px solid #c0c0c0; border-radius: 4px; background: #ffffff; }"
    )
    fig_layout = QtWidgets.QVBoxLayout(fig_container)
    fig_layout.setContentsMargins(8, 8, 8, 8)
    fig_layout.setSpacing(6)
    owner.modality_canvas = ModalityCanvasManager(parent=owner)
    owner.figure = owner.modality_canvas.figure
    owner.ax_frame = None
    owner.ax_mean = None
    owner.ax_comp = None
    owner.ax_support = None
    owner.ax_std = None
    owner.ax_line = None
    owner.ax_hist = None
    owner.canvas = owner.modality_canvas.canvas
    if owner.canvas is not None:
        owner.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        owner.canvas.updateGeometry()
    owner.toolbar = NavigationToolbar2QT(owner.canvas, owner) if owner.canvas is not None else None
    if owner.toolbar is not None:
        fig_layout.addWidget(owner.toolbar)
    owner.evidence_strip_lbl = QtWidgets.QLabel("Evidence: view=Frame | projection=Raw | modalities=default")
    owner.evidence_strip_lbl.setStyleSheet(
        "QLabel { background: #eef3f8; color: #1d3557; padding: 4px 8px; border-radius: 4px; }"
    )
    fig_layout.addWidget(owner.evidence_strip_lbl)
    fig_layout.addWidget(owner.modality_canvas, stretch=1)
    fallback_cmaps = [cmap_for(spec, False) for spec in LUTS]
    owner.renderer = Renderer(owner.figure, owner.canvas, fallback_cmaps)
    owner.renderer.set_roi_callback(owner._on_roi_interactor_change)

    playback_bar = QtWidgets.QWidget()
    playback_bar.setStyleSheet(
        "QWidget { border-top: 2px solid #b8b8b8; background: #f9f9f9; border-radius: 3px; }"
    )
    playback_layout = QtWidgets.QGridLayout(playback_bar)
    playback_layout.setContentsMargins(6, 6, 6, 6)
    playback_layout.setSpacing(6)
    owner.t_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    owner.t_slider_label = QtWidgets.QLabel("T: 1")
    owner.t_slider.setSingleStep(1)
    owner.t_minus_button = QtWidgets.QPushButton("-")
    owner.t_plus_button = QtWidgets.QPushButton("+")
    owner.t_minus_button.setToolTip("Previous time frame")
    owner.t_plus_button.setToolTip("Next time frame")
    t_slider_box = QtWidgets.QHBoxLayout()
    t_slider_box.addWidget(owner.t_minus_button)
    t_slider_box.addWidget(owner.t_slider, stretch=1)
    t_slider_box.addWidget(owner.t_plus_button)
    owner.play_t_btn = QtWidgets.QPushButton("Play T")
    owner.z_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    owner.z_slider_label = QtWidgets.QLabel("Z: 1")
    owner.z_slider.setSingleStep(1)
    owner.z_minus_button = QtWidgets.QPushButton("-")
    owner.z_plus_button = QtWidgets.QPushButton("+")
    owner.z_minus_button.setToolTip("Previous Z plane")
    owner.z_plus_button.setToolTip("Next Z plane")
    z_slider_box = QtWidgets.QHBoxLayout()
    z_slider_box.addWidget(owner.z_minus_button)
    z_slider_box.addWidget(owner.z_slider, stretch=1)
    z_slider_box.addWidget(owner.z_plus_button)
    owner.play_z_btn = QtWidgets.QPushButton("Play Z")
    owner.speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    owner.speed_slider.setRange(1, DEFAULT_PLAYBACK_FPS)
    owner.speed_slider.setValue(DEFAULT_PLAYBACK_FPS)
    owner.speed_slider.setSingleStep(1)
    owner.speed_minus_button = QtWidgets.QPushButton("-")
    owner.speed_plus_button = QtWidgets.QPushButton("+")
    owner.speed_minus_button.setToolTip("Slow down playback")
    owner.speed_plus_button.setToolTip("Speed up playback")
    speed_slider_box = QtWidgets.QHBoxLayout()
    speed_slider_box.addWidget(owner.speed_minus_button)
    speed_slider_box.addWidget(owner.speed_slider, stretch=1)
    speed_slider_box.addWidget(owner.speed_plus_button)
    owner.loop_chk = QtWidgets.QCheckBox("Loop")
    playback_layout.addWidget(QtWidgets.QLabel("Time"), 0, 0)
    playback_layout.addWidget(owner.t_slider_label, 0, 1)
    playback_layout.addLayout(t_slider_box, 0, 2)
    playback_layout.addWidget(owner.play_t_btn, 0, 3)
    playback_layout.addWidget(QtWidgets.QLabel("Depth"), 1, 0)
    playback_layout.addWidget(owner.z_slider_label, 1, 1)
    playback_layout.addLayout(z_slider_box, 1, 2)
    playback_layout.addWidget(owner.play_z_btn, 1, 3)
    playback_layout.addWidget(QtWidgets.QLabel("Speed (fps)"), 2, 0)
    playback_layout.addLayout(speed_slider_box, 2, 2)
    playback_layout.addWidget(owner.loop_chk, 2, 3)
    owner.fps_label = QtWidgets.QLabel(f"FPS: {owner.speed_slider.value()}")
    playback_layout.addWidget(owner.fps_label, 2, 1)
    owner.sync_target_live_lbl = QtWidgets.QLabel("Sync target: Manual group")
    owner.sync_target_live_lbl.setStyleSheet("color: #455a64; font-style: italic;")
    playback_layout.addWidget(owner.sync_target_live_lbl, 3, 0, 1, 4)
    owner.sync_contract_live_lbl = QtWidgets.QLabel("Sync contract: Contrast, Zoom/Pan, Playback")
    owner.sync_contract_live_lbl.setStyleSheet("color: #546e7a;")
    playback_layout.addWidget(owner.sync_contract_live_lbl, 4, 0, 1, 4)
    owner.sync_panels_live_lbl = QtWidgets.QLabel("Sync panels: -")
    owner.sync_panels_live_lbl.setStyleSheet("color: #607d8b;")
    playback_layout.addWidget(owner.sync_panels_live_lbl, 5, 0, 1, 4)
    owner.sync_view_live_lbl = QtWidgets.QLabel("Sync view: -")
    owner.sync_view_live_lbl.setStyleSheet("color: #78909c;")
    playback_layout.addWidget(owner.sync_view_live_lbl, 6, 0, 1, 4)
    owner.sync_target_mode_combo = QtWidgets.QComboBox()
    owner.sync_target_mode_combo.addItem("Manual group", "manual")
    owner.sync_target_mode_combo.addItem("Active canvas group", "active")
    owner.sync_target_mode_combo.setCurrentIndex(0)
    owner.sync_target_mode_combo.setToolTip("Choose how sync target group is selected.")
    owner.sync_key_combo = QtWidgets.QComboBox()
    owner.sync_key_combo.addItem("Group 1", "1")
    owner.sync_key_combo.setEnabled(True)
    owner.sync_key_combo.setToolTip("Select numeric Sync Group key from Lazy Loading.")
    owner.sync_key_combo.setStyleSheet(
        "QComboBox { color: #000000; background-color: #ffffff; }"
        "QComboBox QAbstractItemView { color: #000000; background-color: #ffffff; "
        "selection-background-color: #0078d7; selection-color: #ffffff; }"
        "QComboBox QAbstractItemView::item:hover { color: #ffffff; background-color: #0078d7; }"
    )
    playback_layout.addWidget(QtWidgets.QLabel("Sync Target"), 7, 0)
    playback_layout.addWidget(owner.sync_target_mode_combo, 7, 1)
    playback_layout.addWidget(owner.sync_key_combo, 7, 2, 1, 2)
    return fig_container, playback_bar
