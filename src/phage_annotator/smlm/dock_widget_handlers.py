"""Extracted method group 2 for SmlmDockWidget."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins




class DockWidgetHandlersMixin:
    """Method group 2 extracted from SmlmDockWidget."""

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
        """Handle the populate plugin list helper flow."""
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
        """Handle the on plugin changed helper flow."""
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
        """Refresh effective config for the current workflow."""
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
        """Toggle generated macro view for the current workflow."""
        visible = not self.generated_macro_view.isVisible()
        self.generated_macro_view.setVisible(visible)
        self.show_macro_btn.setText("Hide Generated Macro" if visible else "Show Generated Macro")
    def _copy_debug_report(self) -> None:
        """Copy debug report for the current workflow."""
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
        """Clear localizations for the current workflow."""
        self._localizations = []
        self.results_table.setRowCount(0)
        self.results_summary_lbl.setText("No localizations yet.")
        self._update_selection_state()
    def selected_localization_indices(self) -> list[int]:
        """Run the selected localization indices workflow."""
        rows = sorted({index.row() for index in self.results_table.selectionModel().selectedRows()})
        return [row for row in rows if 0 <= row < len(self._localizations)]
    def selected_localizations(self) -> list[object]:
        """Run the selected localizations workflow."""
        return [self._localizations[row] for row in self.selected_localization_indices()]
