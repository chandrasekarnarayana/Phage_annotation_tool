"""Extracted method group 2 for QCThresholdsPanel."""

from __future__ import annotations

from typing import Optional, Callable

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.session.qc_thresholds import QCThresholds



class QcthresholdsPanelControlsMixin:
    """Method group 2 extracted from QCThresholdsPanel."""

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
