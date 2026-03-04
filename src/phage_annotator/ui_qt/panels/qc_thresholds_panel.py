"""QC Thresholds settings panel for interactive tuning.

Provides a well-organized UI for adjusting QC sensitivity parameters
with live preview and preset profiles.
"""

from __future__ import annotations

from typing import Optional, Callable

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.session.qc_thresholds import QCThresholds


class QCThresholdsPanel(QtWidgets.QDialog):
    """
    Dialog for configuring QC thresholds.
    
    Organized into logical sections:
    - Annotation Spatial Constraints
    - Image Quality (Artifacts)
    - Statistical (Stochasticity)
    - Enable/Disable Checks
    """
    
    thresholds_changed = QtCore.Signal()  # Emitted when user changes thresholds
    
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
        
        layout.addStretch()
        return w
    
    def _create_artifacts_tab(self) -> QtWidgets.QWidget:
        """Create image quality artifacts tab."""
        w = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(w)
        layout.setSpacing(12)
        
        # Illumination
        layout.addRow(QtWidgets.QLabel("<b>Illumination Evenness</b>"))
        ill_min = QtWidgets.QDoubleSpinBox()
        ill_min.setRange(0.1, 2.0)
        ill_min.setSingleStep(0.05)
        ill_min.setDecimals(2)
        ill_min.setToolTip("Minimum center/border ratio (below = dark edges)")
        self.widgets["illumination_ratio_min"] = ill_min
        layout.addRow("Min ratio (center/border):", ill_min)
        
        ill_max = QtWidgets.QDoubleSpinBox()
        ill_max.setRange(0.1, 2.0)
        ill_max.setSingleStep(0.05)
        ill_max.setDecimals(2)
        ill_max.setToolTip("Maximum center/border ratio (above = bright center)")
        self.widgets["illumination_ratio_max"] = ill_max
        layout.addRow("Max ratio (center/border):", ill_max)
        
        # Photobleaching
        layout.addRow(QtWidgets.QLabel("<b>Photobleaching</b>"))
        photo_spin = QtWidgets.QDoubleSpinBox()
        photo_spin.setRange(0.0, 100.0)
        photo_spin.setSingleStep(1.0)
        photo_spin.setSuffix(" %")
        photo_spin.setToolTip("Maximum allowed intensity drop over frames")
        self.widgets["photobleaching_drop_percent"] = photo_spin
        layout.addRow("Max intensity drop:", photo_spin)
        
        # Dust/Lens Artifacts
        layout.addRow(QtWidgets.QLabel("<b>Dust & Lens Artifacts</b>"))
        dust_px = QtWidgets.QSpinBox()
        dust_px.setRange(1, 1000)
        dust_px.setSingleStep(1)
        dust_px.setSuffix(" px")
        dust_px.setToolTip("Minimum persistent artifact pixels to flag")
        self.widgets["dust_min_pixels"] = dust_px
        layout.addRow("Min artifact pixels:", dust_px)
        
        dust_pct = QtWidgets.QDoubleSpinBox()
        dust_pct.setRange(0.01, 1.0)
        dust_pct.setSingleStep(0.01)
        dust_pct.setDecimals(3)
        dust_pct.setSuffix(" %")
        dust_pct.setToolTip("Percent of image size for dynamic dust detection")
        self.widgets["dust_percent_image"] = dust_pct
        layout.addRow("Dynamic threshold (% image):", dust_pct)
        
        # Patterned intensity
        layout.addRow(QtWidgets.QLabel("<b>Patterned Intensity</b>"))
        pattern_spin = QtWidgets.QDoubleSpinBox()
        pattern_spin.setRange(0.01, 0.50)
        pattern_spin.setSingleStep(0.01)
        pattern_spin.setDecimals(2)
        pattern_spin.setToolTip("Max band strength (row/col std / frame std)")
        self.widgets["patterned_band_strength"] = pattern_spin
        layout.addRow("Max band strength:", pattern_spin)
        
        # Clustered signal
        layout.addRow(QtWidgets.QLabel("<b>Clustered Bright Signal</b>"))
        cluster_count = QtWidgets.QSpinBox()
        cluster_count.setRange(1, 500)
        cluster_count.setSingleStep(10)
        self.widgets["clustered_signal_peak_count"] = cluster_count
        layout.addRow("Min peak count:", cluster_count)
        
        cluster_ratio = QtWidgets.QDoubleSpinBox()
        cluster_ratio.setRange(1.0, 10.0)
        cluster_ratio.setSingleStep(0.1)
        cluster_ratio.setDecimals(2)
        self.widgets["clustered_signal_ratio"] = cluster_ratio
        layout.addRow("Peak/mean multiplier:", cluster_ratio)
        
        layout.addStretch()
        return w
    
    def _create_stochasticity_tab(self) -> QtWidgets.QWidget:
        """Create stochasticity checks tab."""
        w = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(w)
        layout.setSpacing(12)
        
        # Image Fano-factor
        layout.addRow(QtWidgets.QLabel("<b>Image Signal Stochasticity</b>"))
        layout.addRow(QtWidgets.QLabel("(Fano-factor = variance/mean; ~1.0 = Poisson)"))
        
        img_fano_min = QtWidgets.QDoubleSpinBox()
        img_fano_min.setRange(0.1, 5.0)
        img_fano_min.setSingleStep(0.1)
        img_fano_min.setDecimals(2)
        img_fano_min.setToolTip("Minimum allowed Fano-factor")
        self.widgets["image_fano_min"] = img_fano_min
        layout.addRow("Min Fano-factor:", img_fano_min)
        
        img_fano_max = QtWidgets.QDoubleSpinBox()
        img_fano_max.setRange(0.1, 5.0)
        img_fano_max.setSingleStep(0.1)
        img_fano_max.setDecimals(2)
        img_fano_max.setToolTip("Maximum allowed Fano-factor")
        self.widgets["image_fano_max"] = img_fano_max
        layout.addRow("Max Fano-factor:", img_fano_max)
        
        img_warn = QtWidgets.QDoubleSpinBox()
        img_warn.setRange(0.1, 10.0)
        img_warn.setSingleStep(0.2)
        img_warn.setDecimals(2)
        img_warn.setToolTip("Fano-factor above this is WARNING severity")
        self.widgets["image_fano_warning_threshold"] = img_warn
        layout.addRow("Warning threshold:", img_warn)
        
        # Annotation Spatial Fano-factor
        layout.addRow(QtWidgets.QLabel("<b>Annotation Spatial Stochasticity</b>"))
        ann_fano_min = QtWidgets.QDoubleSpinBox()
        ann_fano_min.setRange(0.1, 5.0)
        ann_fano_min.setSingleStep(0.1)
        ann_fano_min.setDecimals(2)
        self.widgets["annotation_fano_min"] = ann_fano_min
        layout.addRow("Min Fano-factor:", ann_fano_min)
        
        ann_fano_max = QtWidgets.QDoubleSpinBox()
        ann_fano_max.setRange(0.1, 5.0)
        ann_fano_max.setSingleStep(0.1)
        ann_fano_max.setDecimals(2)
        self.widgets["annotation_fano_max"] = ann_fano_max
        layout.addRow("Max Fano-factor:", ann_fano_max)
        
        ann_warn = QtWidgets.QDoubleSpinBox()
        ann_warn.setRange(0.1, 10.0)
        ann_warn.setSingleStep(0.2)
        ann_warn.setDecimals(2)
        self.widgets["annotation_fano_warning_threshold"] = ann_warn
        layout.addRow("Warning threshold:", ann_warn)
        
        layout.addStretch()
        return w
    
    def _create_enable_tab(self) -> QtWidgets.QWidget:
        """Create enable/disable checks tab."""
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setSpacing(8)
        
        layout.addWidget(QtWidgets.QLabel("<b>Annotation Checks</b>"))
        
        checks = [
            ("enabled_duplicate_check", "Enable duplicate detection"),
            ("enabled_bounds_check", "Enable out-of-bounds detection"),
            ("enabled_label_check", "Enable label validation"),
            ("enabled_density_check", "Enable density clustering detection"),
        ]
        
        for field_name, label_text in checks:
            cb = QtWidgets.QCheckBox(label_text)
            self.widgets[field_name] = cb
            layout.addWidget(cb)
        
        layout.addWidget(QtWidgets.QLabel("<b>Image Quality Checks</b>"))
        
        artifact_checks = [
            ("enabled_illumination_check", "Enable illumination analysis"),
            ("enabled_photobleaching_check", "Enable photobleaching detection"),
            ("enabled_dust_check", "Enable dust/lens artifact detection"),
            ("enabled_patterned_check", "Enable patterned intensity detection"),
            ("enabled_clustered_signal_check", "Enable clustered signal detection"),
        ]
        
        for field_name, label_text in artifact_checks:
            cb = QtWidgets.QCheckBox(label_text)
            self.widgets[field_name] = cb
            layout.addWidget(cb)
        
        layout.addWidget(QtWidgets.QLabel("<b>Stochasticity Checks</b>"))
        
        stat_checks = [
            ("enabled_image_fano_check", "Enable image signal stochasticity check"),
            ("enabled_annotation_fano_check", "Enable annotation spatial stochasticity check"),
        ]
        
        for field_name, label_text in stat_checks:
            cb = QtWidgets.QCheckBox(label_text)
            self.widgets[field_name] = cb
            layout.addWidget(cb)
        
        layout.addStretch()
        return w
    
    def _load_thresholds(self) -> None:
        """Load current thresholds into UI widgets."""
        for field_name, widget in self.widgets.items():
            value = getattr(self.thresholds, field_name, None)
            if value is None:
                continue
            
            if isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox)):
                widget.setValue(value)
    
    def _save_thresholds(self) -> None:
        """Save UI values back to thresholds object."""
        for field_name, widget in self.widgets.items():
            if isinstance(widget, QtWidgets.QCheckBox):
                setattr(self.thresholds, field_name, widget.isChecked())
            elif isinstance(widget, (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox)):
                setattr(self.thresholds, field_name, float(widget.value()) if isinstance(widget, QtWidgets.QDoubleSpinBox) else int(widget.value()))
    
    def _preset_default(self) -> None:
        """Load default thresholds."""
        self.thresholds = QCThresholds()
        self._load_thresholds()
    
    def _preset_strict(self) -> None:
        """Load strict thresholds."""
        self.thresholds = QCThresholds.strict_profile()
        self._load_thresholds()
    
    def _preset_relaxed(self) -> None:
        """Load relaxed thresholds."""
        self.thresholds = QCThresholds.relaxed_profile()
        self._load_thresholds()
    
    def get_thresholds(self) -> QCThresholds:
        """Get configured thresholds."""
        self._save_thresholds()
        return self.thresholds
    
    def accept(self) -> None:
        """Override accept to save thresholds."""
        self._save_thresholds()
        self.thresholds_changed.emit()
        super().accept()


def show_qc_thresholds_dialog(
    parent: Optional[QtWidgets.QWidget] = None,
    thresholds: Optional[QCThresholds] = None,
) -> Optional[QCThresholds]:
    """Show QC thresholds dialog and return configured thresholds.
    
    Parameters
    ----------
    parent : QWidget, optional
        Parent widget.
    thresholds : QCThresholds, optional
        Initial thresholds.
    
    Returns
    -------
    QCThresholds or None
        Configured thresholds if OK clicked, None if cancelled.
    """
    dialog = QCThresholdsPanel(thresholds=thresholds, parent=parent)
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        return dialog.get_thresholds()
    return None
