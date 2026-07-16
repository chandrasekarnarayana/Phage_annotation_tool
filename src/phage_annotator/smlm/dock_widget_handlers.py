"""Event handler mixin and UI-value snapshot for the SMLM parameter panel."""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.backends_discovery import discover_thunderstorm_jar_in_fiji
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins
from phage_annotator.smlm.fiji_downloader import (
    download_fiji,
    install_thunderstorm_jar,
    resolve_fiji_plugins_dir,
)
from phage_annotator.smlm.platform_utils import (
    discover_fiji_executable,
    fiji_app_to_executable,
)


@dataclass
class SmlmUiValues:
    """Typed snapshot of all SMLM panel parameter values.

    Instances are created by :meth:`DockWidgetHandlersMixin.values` and
    passed directly to the analysis backend. All physical-unit fields carry
    their unit in the field name (``_px``, ``_nm``) to prevent silent
    conversion errors.
    """

    # Acquisition
    pixel_size_nm: float
    em_wavelength_nm: int

    # Filter
    sigma_px: float
    fit_radius_px: int
    filter_type: str
    dog_sigma1: float
    dog_sigma2: float

    # Detection
    detection_thr_sigma: float
    max_candidates_per_frame: int

    # Post-filter
    merge_radius_px: float
    min_photons: float
    max_uncertainty_nm: float

    # Rendering
    upsample: int
    render_mode: str
    render_sigma_nm: float

    # Backend / bridge
    backend: str
    plugin_id: str
    fiji_executable: str
    fiji_macro_path: str
    plugin_jar_path: str
    thunderstorm_jar_path: str
    fiji_command_template: str
    pyimagej_app_path: str

    # Reproducibility
    reproducibility_mode: bool


class DockWidgetHandlersMixin:
    """Event handlers and data-access helpers for the SMLM parameter panel."""

    def values(self) -> SmlmUiValues:
        """Return a typed snapshot of the current UI parameter values."""
        return SmlmUiValues(
            # Acquisition
            pixel_size_nm=float(self.pixel_size_spin.value()),
            em_wavelength_nm=int(self.em_wavelength_spin.value()),
            # Filter
            sigma_px=float(self.sigma_spin.value()),
            fit_radius_px=int(self.fit_radius_spin.value()),
            filter_type=str(self.filter_combo.currentData() or self.filter_combo.currentText()),
            dog_sigma1=float(self.dog_sigma1_spin.value()),
            dog_sigma2=float(self.dog_sigma2_spin.value()),
            # Detection
            detection_thr_sigma=float(self.det_thr_spin.value()),
            max_candidates_per_frame=int(self.max_candidates_spin.value()),
            # Post-filter
            merge_radius_px=float(self.merge_radius_spin.value()),
            min_photons=float(self.min_photons_spin.value()),
            max_uncertainty_nm=float(self.max_uncertainty_spin.value()),
            # Rendering
            upsample=int(self.upsample_spin.value()),
            render_mode=str(self.render_combo.currentData() or self.render_combo.currentText()),
            render_sigma_nm=float(self.render_sigma_spin.value()),
            # Backend
            backend=str(self.backend_combo.currentData() or self.backend_combo.currentText()),
            plugin_id=str(self.plugin_combo.currentData() or ""),
            fiji_executable=str(self.fiji_exec_edit.text()).strip(),
            fiji_macro_path=str(self.fiji_macro_edit.text()).strip(),
            plugin_jar_path=str(self.thunderstorm_jar_edit.text()).strip(),
            thunderstorm_jar_path=str(self.thunderstorm_jar_edit.text()).strip(),
            fiji_command_template=str(self.fiji_command_template_edit.text()).strip(),
            pyimagej_app_path=str(self.pyimagej_app_edit.text()).strip(),
            # Reproducibility
            reproducibility_mode=bool(self.repro_mode_chk.isChecked()),
        )

    def _populate_plugin_list(self) -> None:
        current_id = str(self.plugin_combo.currentData() or "")
        self.plugin_combo.blockSignals(True)
        self.plugin_combo.clear()
        self._plugin_descriptors = {}
        discovered = discover_external_fiji_plugins()
        if not discovered:
            self.plugin_combo.addItem("None (manual JAR path)", "")
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
        if not macro_text:
            if plugin is not None and plugin.macro_path:
                macro_source = "bundled default"
            elif plugin is not None and getattr(plugin, "manifest", None) is not None:
                macro_source = "generated-from-manifest"
            else:
                macro_source = "missing"
        else:
            macro_source = "user-supplied"
        lines = [
            f"backend={self.backend_combo.currentData() or self.backend_combo.currentText()}",
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
        if plugin is not None and getattr(plugin, "manifest", None) is not None:
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
        self.show_macro_btn.setText(
            "Hide Generated Macro" if visible else "Show Generated Macro"
        )

    def _copy_debug_report(self) -> None:
        lines = [self.effective_config_view.toPlainText().strip()]
        macro = self.generated_macro_view.toPlainText().strip()
        if macro:
            lines.append("=== GENERATED_MACRO ===")
            lines.append(macro)
        text = "\n\n".join([p for p in lines if p])
        QtWidgets.QApplication.clipboard().setText(text)

    def append_debug_report(self, text: str) -> None:
        """Append diagnostics text to the execution plan panel."""
        existing = self.effective_config_view.toPlainText().strip()
        prefix = f"{existing}\n\n" if existing else ""
        self.effective_config_view.setPlainText(prefix + text.strip())

    def set_localizations(self, localizations: Iterable[object]) -> None:
        """Populate the results table with a new set of localisation objects."""
        self._localizations = list(localizations or [])
        self.results_table.setRowCount(len(self._localizations))
        pixel_size = float(getattr(self, "pixel_size_spin", None) and self.pixel_size_spin.value() or 100.0)
        for row, loc in enumerate(self._localizations):
            unc_px = float(getattr(loc, "uncertainty_px", 0.0))
            unc_nm = unc_px * pixel_size
            merged = bool(getattr(loc, "merged", False))
            cells = [
                (int(getattr(loc, "frame_index", 0)), "{}"),
                (float(getattr(loc, "x_px", 0.0)), "{:.3f}"),
                (float(getattr(loc, "y_px", 0.0)), "{:.3f}"),
                (float(getattr(loc, "sigma_px", 0.0)), "{:.3f}"),
                (float(getattr(loc, "photons", 0.0)), "{:.1f}"),
                (unc_nm, "{:.2f}"),
                ("Yes" if merged else "No", "{}"),
            ]
            for col, (value, fmt) in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(fmt.format(value))
                item.setData(QtCore.Qt.ItemDataRole.UserRole, row)
                self.results_table.setItem(row, col, item)
        self.results_table.resizeColumnsToContents()
        count = len(self._localizations)
        self.results_summary_lbl.setText(f"{count:,} localisation{'s' if count != 1 else ''} accepted.")
        self._update_selection_state()

    def clear_localizations(self) -> None:
        """Clear the localisation results table."""
        self._localizations = []
        self.results_table.setRowCount(0)
        self.results_summary_lbl.setText("No localisations yet.")
        self._update_selection_state()

    def selected_localization_indices(self) -> list:
        rows = sorted({i.row() for i in self.results_table.selectionModel().selectedRows()})
        return [r for r in rows if 0 <= r < len(self._localizations)]

    def selected_localizations(self) -> list:
        return [self._localizations[r] for r in self.selected_localization_indices()]

    def _update_selection_state(self) -> None:
        has_sel = bool(self.selected_localization_indices())
        if hasattr(self, "copy_results_btn"):
            self.copy_results_btn.setEnabled(has_sel)
        if hasattr(self, "add_ann_btn"):
            self.add_ann_btn.setEnabled(has_sel)

    def _copy_selected_results(self) -> None:
        rows = self.selected_localization_indices()
        if not rows:
            return
        headers = ["Frame", "X (px)", "Y (px)", "Sigma (px)", "Photons", "Uncertainty (nm)", "Merged"]
        lines = ["\t".join(headers)]
        for row in rows:
            cells = []
            for col in range(self.results_table.columnCount()):
                item = self.results_table.item(row, col)
                cells.append(item.text() if item else "")
            lines.append("\t".join(cells))
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))

    def _open_results_context_menu(self, pos) -> None:
        menu = QtWidgets.QMenu(self)
        copy_action = menu.addAction("Copy selected rows")
        sel_action = menu.addAction("Select all")
        copy_action.triggered.connect(self._copy_selected_results)
        sel_action.triggered.connect(self.results_table.selectAll)
        menu.exec(self.results_table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Fiji / ThunderSTORM find & download handlers
    # ------------------------------------------------------------------

    def _handle_find_fiji(self) -> None:
        """Search for a Fiji installation on this system and populate the field."""
        user_hint = self.fiji_exec_edit.text().strip() or None
        extra: list[str] = []
        if user_hint:
            # If user typed a path, also search the parent dir as a Fiji.app hint
            p = Path(user_hint)
            for ancestor in (p, p.parent, p.parent.parent):
                if ancestor.is_dir():
                    extra.append(str(ancestor))
        exe = discover_fiji_executable(extra_dirs=extra or None)
        if exe:
            self.fiji_exec_edit.setText(exe)
            self.fiji_status_lbl.setText(f"Found: {exe}")
            QtWidgets.QMessageBox.information(self, "Fiji found", f"Fiji detected at:\n{exe}")
        else:
            self.fiji_status_lbl.setText("Not found on this system.")
            QtWidgets.QMessageBox.warning(
                self,
                "Fiji not found",
                "Fiji could not be located automatically.\n\n"
                "Options:\n"
                "• Browse to the Fiji executable manually.\n"
                "• Click 'Download' to fetch Fiji from downloads.imagej.net.\n"
                "• Set the FIJI_EXECUTABLE or FIJI_APP environment variable.",
            )

    def _handle_download_fiji(self) -> None:
        """Download Fiji from the internet and populate the executable field."""
        progress = QtWidgets.QProgressDialog("Downloading Fiji…", "Cancel", 0, 100, self)
        progress.setWindowTitle("Downloading Fiji")
        progress.setMinimumDuration(0)
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setValue(0)

        result: dict = {}
        cancelled = threading.Event()

        def _progress_cb(done: int, total: int) -> None:
            if cancelled.is_set():
                return
            if total > 0:
                pct = int(done * 100 / total)
            else:
                pct = min(99, int(done / (1024 * 1024)))
            QtCore.QMetaObject.invokeMethod(
                progress, "setValue", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(int, pct),
            )

        def _worker() -> None:
            try:
                exe = download_fiji(progress_cb=_progress_cb)
                result["exe"] = exe
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)

        progress.canceled.connect(lambda: cancelled.set())
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        while t.is_alive():
            QtWidgets.QApplication.processEvents()
            t.join(timeout=0.1)
            if progress.wasCanceled():
                cancelled.set()
                progress.close()
                return

        progress.setValue(100)
        progress.close()

        if "error" in result:
            QtWidgets.QMessageBox.critical(
                self, "Download failed",
                f"Could not download Fiji:\n{result['error']}\n\n"
                "Check your internet connection and try again.",
            )
        elif "exe" in result:
            exe = result["exe"]
            self.fiji_exec_edit.setText(exe)
            self.fiji_status_lbl.setText(f"Downloaded: {exe}")
            QtWidgets.QMessageBox.information(
                self, "Fiji downloaded", f"Fiji installed to:\n{exe}"
            )

    def _handle_find_thunderstorm_jar(self) -> None:
        """Find or install ThunderSTORM JAR and populate the field.

        Search order:
        1. Already installed in Fiji.app/plugins/ — use it directly.
        2. Bundled JAR in external_plugins/ — copy it into Fiji.app/plugins/
           (so Fiji can find it) and use that path.
        3. Neither found — prompt the user to download.
        """
        fiji_exe = self.fiji_exec_edit.text().strip() or None

        # 1. Search inside the configured Fiji installation
        if fiji_exe:
            plugins_dir = resolve_fiji_plugins_dir(fiji_exe)
            fiji_app_path = str(plugins_dir.parent) if plugins_dir else None
            jar = discover_thunderstorm_jar_in_fiji(fiji_app_path) if fiji_app_path else None
            if jar:
                self.thunderstorm_jar_edit.setText(jar)
                self.jar_status_lbl.setText(f"Found: {jar}")
                QtWidgets.QMessageBox.information(
                    self, "ThunderSTORM found", f"ThunderSTORM JAR detected at:\n{jar}"
                )
                return

        # 2. Bundled JAR available — copy it into Fiji.app/plugins/ if possible
        bundled = discover_bundled_thunderstorm_jar()
        if bundled:
            try:
                jar = install_thunderstorm_jar(fiji_exe=fiji_exe, src_jar=Path(str(bundled)))
            except Exception as exc:  # noqa: BLE001
                # Copy failed (e.g. read-only Fiji dir) — use bundled path directly
                jar = str(bundled)
                self.jar_status_lbl.setText(f"Bundled (in-place): {jar}")
                self.thunderstorm_jar_edit.setText(jar)
                QtWidgets.QMessageBox.warning(
                    self, "Copy failed",
                    f"Could not copy bundled JAR into Fiji plugins:\n{exc}\n\n"
                    f"Using bundled path directly:\n{jar}",
                )
                return
            self.thunderstorm_jar_edit.setText(jar)
            if fiji_exe and resolve_fiji_plugins_dir(fiji_exe) and \
                    str(resolve_fiji_plugins_dir(fiji_exe)) in jar:
                self.jar_status_lbl.setText(f"Installed into Fiji: {jar}")
                QtWidgets.QMessageBox.information(
                    self, "ThunderSTORM installed",
                    f"Bundled ThunderSTORM JAR copied into Fiji plugins:\n{jar}\n\n"
                    "Fiji will find it automatically on next run."
                )
            else:
                self.jar_status_lbl.setText(f"Bundled: {jar}")
            return

        # 3. Nothing found — prompt download
        self.jar_status_lbl.setText("Not found — click 'Download'.")
        QtWidgets.QMessageBox.warning(
            self,
            "ThunderSTORM not found",
            "ThunderSTORM JAR was not found on this system.\n\n"
            "Click 'Download' to fetch it from GitHub.\n"
            "It will be placed in Fiji.app/plugins/ automatically if Fiji is configured.",
        )

    def _handle_download_thunderstorm_jar(self) -> None:
        """Download ThunderSTORM JAR from GitHub and install it where Fiji expects it.

        If a Fiji executable is configured the JAR is placed directly in
        ``Fiji.app/plugins/`` so Fiji picks it up without any manual copy.
        Otherwise it is saved to the user application data directory.
        """
        fiji_exe = self.fiji_exec_edit.text().strip() or None
        plugins_dir = resolve_fiji_plugins_dir(fiji_exe) if fiji_exe else None
        dest_label = str(plugins_dir) if plugins_dir else "user data folder"

        progress = QtWidgets.QProgressDialog(
            f"Downloading ThunderSTORM JAR to {dest_label}…", "Cancel", 0, 100, self
        )
        progress.setWindowTitle("Downloading ThunderSTORM")
        progress.setMinimumDuration(0)
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setValue(0)

        result: dict = {}
        cancelled = threading.Event()

        def _progress_cb(done: int, total: int) -> None:
            if cancelled.is_set():
                return
            if total > 0:
                pct = int(done * 100 / total)
            else:
                pct = min(99, int(done / (1024 * 1024)))
            QtCore.QMetaObject.invokeMethod(
                progress, "setValue", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(int, pct),
            )

        def _worker() -> None:
            try:
                jar = install_thunderstorm_jar(fiji_exe=fiji_exe, progress_cb=_progress_cb)
                result["jar"] = jar
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)

        progress.canceled.connect(lambda: cancelled.set())
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        while t.is_alive():
            QtWidgets.QApplication.processEvents()
            t.join(timeout=0.1)
            if progress.wasCanceled():
                cancelled.set()
                progress.close()
                return

        progress.setValue(100)
        progress.close()

        if "error" in result:
            QtWidgets.QMessageBox.critical(
                self, "Download failed",
                f"Could not download ThunderSTORM JAR:\n{result['error']}\n\n"
                "Check your internet connection and try again.",
            )
        elif "jar" in result:
            jar = result["jar"]
            self.thunderstorm_jar_edit.setText(jar)
            self.jar_status_lbl.setText(f"Installed: {jar}")
            if plugins_dir and str(plugins_dir) in jar:
                msg = (
                    f"ThunderSTORM JAR installed in Fiji plugins:\n{jar}\n\n"
                    "Fiji will find it automatically — no manual copy needed."
                )
            else:
                msg = (
                    f"ThunderSTORM JAR saved to:\n{jar}\n\n"
                    "Configure a Fiji executable above so the JAR can be placed "
                    "in Fiji.app/plugins/ automatically next time."
                )
            QtWidgets.QMessageBox.information(self, "ThunderSTORM installed", msg)
