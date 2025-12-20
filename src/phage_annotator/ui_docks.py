"""Dock/panel wiring helpers for the main window."""

from __future__ import annotations

from typing import List, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.analyze_particles_panel import AnalyzeParticlesPanel
from phage_annotator.density_panel import DensityPanel
from phage_annotator.metadata_dock import MetadataDock
from phage_annotator.orthoview import OrthoViewWidget
from phage_annotator.panels import PanelSpec
from phage_annotator.recorder import RecorderWidget
from phage_annotator.results_table import ResultsTableWidget
from phage_annotator.roi_widgets import RoiManagerWidget
from phage_annotator.smlm_ui import SmlmPanel
from phage_annotator.threshold_panel import ThresholdPanel


def init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
    """Create dock widgets and View menu actions from the registry."""
    self.panel_specs = build_panel_registry(self)
    self.panel_docks.clear()
    self.dock_actions.clear()

    for spec in self.panel_specs:
        widget = spec.widget_factory()
        dock = create_dock(self, spec.id, spec.title, widget)
        self.panel_docks[spec.id] = dock
        self.addDockWidget(spec.default_area, dock)
        action = dock_menu.addAction(spec.toggle_action_text)
        action.setCheckable(True)
        action.setChecked(spec.default_visible)
        if spec.shortcut:
            action.setShortcut(spec.shortcut)
        self.dock_actions[spec.id] = action
        checkbox = None
        if spec.id == "hist":
            checkbox = self.hist_chk
        elif spec.id == "profile":
            checkbox = self.profile_chk
        wire_dock_action(self, dock, action, checkbox)
        dock.setVisible(spec.default_visible)

    self.dock_sidebar = self.panel_docks.get("sidebar")
    self.dock_annotations = self.panel_docks.get("annotations")
    self.dock_roi = self.panel_docks.get("roi")
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

    if self.dock_hist and self.dock_profile:
        self.tabifyDockWidget(self.dock_hist, self.dock_profile)
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
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_roi_widget,
            toggle_action_text="ROI Controls",
        ),
        PanelSpec(
            id="roi_manager",
            title="ROI Manager",
            default_area=QtCore.Qt.RightDockWidgetArea,
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
            default_visible=True,
            widget_factory=self._make_hist_widget,
            toggle_action_text="Histogram",
        ),
        PanelSpec(
            id="profile",
            title="Line Profile",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_profile_widget,
            toggle_action_text="Line Profile",
        ),
        PanelSpec(
            id="orthoview",
            title="Ortho Views",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_orthoview_widget,
            toggle_action_text="Ortho Views",
        ),
        PanelSpec(
            id="smlm",
            title="SMLM (ROI)",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_smlm_widget,
            toggle_action_text="SMLM (ROI)",
        ),
        PanelSpec(
            id="threshold",
            title="Threshold",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_threshold_widget,
            toggle_action_text="Threshold",
        ),
        PanelSpec(
            id="particles",
            title="Analyze Particles",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_particles_widget,
            toggle_action_text="Analyze Particles",
        ),
        PanelSpec(
            id="density",
            title="Density",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_density_widget,
            toggle_action_text="Density",
        ),
        PanelSpec(
            id="logs",
            title="Logs",
            default_area=QtCore.Qt.BottomDockWidgetArea,
            default_visible=True,
            widget_factory=self._make_logs_widget,
            toggle_action_text="Toggle Logs",
        ),
        PanelSpec(
            id="metadata",
            title="Metadata",
            default_area=QtCore.Qt.RightDockWidgetArea,
            default_visible=False,
            widget_factory=self._make_metadata_widget,
            toggle_action_text="Metadata",
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
    return hist_container


def make_profile_widget(self) -> QtWidgets.QWidget:
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
    self.show_profile_chk = self.profile_chk
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
    logs_widget = QtWidgets.QWidget()
    logs_layout = QtWidgets.QVBoxLayout(logs_widget)
    logs_layout.setContentsMargins(8, 8, 8, 8)
    logs_layout.setSpacing(6)
    logs_layout.addWidget(self.status)
    self.cache_stats_label = QtWidgets.QLabel("Cache: 0 MB | Items: 0")
    logs_layout.addWidget(self.cache_stats_label)
    self.log_view = QtWidgets.QPlainTextEdit()
    self.log_view.setReadOnly(True)
    self.log_view.setMaximumBlockCount(500)
    logs_layout.addWidget(self.log_view)
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
    """Initialize the status bar widgets (progress + tool indicator)."""
    status = self.statusBar()
    self.status = status
    status.setSizeGripEnabled(True)
    self.progress_label = QtWidgets.QLabel("Working:")
    self.progress_bar = QtWidgets.QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setFixedWidth(160)
    self.progress_cancel_btn = QtWidgets.QToolButton()
    self.progress_cancel_btn.setText("Cancel")
    self.progress_cancel_btn.clicked.connect(self._cancel_active_job)
    for w in (self.progress_label, self.progress_bar, self.progress_cancel_btn):
        w.setVisible(False)
        status.addPermanentWidget(w)
    self.buffer_stats_label = QtWidgets.QLabel("Buffer: 0/0 | Prefetch: 64 | Underruns: 0")
    status.addPermanentWidget(self.buffer_stats_label)
    self.render_level_label = QtWidgets.QLabel("Render: L0")
    status.addPermanentWidget(self.render_level_label)
    self.tool_label = QtWidgets.QLabel("Tool: Annotate")
    status.addPermanentWidget(self.tool_label)
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
    status.addWidget(self.annotation_meta_widget)
