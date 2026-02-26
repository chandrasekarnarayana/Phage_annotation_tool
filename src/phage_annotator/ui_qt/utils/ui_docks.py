"""Dock/panel wiring helpers for the main window."""

from __future__ import annotations

from typing import List, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.roi.widgets import RoiManagerWidget
from phage_annotator.ui_qt.panels.analyze_particles_panel import AnalyzeParticlesPanel
from phage_annotator.ui_qt.panels.density_panel import DensityPanel
from phage_annotator.ui_qt.panels.recorder_legacy import RecorderWidget
from phage_annotator.ui_qt.panels.registry_legacy import PanelSpec
from phage_annotator.ui_qt.docks.metadata_dock import MetadataDock
from phage_annotator.ui_qt.widgets.table_legacy import ResultsTableWidget
from phage_annotator.ui_qt.widgets.orthoview import OrthoViewWidget
# performance_panel moved to ui_qt PerformancePanel
from phage_annotator.smlm.ui import SmlmPanel
# threshold_panel moved to ui_qt ThresholdPanel


def init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
    """Create dock widgets and corresponding View menu actions."""
    self.panel_specs = build_panel_registry(self)
    self.panel_docks.clear()
    self.dock_actions.clear()

    for spec in self.panel_specs:
        widget = spec.widget_factory()
        dock = create_dock(self, spec.id, spec.title, widget)
        if spec.id == "annotations":
            dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.panel_docks[spec.id] = dock
        self.addDockWidget(spec.default_area, dock)
        action = dock_menu.addAction(spec.toggle_action_text)
        action.setCheckable(True)
        action.setChecked(spec.default_visible)
        if spec.shortcut:
            action.setShortcut(spec.shortcut)
        self.dock_actions[spec.id] = action
        # Some checkboxes are created by panel factories, so guard lookup here.
        checkbox = None
        if spec.id == "hist":
            checkbox = getattr(self, "hist_chk", None)
        elif spec.id == "profile":
            checkbox = getattr(self, "profile_chk", None)
        wire_dock_action(self, dock, action, checkbox)
        dock.setVisible(spec.default_visible)

    self.dock_sidebar = self.panel_docks.get("sidebar")
    self.dock_annotations = self.panel_docks.get("annotations")
    self.dock_roi = self.panel_docks.get("roi")
    self.dock_roi_manager = self.panel_docks.get("roi_manager")
    self.dock_results = self.panel_docks.get("results")
    self.dock_hist = self.panel_docks.get("hist")
    self.dock_profile = self.panel_docks.get("profile")
    self.dock_orthoview = self.panel_docks.get("orthoview")
    self.dock_smlm = self.panel_docks.get("smlm")
    self.dock_threshold = self.panel_docks.get("threshold")
    self.dock_particles = self.panel_docks.get("particles")
    self.dock_logs = self.panel_docks.get("logs")
    self.dock_recorder = self.panel_docks.get("recorder")
    self.dock_metadata = self.panel_docks.get("metadata")
    self.dock_density = self.panel_docks.get("density")
    self.dock_performance = self.panel_docks.get("performance")

    if self.dock_hist and self.dock_profile:
        self.tabifyDockWidget(self.dock_hist, self.dock_profile)
    if self.dock_roi and self.dock_roi_manager:
        self.tabifyDockWidget(self.dock_roi, self.dock_roi_manager)
    if self.dock_roi and self.dock_results:
        self.tabifyDockWidget(self.dock_roi, self.dock_results)
    if self.dock_roi and self.dock_orthoview:
        self.tabifyDockWidget(self.dock_roi, self.dock_orthoview)
    if self.dock_roi and self.dock_metadata:
        self.tabifyDockWidget(self.dock_roi, self.dock_metadata)
    if self.dock_smlm is not None:
        self.dock_smlm.setFloating(True)
        self.dock_smlm.setVisible(False)
    if self.dock_orthoview is not None:
        self.dock_orthoview.setFloating(True)
        self.dock_orthoview.setVisible(False)
    if self.dock_metadata is not None:
        self.dock_metadata.visibilityChanged.connect(self._on_metadata_dock_visibility)

    self.view_overlay_act.triggered.connect(self._toggle_overlay)
    self.reset_layout_act.triggered.connect(self._reset_layout)
    self.save_layout_default_act.triggered.connect(self._save_layout_default)
    self.preset_annotate_act.triggered.connect(lambda: self.apply_preset("Annotate"))
    self.preset_analyze_act.triggered.connect(lambda: self.apply_preset("Analyze"))
    self.preset_minimal_act.triggered.connect(lambda: self.apply_preset("Minimal"))
    self.preset_default_act.triggered.connect(lambda: self.apply_preset("Default"))
    apply_panel_defaults(self)
    self._restore_sidebar_mode()


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
        ),
        PanelSpec(
            id="annotations",
            title="Annotation Table",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_annotations_widget,
            toggle_action_text="Annotation Table",
        ),
        PanelSpec(
            id="roi",
            title="ROI Controls",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,  # Hidden by default, opened from ROI/Crop panel
            widget_factory=self._make_roi_widget,
            toggle_action_text="ROI Controls",
        ),
        PanelSpec(
            id="roi_manager",
            title="ROI Manager",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_roi_manager_widget,
            toggle_action_text="ROI Manager",
        ),
        PanelSpec(
            id="results",
            title="Results",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_results_widget,
            toggle_action_text="Results",
        ),
        PanelSpec(
            id="recorder",
            title="Recorder",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_recorder_widget,
            toggle_action_text="Recorder",
        ),
        PanelSpec(
            id="hist",
            title="Histogram",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,  # Hidden by default per Task G
            widget_factory=self._make_hist_widget,
            toggle_action_text="Histogram",
        ),
        PanelSpec(
            id="profile",
            title="Line Profile",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,  # Hidden by default per Task G
            widget_factory=self._make_profile_widget,
            toggle_action_text="Line Profile",
        ),
        PanelSpec(
            id="orthoview",
            title="Ortho Views",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_orthoview_widget,
            toggle_action_text="Ortho Views",
        ),
        PanelSpec(
            id="smlm",
            title="SMLM (ROI)",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_smlm_widget,
            toggle_action_text="SMLM (ROI)",
        ),
        PanelSpec(
            id="threshold",
            title="Threshold",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_threshold_widget,
            toggle_action_text="Threshold",
        ),
        PanelSpec(
            id="particles",
            title="Analyze Particles",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_particles_widget,
            toggle_action_text="Analyze Particles",
        ),
        PanelSpec(
            id="density",
            title="Density",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_density_widget,
            toggle_action_text="Density",
        ),
        PanelSpec(
            id="logs",
            title="Diagnostics",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_logs_widget,
            toggle_action_text="Diagnostics",
        ),
        PanelSpec(
            id="metadata",
            title="Metadata",
            default_area=QtCore.Qt.LeftDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_metadata_widget,
            toggle_action_text="Metadata",
        ),
        PanelSpec(
            id="performance",
            title="Performance",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_performance_widget,
            toggle_action_text="Performance Monitor",
        ),
    ]


def apply_panel_defaults(self) -> None:
    """Reset dock placement/visibility using PanelSpec defaults."""
    for spec in self.panel_specs:
        dock = self.panel_docks.get(spec.id)
        if dock is None:
            continue
        self.addDockWidget(spec.default_area, dock)
        dock.setVisible(spec.default_visible)
    if self.panel_docks.get("hist") and self.panel_docks.get("profile"):
        self.tabifyDockWidget(self.panel_docks["hist"], self.panel_docks["profile"])


def create_dock(self, name: str, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QDockWidget:
    """Create a standard dock widget with common features enabled."""
    dock = QtWidgets.QDockWidget(title, self)
    dock.setObjectName(name)
    dock.setWidget(widget)
    dock.setFeatures(
        QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
    return dock


def wire_dock_action(
    self,
    dock: QtWidgets.QDockWidget,
    action: QtWidgets.QAction,
    checkbox: Optional[QtWidgets.QCheckBox] = None,
) -> None:
    """Keep dock visibility, menu toggle, and optional checkbox in sync."""

    def _set_visible(checked: bool) -> None:
        dock.setVisible(checked)

    def _sync_action(visible: bool) -> None:
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
        if checkbox is not None:
            checkbox.blockSignals(True)
            checkbox.setChecked(visible)
            checkbox.blockSignals(False)
            self._refresh_image()

    action.toggled.connect(_set_visible)
    dock.visibilityChanged.connect(_sync_action)


def make_sidebar_widget(self) -> QtWidgets.QWidget:
    return self._build_sidebar_stack()


def make_annotations_widget(self) -> QtWidgets.QWidget:
    return self.annotation_table_panel


def make_roi_widget(self) -> QtWidgets.QWidget:
    roi_widget = QtWidgets.QWidget()
    roi_layout = QtWidgets.QVBoxLayout(roi_widget)
    roi_layout.setContentsMargins(8, 8, 8, 8)
    roi_layout.setSpacing(8)
    roi_layout.addWidget(QtWidgets.QLabel("ROI (X, Y, W, H)"))
    if self._roi_controls_layout is not None:
        roi_layout.addLayout(self._roi_controls_layout)
    return roi_widget


def make_roi_manager_widget(self) -> QtWidgets.QWidget:
    widget = RoiManagerWidget(self.roi_manager, parent=self)
    self.roi_manager_widget = widget
    return widget


def make_results_widget(self) -> QtWidgets.QWidget:
    widget = ResultsTableWidget(parent=self)
    self.results_widget = widget
    return widget


def make_recorder_widget(self) -> QtWidgets.QWidget:
    widget = RecorderWidget(self.recorder, parent=self)
    self.recorder_widget = widget
    return widget


def make_hist_widget(self) -> QtWidgets.QWidget:
    if self.hist_canvas is None:
        self.hist_fig = plt.figure(figsize=(4, 3))
        self.hist_canvas = FigureCanvasQTAgg(self.hist_fig)
        self.ax_hist = self.hist_fig.add_subplot(111)
    hist_container = QtWidgets.QWidget()
    hist_layout = QtWidgets.QVBoxLayout(hist_container)
    hist_layout.setContentsMargins(8, 8, 8, 8)
    hist_layout.setSpacing(6)
    controls = QtWidgets.QHBoxLayout()
    self.hist_chk = QtWidgets.QCheckBox("Histogram")
    self.hist_chk.setChecked(True)
    self.show_hist_chk = self.hist_chk
    self.hist_bins_spin = QtWidgets.QSpinBox()
    self.hist_bins_spin.setRange(16, 512)
    self.hist_bins_spin.setValue(self.hist_bins)
    self.hist_region_combo = QtWidgets.QComboBox()
    self.hist_region_combo.addItems(["Full image", "ROI", "Crop area"])
    if self.hist_region == "roi":
        self.hist_region_combo.setCurrentText("ROI")
    elif self.hist_region == "crop":
        self.hist_region_combo.setCurrentText("Crop area")
    else:
        self.hist_region_combo.setCurrentText("Full image")
    self.hist_scope_combo = QtWidgets.QComboBox()
    self.hist_scope_combo.addItems(["Current slice", "Sampled stack"])
    self.hist_scope_combo.setCurrentText(self._hist_scope_mode)
    controls.addWidget(self.hist_chk)
    controls.addWidget(QtWidgets.QLabel("Bins"))
    controls.addWidget(self.hist_bins_spin)
    controls.addWidget(self.hist_region_combo)
    controls.addWidget(self.hist_scope_combo)
    controls.addStretch(1)
    hist_layout.addLayout(controls)
    hist_layout.addWidget(self.hist_canvas)
    bc_group = QtWidgets.QGroupBox("B&C")
    bc_layout = QtWidgets.QGridLayout(bc_group)
    bc_layout.setContentsMargins(6, 6, 6, 6)
    bc_layout.setSpacing(6)

    self.bc_preview = QtWidgets.QLabel()
    self.bc_preview.setFixedHeight(60)
    self.bc_preview.setMinimumWidth(140)
    self.bc_preview.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )
    bc_layout.addWidget(self.bc_preview, 0, 0, 1, 3)

    self.bc_min_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_max_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_min_spin = QtWidgets.QDoubleSpinBox()
    self.bc_max_spin = QtWidgets.QDoubleSpinBox()
    for spin in (self.bc_min_spin, self.bc_max_spin):
        spin.setDecimals(3)
        spin.setSingleStep(1.0)
        spin.setKeyboardTracking(False)
    bc_layout.addWidget(QtWidgets.QLabel("Minimum"), 1, 0)
    bc_layout.addWidget(self.bc_min_spin, 1, 1)
    bc_layout.addWidget(self.bc_min_slider, 1, 2)
    bc_layout.addWidget(QtWidgets.QLabel("Maximum"), 2, 0)
    bc_layout.addWidget(self.bc_max_spin, 2, 1)
    bc_layout.addWidget(self.bc_max_slider, 2, 2)

    self.bc_brightness_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_brightness_slider.setRange(-100, 100)
    self.bc_brightness_slider.setValue(0)
    self.bc_contrast_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self.bc_contrast_slider.setRange(-100, 100)
    self.bc_contrast_slider.setValue(0)
    bc_layout.addWidget(QtWidgets.QLabel("Brightness"), 3, 0)
    bc_layout.addWidget(self.bc_brightness_slider, 3, 1, 1, 2)
    bc_layout.addWidget(QtWidgets.QLabel("Contrast"), 4, 0)
    bc_layout.addWidget(self.bc_contrast_slider, 4, 1, 1, 2)

    bc_btns = QtWidgets.QHBoxLayout()
    self.bc_auto_btn = QtWidgets.QPushButton("Auto")
    self.bc_reset_btn = QtWidgets.QPushButton("Reset")
    self.bc_set_btn = QtWidgets.QPushButton("Set")
    self.bc_apply_btn = QtWidgets.QPushButton("Apply")
    bc_btns.addWidget(self.bc_auto_btn)
    bc_btns.addWidget(self.bc_reset_btn)
    bc_btns.addWidget(self.bc_set_btn)
    bc_btns.addWidget(self.bc_apply_btn)
    bc_layout.addLayout(bc_btns, 5, 0, 1, 3)

    hist_layout.addWidget(bc_group)
    return hist_container


def make_profile_widget(self) -> QtWidgets.QWidget:
    """Create the profile (line-plot) widget and checkbox."""
    if self.profile_canvas is None:
        self.profile_fig = plt.figure(figsize=(4, 3))
        self.profile_canvas = FigureCanvasQTAgg(self.profile_fig)
        self.ax_line = self.profile_fig.add_subplot(111)
    profile_container = QtWidgets.QWidget()
    profile_layout = QtWidgets.QVBoxLayout(profile_container)
    profile_layout.setContentsMargins(8, 8, 8, 8)
    profile_layout.setSpacing(6)
    controls = QtWidgets.QHBoxLayout()
    self.profile_chk = QtWidgets.QCheckBox("Profile")
    self.profile_chk.setChecked(True)
    self.show_profile_chk = self.profile_chk  # Alias for backward compatibility
    controls.addWidget(self.profile_chk)
    controls.addStretch(1)
    profile_layout.addLayout(controls)
    profile_layout.addWidget(self.profile_canvas)
    return profile_container


def make_orthoview_widget(self) -> QtWidgets.QWidget:
    widget = OrthoViewWidget(parent=self)
    self.orthoview_widget = widget
    return widget


def make_smlm_widget(self) -> QtWidgets.QWidget:
    widget = SmlmPanel(parent=self)
    self.smlm_panel = widget
    return widget


def make_threshold_widget(self) -> QtWidgets.QWidget:
    widget = ThresholdPanel(parent=self)
    self.threshold_panel = widget
    return widget


def make_particles_widget(self) -> QtWidgets.QWidget:
    widget = AnalyzeParticlesPanel(parent=self)
    self.particles_panel = widget
    return widget


def make_logs_widget(self) -> QtWidgets.QWidget:
    """Create the logs and cache statistics widget."""
    logs_widget = QtWidgets.QWidget()
    logs_layout = QtWidgets.QVBoxLayout(logs_widget)
    logs_layout.setContentsMargins(8, 8, 8, 8)
    logs_layout.setSpacing(6)
    # Status label is initialized during UI setup; guard prevents startup-order issues.
    if self.status is not None:
        logs_layout.addWidget(self.status)
    # Header row: cache stats + filter + actions
    header_row = QtWidgets.QHBoxLayout()
    self.cache_stats_label = QtWidgets.QLabel("Cache: 0 MB | Items: 0")
    header_row.addWidget(self.cache_stats_label)
    
    # Severity filter
    filter_label = QtWidgets.QLabel(" Level:")
    self.log_level_combo = QtWidgets.QComboBox()
    self.log_level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
    self.log_level_combo.setCurrentText("ALL")
    self.log_level_combo.setToolTip("Filter log messages by severity level")
    self.log_level_combo.setMaximumWidth(100)
    header_row.addWidget(filter_label)
    header_row.addWidget(self.log_level_combo)
    
    header_row.addStretch(1)
    copy_btn = QtWidgets.QToolButton()
    copy_btn.setText("Copy")
    copy_btn.setToolTip("Copy logs to clipboard")
    save_btn = QtWidgets.QToolButton()
    save_btn.setText("Save…")
    save_btn.setToolTip("Save logs to file")
    clear_btn = QtWidgets.QToolButton()
    clear_btn.setText("Clear")
    clear_btn.setToolTip("Clear log view")
    header_row.addWidget(copy_btn)
    header_row.addWidget(save_btn)
    header_row.addWidget(clear_btn)
    logs_layout.addLayout(header_row)
    self.log_view = QtWidgets.QPlainTextEdit()
    self.log_view.setReadOnly(True)
    self.log_view.setMaximumBlockCount(1000)
    self.log_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
    logs_layout.addWidget(self.log_view)

    # Store full logs for filtering
    self._all_logs = []
    
    # Wire actions
    def _copy_logs() -> None:
        QtWidgets.QApplication.clipboard().setText(self.log_view.toPlainText())
    
    def _clear_logs() -> None:
        self.log_view.clear()
        self._all_logs.clear()

    def _save_logs() -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Logs", str(pathlib.Path.cwd() / "phage_annotator.log"), "Log Files (*.log);;Text Files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Logs failed", str(exc))
    
    def _filter_logs() -> None:
        """Filter logs based on selected severity level."""
        level = self.log_level_combo.currentText()
        self.log_view.clear()
        
        if level == "ALL":
            for log_entry in self._all_logs:
                self.log_view.appendPlainText(log_entry)
        else:
            # Filter by level keyword
            for log_entry in self._all_logs:
                if f"[{level}]" in log_entry or (level == "ERROR" and "[EXCEPTION]" in log_entry):
                    self.log_view.appendPlainText(log_entry)

    copy_btn.clicked.connect(_copy_logs)
    save_btn.clicked.connect(_save_logs)
    clear_btn.clicked.connect(_clear_logs)
    self.log_level_combo.currentTextChanged.connect(_filter_logs)
    return logs_widget


def make_metadata_widget(self) -> QtWidgets.QWidget:
    widget = MetadataDock(parent=self)
    self.metadata_widget = widget
    return widget


def make_density_widget(self) -> QtWidgets.QWidget:
    widget = DensityPanel(parent=self)
    self.density_panel = widget
    return widget


def setup_status_bar(self) -> None:
    """Initialize status-bar widgets (progress, buffer stats, and tool status)."""
    status_bar = self.statusBar()
    status_bar.setSizeGripEnabled(True)

    # QLabel used by docks as the shared status text widget.
    self.status = QtWidgets.QLabel("")
    status_bar.addWidget(self.status, stretch=1)
    
    self.progress_label = QtWidgets.QLabel("Working:")
    self.progress_bar = QtWidgets.QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setFixedWidth(160)
    self.progress_cancel_btn = QtWidgets.QToolButton()
    self.progress_cancel_btn.setText("Cancel")
    self.progress_cancel_btn.clicked.connect(self._cancel_active_job)
    # Add a 'Cancel All' button to stop all background jobs
    self.progress_cancel_all_btn = QtWidgets.QToolButton()
    self.progress_cancel_all_btn.setText("Cancel All")
    self.progress_cancel_all_btn.clicked.connect(self._cancel_all_jobs)
    for w in (self.progress_label, self.progress_bar, self.progress_cancel_btn, self.progress_cancel_all_btn):
        w.setVisible(False)
        status_bar.addPermanentWidget(w)
    self.buffer_stats_label = QtWidgets.QLabel("Buffer: 0/0 | Prefetch: 64 | Underruns: 0")
    self.buffer_stats_label.setVisible(False)
    status_bar.addPermanentWidget(self.buffer_stats_label)
    self.render_level_label = QtWidgets.QLabel("Render: L0")
    self.render_level_label.setVisible(False)
    status_bar.addPermanentWidget(self.render_level_label)
    self.tool_label = QtWidgets.QLabel("Tool: Annotate")
    self.tool_label.setVisible(False)
    status_bar.addPermanentWidget(self.tool_label)
    self.annotation_meta_widget = QtWidgets.QWidget()
    meta_layout = QtWidgets.QHBoxLayout(self.annotation_meta_widget)
    meta_layout.setContentsMargins(6, 0, 6, 0)
    meta_layout.setSpacing(6)
    self.annotation_meta_label = QtWidgets.QLabel("Metadata detected.")
    self.annotation_meta_apply_btn = QtWidgets.QToolButton()
    self.annotation_meta_apply_btn.setText("Apply")
    self.annotation_meta_close_btn = QtWidgets.QToolButton()
    self.annotation_meta_close_btn.setText("Dismiss")
    meta_layout.addWidget(self.annotation_meta_label)
    meta_layout.addWidget(self.annotation_meta_apply_btn)
    meta_layout.addWidget(self.annotation_meta_close_btn)
    self.annotation_meta_widget.setVisible(False)
    status_bar.addWidget(self.annotation_meta_widget)
