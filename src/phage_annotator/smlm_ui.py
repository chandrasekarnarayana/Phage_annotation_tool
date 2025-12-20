"""Unified SMLM UI panel with presets for ThunderSTORM and Deep-STORM."""

from __future__ import annotations

from typing import Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.deepstorm_widget import DeepStormDockWidget
from phage_annotator.smlm_presets import PRESETS
from phage_annotator.smlm_widget import SmlmDockWidget


class SmlmPanel(QtWidgets.QWidget):
    """Unified SMLM panel with presets and per-method tabs."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel("Preset"))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(["Balanced", "Conservative", "Sensitive"])
        preset_row.addWidget(self.preset_combo)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)

        self.tabs = QtWidgets.QTabWidget()
        self.thunder = SmlmDockWidget(parent=self)
        self.deep = DeepStormDockWidget(parent=self)
        self.tabs.addTab(self.thunder, "ThunderSTORM")
        self.tabs.addTab(self.deep, "Deep-STORM")
        layout.addWidget(self.tabs)

        self._apply_tooltips()
        self.apply_preset("Balanced")

    def apply_preset(self, name: str) -> None:
        """Apply a preset to both ThunderSTORM and Deep-STORM controls."""
        preset = PRESETS.get(name)
        if not preset:
            return
        thunder = preset["thunder"]
        deep = preset["deep"]
        self.thunder.sigma_spin.setValue(thunder.sigma_px)
        self.thunder.fit_radius_spin.setValue(thunder.fit_radius_px)
        self.thunder.det_thr_spin.setValue(thunder.detection_thr_sigma)
        self.thunder.merge_radius_spin.setValue(thunder.merge_radius_px)
        self.thunder.min_photons_spin.setValue(thunder.min_photons)

        self.deep.patch_combo.setCurrentText(str(deep.patch_size))
        self.deep.overlap_spin.setValue(deep.overlap)
        self.deep.upsample_spin.setValue(deep.upsample)
        self.deep.sigma_spin.setValue(deep.sigma_px)
        self.deep.normalize_combo.setCurrentText(deep.normalize_mode)
        self.deep.window_spin.setValue(deep.window_size)
        self.deep.agg_combo.setCurrentText(deep.aggregation_mode)

    def _apply_tooltips(self) -> None:
        sigma_tip = "sigma_px ≈ FWHM/2.35; start 1.1–1.6 px."
        thr_tip = "Threshold 2–6 sigma; higher = fewer false positives."
        fit_tip = "Fit radius 3–5 px for typical spots."
        self.thunder.sigma_spin.setToolTip(sigma_tip)
        self.thunder.det_thr_spin.setToolTip(thr_tip)
        self.thunder.fit_radius_spin.setToolTip(fit_tip)
        self.deep.sigma_spin.setToolTip(sigma_tip)
