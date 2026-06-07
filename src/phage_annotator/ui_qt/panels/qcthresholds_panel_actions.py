"""Extracted method group 3 for QCThresholdsPanel."""

from __future__ import annotations

from typing import Optional, Callable

from matplotlib.backends.qt_compat import QtCore, QtWidgets, QtGui

from phage_annotator.session.qc_thresholds import QCThresholds



class QcthresholdsPanelActionsMixin:
    """Method group 3 extracted from QCThresholdsPanel."""

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
