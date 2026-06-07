"""Extracted method group 4 for UiSetupMixin."""

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



class DockStatusBarMixin:
    """Method group 4 extracted from UiSetupMixin."""

    def _build_roi_controls_layout(self) -> None:
        """Build ROI/crop controls used by the ROI dock."""
        if bool(getattr(self, "_annotate_roi_embedded", False)):
            self._roi_controls_layout = None
            return
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
        """Handle the setup status bar helper flow."""
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


def setup_status_bar(self) -> None:
    """Create and attach a ManagedStatusBar to the main window."""
    from phage_annotator.ui_qt.services.status import ManagedStatusBar
    bar = ManagedStatusBar(parent=self)
    try:
        self.setStatusBar(bar)
    except Exception:
        pass
    self._managed_status_bar = bar
    status_service = getattr(self, "_status_service", None)
    if status_service is not None:
        try:
            bar.attach_status_service(status_service)
        except Exception:
            pass
