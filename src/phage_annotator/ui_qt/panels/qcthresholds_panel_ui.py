"""Extracted method group 1 for QCThresholdsPanel."""

from __future__ import annotations

from typing import Optional, Callable

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.session.qc_thresholds import QCThresholds



class QcthresholdsPanelUiMixin:
    """Method group 1 extracted from QCThresholdsPanel."""

    def __init__(
        self,
        thresholds: Optional[QCThresholds] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize threshold settings dialog.
        
        Parameters
        ----------
        thresholds : QCThresholds, optional
            Initial threshold configuration.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("QC Thresholds & Sensitivity")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        self.thresholds = thresholds or QCThresholds()
        self.widgets = {}  # Track widgets for easy access
        
        self._setup_ui()
        self._load_thresholds()
    def _setup_ui(self) -> None:
        """Build the UI with tabs for each section."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Tabs for sections
        tabs = QtWidgets.QTabWidget()
        
        # Tab 1: Annotation Spatial Constraints
        tabs.addTab(self._create_spatial_tab(), "Annotation Constraints")
        
        # Tab 2: Image Quality Artifacts
        tabs.addTab(self._create_artifacts_tab(), "Image Quality")
        
        # Tab 3: Statistical Checks
        tabs.addTab(self._create_stochasticity_tab(), "Stochasticity")
        
        # Tab 4: Enable/Disable
        tabs.addTab(self._create_enable_tab(), "Checks")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        # Presets
        preset_label = QtWidgets.QLabel("Presets:")
        button_layout.addWidget(preset_label)
        
        default_btn = QtWidgets.QPushButton("Default")
        default_btn.clicked.connect(self._preset_default)
        button_layout.addWidget(default_btn)
        
        strict_btn = QtWidgets.QPushButton("Strict")
        strict_btn.clicked.connect(self._preset_strict)
        button_layout.addWidget(strict_btn)
        
        relaxed_btn = QtWidgets.QPushButton("Relaxed")
        relaxed_btn.clicked.connect(self._preset_relaxed)
        button_layout.addWidget(relaxed_btn)
        
        button_layout.addStretch()
        
        # OK/Cancel
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    def _create_spatial_tab(self) -> QtWidgets.QWidget:
        """Create annotation spatial constraints tab."""
        w = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(w)
        layout.setSpacing(12)
        
        # Duplicate distance
        layout.addRow(QtWidgets.QLabel("<b>Duplicate Detection</b>"))
        dup_spin = QtWidgets.QDoubleSpinBox()
        dup_spin.setRange(0.1, 20.0)
        dup_spin.setSingleStep(0.5)
        dup_spin.setSuffix(" px")
        dup_spin.setToolTip("Maximum distance for annotations to be considered duplicates")
        self.widgets["duplicate_distance_px"] = dup_spin
        layout.addRow("Duplicate distance:", dup_spin)
        
        # Border safety margin
        layout.addRow(QtWidgets.QLabel("<b>Boundary Constraints</b>"))
        margin_spin = QtWidgets.QDoubleSpinBox()
        margin_spin.setRange(0.0, 50.0)
        margin_spin.setSingleStep(1.0)
        margin_spin.setSuffix(" px")
        margin_spin.setToolTip("Minimum distance from image edge (warning if closer)")
        self.widgets["border_safety_margin_px"] = margin_spin
        layout.addRow("Safety margin from edge:", margin_spin)
        
        # Density clustering
        layout.addRow(QtWidgets.QLabel("<b>Density Clustering</b>"))
        grid_spin = QtWidgets.QDoubleSpinBox()
        grid_spin.setRange(10.0, 200.0)
        grid_spin.setSingleStep(5.0)
        grid_spin.setSuffix(" px")
        grid_spin.setToolTip("Grid cell size for density analysis (smaller = finer)")
        self.widgets["density_grid_size_px"] = grid_spin
        layout.addRow("Grid cell size:", grid_spin)
        
        count_spin = QtWidgets.QSpinBox()
        count_spin.setRange(1, 50)
        count_spin.setSingleStep(1)
        count_spin.setToolTip("Minimum annotations in grid cell to flag as cluster")
        self.widgets["density_min_annotations"] = count_spin
        layout.addRow("Min annotations per cell:", count_spin)

        return w
