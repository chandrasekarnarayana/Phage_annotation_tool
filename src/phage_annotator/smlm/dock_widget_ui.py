"""Extracted method group 1 for SmlmDockWidget."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins




class DockWidgetUiMixin:
    """Method group 1 extracted from SmlmDockWidget."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize the object and prepare its runtime state."""
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
