"""Qt panel for Analyze Particles controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets


@dataclass
class AnalyzeParticlesValues:
    """Snapshot of Analyze Particles controls."""

    modality: str  # Phase ζ: Selected modality name
    region_roi: bool
    scope: str
    min_area: int
    max_area: int
    min_circ: float
    max_circ: float
    exclude_edges: bool
    include_holes: bool
    clear_previous: bool
    show_outlines: bool
    show_boxes: bool
    show_ellipses: bool
    show_labels: bool
    watershed_split: bool


class AnalyzeParticlesPanel(QtWidgets.QWidget):
    """Analyze Particles panel with filters and results table."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize the object and prepare its runtime state."""
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        layout.addLayout(form)

        # Phase ζ: Modality selector for multi-modality analysis
        self.modality_combo = QtWidgets.QComboBox()
        self.modality_combo.addItem("Current (Modality 1)")
        form.addRow("Run on modality", self.modality_combo)

        self.region_chk = QtWidgets.QCheckBox("ROI only")
        self.region_chk.setChecked(True)
        form.addRow("Region", self.region_chk)

        self.scope_combo = QtWidgets.QComboBox()
        self.scope_combo.addItems(["Current slice", "All frames"])
        form.addRow("Scope", self.scope_combo)

        self.min_area_spin = QtWidgets.QSpinBox()
        self.min_area_spin.setRange(0, 100000)
        self.min_area_spin.setValue(5)
        self.max_area_spin = QtWidgets.QSpinBox()
        self.max_area_spin.setRange(0, 1000000)
        self.max_area_spin.setValue(0)
        form.addRow("Min area (px)", self.min_area_spin)
        form.addRow("Max area (px, 0=inf)", self.max_area_spin)

        self.min_circ_spin = QtWidgets.QDoubleSpinBox()
        self.min_circ_spin.setRange(0.0, 1.0)
        self.min_circ_spin.setDecimals(2)
        self.min_circ_spin.setValue(0.0)
        self.max_circ_spin = QtWidgets.QDoubleSpinBox()
        self.max_circ_spin.setRange(0.0, 1.0)
        self.max_circ_spin.setDecimals(2)
        self.max_circ_spin.setValue(1.0)
        form.addRow("Min circularity", self.min_circ_spin)
        form.addRow("Max circularity", self.max_circ_spin)

        self.exclude_edges_chk = QtWidgets.QCheckBox("Exclude edge particles")
        self.exclude_edges_chk.setChecked(True)
        self.include_holes_chk = QtWidgets.QCheckBox("Include holes")
        form.addRow(self.exclude_edges_chk)
        form.addRow(self.include_holes_chk)
        self.watershed_chk = QtWidgets.QCheckBox("Watershed split")
        form.addRow(self.watershed_chk)

        self.clear_chk = QtWidgets.QCheckBox("Clear previous results")
        self.clear_chk.setChecked(True)
        form.addRow(self.clear_chk)

        show_box = QtWidgets.QGroupBox("Show overlays")
        show_layout = QtWidgets.QVBoxLayout(show_box)
        self.show_outlines_chk = QtWidgets.QCheckBox("Outlines")
        self.show_boxes_chk = QtWidgets.QCheckBox("Bounding boxes")
        self.show_ellipses_chk = QtWidgets.QCheckBox("Ellipses")
        self.show_labels_chk = QtWidgets.QCheckBox("Labels")
        self.show_outlines_chk.setChecked(True)
        show_layout.addWidget(self.show_outlines_chk)
        show_layout.addWidget(self.show_boxes_chk)
        show_layout.addWidget(self.show_ellipses_chk)
        show_layout.addWidget(self.show_labels_chk)
        layout.addWidget(show_box)

        btn_row = QtWidgets.QHBoxLayout()
        self.measure_btn = QtWidgets.QPushButton("Measure")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.selection_btn = QtWidgets.QPushButton("Create selection")
        btn_row.addWidget(self.measure_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.selection_btn)
        layout.addLayout(btn_row)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Frame", "Area", "Perim", "Circ", "X", "Y", "EqDiam", "BBox"]
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def values(self) -> AnalyzeParticlesValues:
        """Return a typed snapshot of current UI values."""
        return AnalyzeParticlesValues(
            modality=self.modality_combo.currentText(),
            region_roi=self.region_chk.isChecked(),
            scope=self.scope_combo.currentText(),
            min_area=int(self.min_area_spin.value()),
            max_area=int(self.max_area_spin.value()),
            min_circ=float(self.min_circ_spin.value()),
            max_circ=float(self.max_circ_spin.value()),
            exclude_edges=self.exclude_edges_chk.isChecked(),
            include_holes=self.include_holes_chk.isChecked(),
            clear_previous=self.clear_chk.isChecked(),
            show_outlines=self.show_outlines_chk.isChecked(),
            show_boxes=self.show_boxes_chk.isChecked(),
            show_ellipses=self.show_ellipses_chk.isChecked(),
            show_labels=self.show_labels_chk.isChecked(),
            watershed_split=self.watershed_chk.isChecked(),
        )

    def update_modality_list(self, modality_manager) -> None:
        """Update modality combo with available modalities."""
        current_text = self.modality_combo.currentText()
        self.modality_combo.clear()
        self.modality_combo.addItem("Current (Modality 1)")
        
        if modality_manager is not None:
            modalities = modality_manager.get_all_modalities()
            for modality in modalities:
                self.modality_combo.addItem(modality.display_name, modality.idx)
        
        # Restore previous selection if still available
        idx = self.modality_combo.findText(current_text)
        if idx >= 0:
            self.modality_combo.setCurrentIndex(idx)
    
    def get_selected_modality_idx(self) -> Optional[int]:
        """Get modality_idx for selected modality, or None for current."""
        data = self.modality_combo.currentData()
        return data if data is not None else None
