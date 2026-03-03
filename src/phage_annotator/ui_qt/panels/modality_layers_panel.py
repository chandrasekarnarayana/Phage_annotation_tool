"""Layer-style modality/evidence controls for suggestion workflows."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtWidgets


class ModalityLayersPanel(QtWidgets.QWidget):
    """Manage modality/view evidence states in a compact layer table."""

    layer_changed = QtCore.Signal(str, bool, float, str, str)
    save_preset_requested = QtCore.Signal(str)
    load_preset_requested = QtCore.Signal(str)
    compare_presets_requested = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self.header_lbl = QtWidgets.QLabel("Modality / Evidence Layers")
        self.header_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.header_lbl)
        self.first_run_hint_lbl = QtWidgets.QLabel(
            "Tip: Set role=proposal evidence for modalities used by suggestion generation."
        )
        self.first_run_hint_lbl.setWordWrap(True)
        self.first_run_hint_lbl.setStyleSheet("color: #455a64; font-style: italic;")
        layout.addWidget(self.first_run_hint_lbl)

        self.table = QtWidgets.QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Visible", "Modality", "Opacity", "Colormap", "Role"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel("Preset"))
        self.preset_name_edit = QtWidgets.QLineEdit(self)
        self.preset_name_edit.setPlaceholderText("experiment_default")
        self.save_btn = QtWidgets.QPushButton("Save", self)
        self.load_btn = QtWidgets.QPushButton("Load", self)
        preset_row.addWidget(self.preset_name_edit, stretch=1)
        preset_row.addWidget(self.save_btn)
        preset_row.addWidget(self.load_btn)
        layout.addLayout(preset_row)

        self.save_btn.clicked.connect(self._emit_save)
        self.load_btn.clicked.connect(self._emit_load)

        compare_group = QtWidgets.QGroupBox("Quick Compare (A/B)", self)
        compare_layout = QtWidgets.QGridLayout(compare_group)
        compare_layout.setContentsMargins(8, 8, 8, 8)
        compare_layout.addWidget(QtWidgets.QLabel("A"), 0, 0)
        self.compare_a_edit = QtWidgets.QLineEdit(self)
        self.compare_a_edit.setPlaceholderText("preset_a")
        compare_layout.addWidget(self.compare_a_edit, 0, 1)
        compare_layout.addWidget(QtWidgets.QLabel("B"), 1, 0)
        self.compare_b_edit = QtWidgets.QLineEdit(self)
        self.compare_b_edit.setPlaceholderText("preset_b")
        compare_layout.addWidget(self.compare_b_edit, 1, 1)
        self.compare_btn = QtWidgets.QPushButton("Compare A/B", self)
        compare_layout.addWidget(self.compare_btn, 2, 0, 1, 2)
        layout.addWidget(compare_group)
        self.compare_btn.clicked.connect(self._emit_compare)

    def _emit_save(self) -> None:
        name = str(self.preset_name_edit.text()).strip() or "default"
        self.save_preset_requested.emit(name)

    def _emit_load(self) -> None:
        name = str(self.preset_name_edit.text()).strip() or "default"
        self.load_preset_requested.emit(name)

    def _emit_compare(self) -> None:
        a_name = str(self.compare_a_edit.text()).strip() or "default"
        b_name = str(self.compare_b_edit.text()).strip() or "default"
        self.compare_presets_requested.emit(a_name, b_name)

    def set_layers(self, layers: list[dict]) -> None:
        """Populate rows from layer dictionaries."""
        self.table.setRowCount(0)
        for row_idx, layer in enumerate(layers):
            self.table.insertRow(row_idx)
            modality_id = str(layer.get("modality_id", "unknown"))
            visible = bool(layer.get("visible", True))
            opacity = float(layer.get("opacity", 1.0))
            lut = str(layer.get("lut", "gray"))
            role = str(layer.get("role", "proposal evidence"))

            visible_chk = QtWidgets.QCheckBox(self.table)
            visible_chk.setChecked(visible)
            visible_chk.toggled.connect(
                lambda checked, m=modality_id, r=row_idx: self._emit_row_change(r, m, checked=checked)
            )
            self.table.setCellWidget(row_idx, 0, visible_chk)

            self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(modality_id))

            opacity_spin = QtWidgets.QDoubleSpinBox(self.table)
            opacity_spin.setRange(0.0, 1.0)
            opacity_spin.setDecimals(2)
            opacity_spin.setSingleStep(0.05)
            opacity_spin.setValue(max(0.0, min(1.0, opacity)))
            opacity_spin.valueChanged.connect(
                lambda _v, m=modality_id, r=row_idx: self._emit_row_change(r, m)
            )
            self.table.setCellWidget(row_idx, 2, opacity_spin)

            lut_combo = QtWidgets.QComboBox(self.table)
            for name in ("gray", "viridis", "magma", "plasma", "inferno"):
                lut_combo.addItem(name)
            idx = lut_combo.findText(lut)
            lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
            lut_combo.currentTextChanged.connect(
                lambda _text, m=modality_id, r=row_idx: self._emit_row_change(r, m)
            )
            self.table.setCellWidget(row_idx, 3, lut_combo)

            role_combo = QtWidgets.QComboBox(self.table)
            role_combo.addItems(["proposal evidence", "view only"])
            ridx = role_combo.findText(role)
            role_combo.setCurrentIndex(ridx if ridx >= 0 else 0)
            role_combo.currentTextChanged.connect(
                lambda _text, m=modality_id, r=row_idx: self._emit_row_change(r, m)
            )
            self.table.setCellWidget(row_idx, 4, role_combo)

        self.table.resizeColumnsToContents()

    def _emit_row_change(self, row_idx: int, modality_id: str, checked: bool | None = None) -> None:
        visible_widget = self.table.cellWidget(row_idx, 0)
        opacity_widget = self.table.cellWidget(row_idx, 2)
        lut_widget = self.table.cellWidget(row_idx, 3)
        role_widget = self.table.cellWidget(row_idx, 4)
        if visible_widget is None or opacity_widget is None or lut_widget is None or role_widget is None:
            return
        visible = bool(visible_widget.isChecked()) if checked is None else bool(checked)
        opacity = float(opacity_widget.value())
        lut = str(lut_widget.currentText())
        role = str(role_widget.currentText())
        self.layer_changed.emit(str(modality_id), visible, opacity, lut, role)
