"""Qt widget for ThunderSTORM-style SMLM controls."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins


@dataclass
class SmlmUiValues:
    """Snapshot of SMLM parameter values from the UI."""

    sigma_px: float
    fit_radius_px: int
    filter_type: str
    dog_sigma1: float
    dog_sigma2: float
    detection_thr_sigma: float
    max_candidates_per_frame: int
    merge_radius_px: float
    min_photons: float
    max_uncertainty_nm: float
    upsample: int
    render_mode: str
    render_sigma_nm: float
    backend: str
    plugin_id: str
    fiji_executable: str
    fiji_macro_path: str
    plugin_jar_path: str
    thunderstorm_jar_path: str
    fiji_command_template: str
    pyimagej_app_path: str
    reproducibility_mode: bool


class SmlmDockWidget(QtWidgets.QWidget):
    """Parameter panel for the ThunderSTORM-style pipeline."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._localizations: list[object] = []
        self._scroll = QtWidgets.QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._scroll)

        container = QtWidgets.QWidget()
        self._scroll.setWidget(container)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        layout.addLayout(form)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["wavelet_bspline", "dog"])
        form.addRow("Filter", self.filter_combo)

        self.backend_combo = QtWidgets.QComboBox()
        self.backend_combo.addItems(["internal", "fiji_subprocess", "fiji_pyimagej"])
        self.backend_combo.setToolTip("Select execution backend for ThunderSTORM-style localization.")
        form.addRow("Backend", self.backend_combo)

        self.plugin_combo = QtWidgets.QComboBox()
        self.plugin_combo.setToolTip("Select Fiji JAR plugin for bridge backends.")
        form.addRow("Plugin", self.plugin_combo)

        self.sigma_spin = QtWidgets.QDoubleSpinBox()
        self.sigma_spin.setRange(0.4, 6.0)
        self.sigma_spin.setDecimals(2)
        self.sigma_spin.setValue(1.3)
        form.addRow("Sigma (px)", self.sigma_spin)

        self.fit_radius_spin = QtWidgets.QSpinBox()
        self.fit_radius_spin.setRange(2, 12)
        self.fit_radius_spin.setValue(4)
        form.addRow("Fit radius (px)", self.fit_radius_spin)

        self.dog_sigma1_spin = QtWidgets.QDoubleSpinBox()
        self.dog_sigma1_spin.setRange(0.5, 5.0)
        self.dog_sigma1_spin.setDecimals(2)
        self.dog_sigma1_spin.setValue(1.0)
        form.addRow("DoG sigma1", self.dog_sigma1_spin)

        self.dog_sigma2_spin = QtWidgets.QDoubleSpinBox()
        self.dog_sigma2_spin.setRange(0.8, 8.0)
        self.dog_sigma2_spin.setDecimals(2)
        self.dog_sigma2_spin.setValue(2.0)
        form.addRow("DoG sigma2", self.dog_sigma2_spin)

        self.det_thr_spin = QtWidgets.QDoubleSpinBox()
        self.det_thr_spin.setRange(0.5, 10.0)
        self.det_thr_spin.setDecimals(2)
        self.det_thr_spin.setValue(3.0)
        form.addRow("Threshold (MAD σ)", self.det_thr_spin)

        self.max_candidates_spin = QtWidgets.QSpinBox()
        self.max_candidates_spin.setRange(100, 20000)
        self.max_candidates_spin.setValue(5000)
        form.addRow("Max candidates", self.max_candidates_spin)

        self.merge_radius_spin = QtWidgets.QDoubleSpinBox()
        self.merge_radius_spin.setRange(0.0, 5.0)
        self.merge_radius_spin.setDecimals(2)
        self.merge_radius_spin.setValue(1.0)
        form.addRow("Merge radius (px)", self.merge_radius_spin)

        self.min_photons_spin = QtWidgets.QDoubleSpinBox()
        self.min_photons_spin.setRange(0.0, 10000.0)
        self.min_photons_spin.setDecimals(1)
        self.min_photons_spin.setValue(50.0)
        form.addRow("Min photons", self.min_photons_spin)

        self.max_uncertainty_spin = QtWidgets.QDoubleSpinBox()
        self.max_uncertainty_spin.setRange(1.0, 200.0)
        self.max_uncertainty_spin.setDecimals(1)
        self.max_uncertainty_spin.setValue(30.0)
        form.addRow("Max uncertainty (nm)", self.max_uncertainty_spin)

        self.upsample_spin = QtWidgets.QSpinBox()
        self.upsample_spin.setRange(2, 16)
        self.upsample_spin.setValue(8)
        form.addRow("Upsample", self.upsample_spin)

        self.render_combo = QtWidgets.QComboBox()
        self.render_combo.addItems(["histogram", "gaussian"])
        form.addRow("Render mode", self.render_combo)

        self.render_sigma_spin = QtWidgets.QDoubleSpinBox()
        self.render_sigma_spin.setRange(1.0, 100.0)
        self.render_sigma_spin.setDecimals(1)
        self.render_sigma_spin.setValue(10.0)
        form.addRow("Render sigma (nm)", self.render_sigma_spin)

        self.fiji_exec_edit = QtWidgets.QLineEdit()
        self.fiji_exec_edit.setPlaceholderText("/path/to/Fiji.app/ImageJ-linux64")
        form.addRow("Fiji executable", self.fiji_exec_edit)

        self.fiji_macro_edit = QtWidgets.QLineEdit()
        self.fiji_macro_edit.setPlaceholderText("/path/to/thunderstorm_macro.ijm")
        form.addRow("Fiji macro/script", self.fiji_macro_edit)

        self.thunderstorm_jar_edit = QtWidgets.QLineEdit()
        self.thunderstorm_jar_edit.setPlaceholderText("/path/to/Thunder_STORM.jar")
        form.addRow("Plugin JAR", self.thunderstorm_jar_edit)

        self.fiji_command_template_edit = QtWidgets.QLineEdit()
        self.fiji_command_template_edit.setPlaceholderText(
            "{fiji_executable} --headless -macro {macro_path} "
            "'input=\"{input_tif}\",output=\"{output_csv}\",params=\"{params_json}\"'"
        )
        self.fiji_command_template_edit.setToolTip(
            "Optional override command template. Supports: {fiji_executable}, {macro_path}, "
            "{input_tif}, {output_csv}, {params_json}."
        )
        form.addRow("Fiji command template", self.fiji_command_template_edit)

        self.pyimagej_app_edit = QtWidgets.QLineEdit()
        self.pyimagej_app_edit.setPlaceholderText("/path/to/Fiji.app")
        form.addRow("PyImageJ app path", self.pyimagej_app_edit)

        self._plugin_descriptors = {}
        self._populate_plugin_list()
        self.plugin_combo.currentIndexChanged.connect(self._on_plugin_changed)
        self.backend_combo.currentIndexChanged.connect(self._refresh_effective_config)
        self.fiji_exec_edit.textChanged.connect(self._refresh_effective_config)
        self.fiji_macro_edit.textChanged.connect(self._refresh_effective_config)
        self.thunderstorm_jar_edit.textChanged.connect(self._refresh_effective_config)
        self.fiji_command_template_edit.textChanged.connect(self._refresh_effective_config)
        self.pyimagej_app_edit.textChanged.connect(self._refresh_effective_config)
        bundled = discover_bundled_thunderstorm_jar()
        if bundled is not None:
            self.thunderstorm_jar_edit.setText(str(Path(bundled)))
            self.thunderstorm_jar_edit.setToolTip(
                "Auto-detected bundled ThunderSTORM JAR. "
                "Available as PHAGE_THUNDERSTORM_JAR in bridge runs."
            )

        btn_row = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run SMLM (ROI)")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.preflight_btn = QtWidgets.QPushButton("Preflight")
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.preflight_btn)
        layout.addLayout(btn_row)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)

        self.fixit_group = QtWidgets.QGroupBox("Guided Fix")
        self.fixit_group.setVisible(False)
        fixit_layout = QtWidgets.QVBoxLayout(self.fixit_group)
        self.fixit_title_label = QtWidgets.QLabel("")
        self.fixit_title_label.setStyleSheet("font-weight: 600;")
        self.fixit_detail_label = QtWidgets.QLabel("")
        self.fixit_detail_label.setWordWrap(True)
        fixit_layout.addWidget(self.fixit_title_label)
        fixit_layout.addWidget(self.fixit_detail_label)
        self.fixit_actions_layout = QtWidgets.QHBoxLayout()
        self.fixit_actions_layout.addStretch(1)
        fixit_layout.addLayout(self.fixit_actions_layout)
        layout.addWidget(self.fixit_group)

        self.effective_config_view = QtWidgets.QPlainTextEdit()
        self.effective_config_view.setReadOnly(True)
        self.effective_config_view.setMaximumHeight(140)
        self.effective_config_view.setPlaceholderText("Effective bridge config")
        self.execution_group = QtWidgets.QGroupBox("Execution Plan / Debug")
        self.execution_group.setCheckable(True)
        self.execution_group.setChecked(False)
        execution_layout = QtWidgets.QVBoxLayout(self.execution_group)
        execution_layout.addWidget(self.effective_config_view)
        debug_btn_row = QtWidgets.QHBoxLayout()
        self.show_macro_btn = QtWidgets.QPushButton("Show Generated Macro")
        self.copy_debug_btn = QtWidgets.QPushButton("Copy Debug Report")
        debug_btn_row.addWidget(self.show_macro_btn)
        debug_btn_row.addWidget(self.copy_debug_btn)
        debug_btn_row.addStretch(1)
        execution_layout.addLayout(debug_btn_row)
        self.generated_macro_view = QtWidgets.QPlainTextEdit()
        self.generated_macro_view.setReadOnly(True)
        self.generated_macro_view.setVisible(False)
        self.generated_macro_view.setPlaceholderText("Generated/Executed macro content")
        self.generated_macro_view.setMaximumHeight(140)
        execution_layout.addWidget(self.generated_macro_view)
        layout.addWidget(self.execution_group)
        self.show_macro_btn.clicked.connect(self._toggle_generated_macro_view)
        self.copy_debug_btn.clicked.connect(self._copy_debug_report)

        runbook_row = QtWidgets.QHBoxLayout()
        self.repro_mode_chk = QtWidgets.QCheckBox("Runbook mode")
        self.lock_profile_btn = QtWidgets.QPushButton("Lock Profile")
        self.export_runbook_btn = QtWidgets.QPushButton("Export Runbook")
        runbook_row.addWidget(self.repro_mode_chk)
        runbook_row.addWidget(self.lock_profile_btn)
        runbook_row.addWidget(self.export_runbook_btn)
        runbook_row.addStretch(1)
        layout.addLayout(runbook_row)

        color_row = QtWidgets.QHBoxLayout()
        color_row.addWidget(QtWidgets.QLabel("Color by"))
        self.color_mode_combo = QtWidgets.QComboBox()
        self.color_mode_combo.addItems(["Photons", "Uncertainty"])
        color_row.addWidget(self.color_mode_combo)
        color_row.addStretch(1)
        layout.addLayout(color_row)

        export_row = QtWidgets.QHBoxLayout()
        self.export_csv_btn = QtWidgets.QPushButton("Export CSV")
        self.export_h5_btn = QtWidgets.QPushButton("Export HDF5")
        self.add_ann_btn = QtWidgets.QPushButton("Add to Annotations")
        self.add_ann_btn.setEnabled(False)
        export_row.addWidget(self.export_csv_btn)
        export_row.addWidget(self.export_h5_btn)
        export_row.addWidget(self.add_ann_btn)
        layout.addLayout(export_row)

        results_group = QtWidgets.QGroupBox("Localization Results")
        results_layout = QtWidgets.QVBoxLayout(results_group)
        summary_row = QtWidgets.QHBoxLayout()
        self.results_summary_lbl = QtWidgets.QLabel("No localizations yet.")
        summary_row.addWidget(self.results_summary_lbl)
        summary_row.addStretch(1)
        self.show_points_chk = QtWidgets.QCheckBox("Show as points on canvas")
        self.show_points_chk.setChecked(True)
        summary_row.addWidget(self.show_points_chk)
        results_layout.addLayout(summary_row)

        self.results_table = QtWidgets.QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["Frame", "X (px)", "Y (px)", "Sigma", "Photons", "Uncertainty"]
        )
        self.results_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(self.results_table)

        results_btn_row = QtWidgets.QHBoxLayout()
        self.copy_results_btn = QtWidgets.QPushButton("Copy Rows")
        self.select_all_results_btn = QtWidgets.QPushButton("Select All")
        self.clear_selection_btn = QtWidgets.QPushButton("Clear Selection")
        results_btn_row.addWidget(self.copy_results_btn)
        results_btn_row.addWidget(self.select_all_results_btn)
        results_btn_row.addWidget(self.clear_selection_btn)
        results_btn_row.addStretch(1)
        results_layout.addLayout(results_btn_row)
        layout.addWidget(results_group)

        layout.addStretch(1)
        self.results_table.itemSelectionChanged.connect(self._update_selection_state)
        self.results_table.customContextMenuRequested.connect(self._open_results_context_menu)
        self.copy_results_btn.clicked.connect(self._copy_selected_results)
        self.select_all_results_btn.clicked.connect(self.results_table.selectAll)
        self.clear_selection_btn.clicked.connect(self.results_table.clearSelection)
        self._refresh_effective_config()

    def values(self) -> SmlmUiValues:
        """Return a typed snapshot of the current UI values."""
        return SmlmUiValues(
            sigma_px=float(self.sigma_spin.value()),
            fit_radius_px=int(self.fit_radius_spin.value()),
            filter_type=str(self.filter_combo.currentText()),
            dog_sigma1=float(self.dog_sigma1_spin.value()),
            dog_sigma2=float(self.dog_sigma2_spin.value()),
            detection_thr_sigma=float(self.det_thr_spin.value()),
            max_candidates_per_frame=int(self.max_candidates_spin.value()),
            merge_radius_px=float(self.merge_radius_spin.value()),
            min_photons=float(self.min_photons_spin.value()),
            max_uncertainty_nm=float(self.max_uncertainty_spin.value()),
            upsample=int(self.upsample_spin.value()),
            render_mode=str(self.render_combo.currentText()),
            render_sigma_nm=float(self.render_sigma_spin.value()),
            backend=str(self.backend_combo.currentText()),
            plugin_id=str(self.plugin_combo.currentData() or ""),
            fiji_executable=str(self.fiji_exec_edit.text()).strip(),
            fiji_macro_path=str(self.fiji_macro_edit.text()).strip(),
            plugin_jar_path=str(self.thunderstorm_jar_edit.text()).strip(),
            thunderstorm_jar_path=str(self.thunderstorm_jar_edit.text()).strip(),
            fiji_command_template=str(self.fiji_command_template_edit.text()).strip(),
            pyimagej_app_path=str(self.pyimagej_app_edit.text()).strip(),
            reproducibility_mode=bool(self.repro_mode_chk.isChecked()),
        )

    def _populate_plugin_list(self) -> None:
        current_id = str(self.plugin_combo.currentData() or "")
        self.plugin_combo.blockSignals(True)
        self.plugin_combo.clear()
        self._plugin_descriptors = {}
        discovered = discover_external_fiji_plugins()
        if not discovered:
            self.plugin_combo.addItem("None (manual jar path)", "")
        for plugin in discovered:
            if not bool(getattr(plugin, "ui_visible", True)):
                continue
            label = f"{plugin.name} ({plugin.plugin_id})"
            self.plugin_combo.addItem(label, plugin.plugin_id)
            self._plugin_descriptors[plugin.plugin_id] = plugin
        idx = self.plugin_combo.findData(current_id)
        if idx >= 0:
            self.plugin_combo.setCurrentIndex(idx)
        elif self.plugin_combo.count() > 0:
            self.plugin_combo.setCurrentIndex(0)
        self.plugin_combo.blockSignals(False)
        self._on_plugin_changed(self.plugin_combo.currentIndex())

    def _on_plugin_changed(self, _index: int) -> None:
        plugin_id = str(self.plugin_combo.currentData() or "")
        if not plugin_id:
            return
        plugin = self._plugin_descriptors.get(plugin_id)
        if plugin is None:
            return
        if plugin.jar_path:
            self.thunderstorm_jar_edit.setText(plugin.jar_path)
        if plugin.macro_path and not self.fiji_macro_edit.text().strip():
            self.fiji_macro_edit.setText(plugin.macro_path)
        self._refresh_effective_config()

    def _refresh_effective_config(self, *_args) -> None:
        if not hasattr(self, "effective_config_view"):
            return
        plugin_id = str(self.plugin_combo.currentData() or "")
        plugin_label = self.plugin_combo.currentText() or "(none)"
        plugin = self._plugin_descriptors.get(plugin_id)
        macro_text = self.fiji_macro_edit.text().strip()
        macro_source = "user-supplied"
        if not macro_text:
            if plugin is not None and plugin.macro_path:
                macro_source = "bundled default"
            elif plugin is not None and plugin.manifest is not None:
                macro_source = "generated-from-manifest"
            else:
                macro_source = "missing"
        lines = [
            f"backend={self.backend_combo.currentText()}",
            f"plugin={plugin_label}",
            f"plugin_id={plugin_id}",
            f"fiji_executable={self.fiji_exec_edit.text().strip()}",
            f"macro_path={macro_text or '<auto-resolved>'}",
            f"macro_source={macro_source}",
            f"plugin_jar={self.thunderstorm_jar_edit.text().strip()}",
            f"pyimagej_app={self.pyimagej_app_edit.text().strip()}",
            "timeout_sec=900",
            f"generated_at={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        if plugin is not None and plugin.command_names:
            lines.append(f"plugin_commands={', '.join(plugin.command_names[:2])}")
        if plugin is not None and plugin.manifest is not None:
            manifest = plugin.manifest
            lines.append(f"plugin_version_tested={manifest.plugin_version_tested or 'n/a'}")
            lines.append(f"csv_schema_version={manifest.csv_schema_version or 'n/a'}")
            if manifest.required_columns:
                lines.append(f"required_columns={', '.join(manifest.required_columns)}")
        template = self.fiji_command_template_edit.text().strip()
        lines.append("command_template=custom" if template else "command_template=default")
        self.effective_config_view.setPlainText("\n".join(lines))

    def _toggle_generated_macro_view(self) -> None:
        visible = not self.generated_macro_view.isVisible()
        self.generated_macro_view.setVisible(visible)
        self.show_macro_btn.setText("Hide Generated Macro" if visible else "Show Generated Macro")

    def _copy_debug_report(self) -> None:
        lines = [self.effective_config_view.toPlainText().strip()]
        macro = self.generated_macro_view.toPlainText().strip()
        if macro:
            lines.append("=== GENERATED_MACRO ===")
            lines.append(macro)
        text = "\n\n".join([part for part in lines if part])
        QtWidgets.QApplication.clipboard().setText(text)

    def append_debug_report(self, text: str) -> None:
        """Append diagnostics to execution plan panel."""
        existing = self.effective_config_view.toPlainText().strip()
        prefix = f"{existing}\n\n" if existing else ""
        self.effective_config_view.setPlainText(prefix + text.strip())

    def set_localizations(self, localizations: Iterable[object]) -> None:
        """Render the current ThunderSTORM results as a selectable table."""
        self._localizations = list(localizations or [])
        self.results_table.setRowCount(len(self._localizations))
        for row, loc in enumerate(self._localizations):
            values = [
                int(getattr(loc, "frame_index", 0)),
                float(getattr(loc, "x_px", 0.0)),
                float(getattr(loc, "y_px", 0.0)),
                float(getattr(loc, "sigma_px", 0.0)),
                float(getattr(loc, "photons", 0.0)),
                float(getattr(loc, "uncertainty_px", 0.0)),
            ]
            for col, value in enumerate(values):
                text = str(value) if col == 0 else f"{value:.4f}"
                item = QtWidgets.QTableWidgetItem(text)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, row)
                self.results_table.setItem(row, col, item)
        self.results_table.resizeColumnsToContents()
        count = len(self._localizations)
        self.results_summary_lbl.setText(f"{count} localizations available.")
        self._update_selection_state()

    def clear_localizations(self) -> None:
        self._localizations = []
        self.results_table.setRowCount(0)
        self.results_summary_lbl.setText("No localizations yet.")
        self._update_selection_state()

    def selected_localization_indices(self) -> list[int]:
        rows = sorted({index.row() for index in self.results_table.selectionModel().selectedRows()})
        return [row for row in rows if 0 <= row < len(self._localizations)]

    def selected_localizations(self) -> list[object]:
        return [self._localizations[row] for row in self.selected_localization_indices()]

    def export_localizations_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "frame_index",
                    "x_px",
                    "y_px",
                    "sigma_px",
                    "photons",
                    "background",
                    "uncertainty_px",
                    "label",
                ]
            )
            for loc in self._localizations:
                writer.writerow(
                    [
                        int(getattr(loc, "frame_index", 0)),
                        f"{float(getattr(loc, 'x_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'y_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'sigma_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'photons', 0.0)):.4f}",
                        f"{float(getattr(loc, 'background', 0.0)):.4f}",
                        f"{float(getattr(loc, 'uncertainty_px', 0.0)):.4f}",
                        str(getattr(loc, "label", "") or ""),
                    ]
                )

    def _update_selection_state(self) -> None:
        total = len(self._localizations)
        selected = len(self.selected_localization_indices())
        if total == 0:
            self.add_ann_btn.setEnabled(False)
            self.add_ann_btn.setText("Add to Annotations")
            return
        if selected > 0:
            self.results_summary_lbl.setText(f"{total} localizations available | {selected} selected")
            self.add_ann_btn.setEnabled(True)
            self.add_ann_btn.setText(f"Add Selected ({selected})")
        else:
            self.results_summary_lbl.setText(f"{total} localizations available.")
            self.add_ann_btn.setEnabled(True)
            self.add_ann_btn.setText(f"Add All ({total})")

    def _copy_selected_results(self) -> None:
        indices = self.selected_localization_indices()
        if not indices:
            return
        lines = ["frame_index\tx_px\ty_px\tsigma_px\tphotons\tuncertainty_px"]
        for row in indices:
            loc = self._localizations[row]
            lines.append(
                "\t".join(
                    [
                        str(int(getattr(loc, "frame_index", 0))),
                        f"{float(getattr(loc, 'x_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'y_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'sigma_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'photons', 0.0)):.4f}",
                        f"{float(getattr(loc, 'uncertainty_px', 0.0)):.4f}",
                    ]
                )
            )
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))

    def _open_results_context_menu(self, pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        copy_act = menu.addAction("Copy Selected")
        select_all_act = menu.addAction("Select All")
        clear_sel_act = menu.addAction("Clear Selection")
        chosen = menu.exec_(self.results_table.viewport().mapToGlobal(pos))
        if chosen is copy_act:
            self._copy_selected_results()
        elif chosen is select_all_act:
            self.results_table.selectAll()
        elif chosen is clear_sel_act:
            self.results_table.clearSelection()

    def set_generated_macro(self, macro_text: str) -> None:
        """Set generated/executed macro text in debug panel."""
        self.generated_macro_view.setPlainText((macro_text or "").strip())

    def clear_fixit_card(self) -> None:
        """Hide and clear guided fix card."""
        self._clear_fixit_buttons()
        self.fixit_title_label.setText("")
        self.fixit_detail_label.setText("")
        self.fixit_group.setVisible(False)

    def set_fixit_card(
        self,
        *,
        title: str,
        detail: str,
        actions: list[tuple[str, Callable[[], None]]],
    ) -> None:
        """Show guided fix card with actionable buttons."""
        self._clear_fixit_buttons()
        self.fixit_title_label.setText(title.strip())
        self.fixit_detail_label.setText(detail.strip())
        for label, handler in actions:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(handler)
            self.fixit_actions_layout.addWidget(btn)
        self.fixit_actions_layout.addStretch(1)
        self.fixit_group.setVisible(True)

    def _clear_fixit_buttons(self) -> None:
        while self.fixit_actions_layout.count():
            item = self.fixit_actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
