"""Menu and dialog actions for the GUI."""

from __future__ import annotations

import gc
import pathlib
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtGui, QtWidgets

from phage_annotator.analysis import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.gui_debug import debug_log
from phage_annotator.gui_image_io import read_metadata
from phage_annotator.lut_manager import lut_names
from phage_annotator.metadata_reader import MetadataBundle


class ActionsMixin:
    """Mixin for File/View/Analyze actions and dialogs."""

    def _open_files(self) -> None:
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_files(self)
        if paths:
            self.recorder.record("open_files", {"count": len(paths)})
            self._open_files_from_paths(paths)

    def _open_folder(self) -> None:
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_folder(self)
        if paths:
            self.recorder.record("open_folder", {"count": len(paths)})
            # Load metadata for all files in the background with progress + cancel (P1.3)
            files = list(paths)

            def _worker(progress, cancel):
                from phage_annotator.gui_image_io import read_metadata

                metas = []
                total = len(files)
                for idx, p in enumerate(files):
                    if cancel.is_cancelled():
                        return None
                    meta = read_metadata(p)
                    metas.append(meta)
                    progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
                return metas

            def _on_result(result):
                if not result:
                    return
                new_images = result
                # Add images and update UI on GUI thread
                self.controller.add_images(new_images)
                for meta in new_images:
                    self.fov_list.addItem(meta.name)
                    self.primary_combo.addItem(meta.name)
                    self.support_combo.addItem(meta.name)
                    self.roi_manager.rois_by_image[meta.id] = []
                # Build annotation index (lightweight) and update availability
                try:
                    self.controller.build_annotation_index(files[0].parent)
                except Exception:
                    pass
                self._refresh_annotation_availability()
                self._refresh_roi_manager()
                self._refresh_metadata_dock(self.primary_image.id)
                self._refresh_image()
                self._maybe_autoload_annotations(self.primary_image.id)

            self.jobs.submit(
                _worker,
                name="Open folder",
                on_result=_on_result,
                timeout_sec=300.0,
                retries=2,
                retry_delay_sec=1.0,
            )

    def _reset_confirmations(self) -> None:
        """Reset all confirmation prompts to enabled (P3.3)."""
        self._settings.setValue("confirmApplyDisplayMapping", True)
        self._settings.setValue("confirmApplyThreshold", True)
        self._settings.setValue("confirmClearROI", True)
        self._settings.setValue("confirmDeleteAnnotations", True)
        self._settings.setValue("confirmOverwriteFile", True)
        QtWidgets.QMessageBox.information(
            self,
            "Confirmations Reset",
            "All confirmation prompts have been re-enabled.\n\nYou will now be asked before:\n• Applying display settings\n• Applying threshold\n• Clearing ROI\n• Deleting annotations\n• Overwriting files"
        )

    def _load_annotations_current(self) -> None:
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            force_image_id=self.primary_image.id,
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._refresh_image()

    def _load_annotations_multi(self) -> None:
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(self, self.primary_image.id, pixel_size_nm=pixel_size_nm)
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._refresh_image()

    def _load_annotations_all(self) -> None:
        targets = []
        for img in self.images:
            if self.controller.annotation_entries_for_image(img.id):
                targets.append(img.id)
        if not targets:
            QtWidgets.QMessageBox.information(
                self, "No annotations", "No indexed annotations were found."
            )
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None

        def _worker(progress, cancel):
            results = {}
            imports = []
            total = len(targets)
            for idx, image_id in enumerate(targets):
                if cancel.is_cancelled():
                    return None
                paths = [
                    entry.path for entry in self.controller.annotation_entries_for_image(image_id)
                ]
                points, import_entries = self.controller._parse_annotations_from_paths(
                    paths,
                    image_id=image_id,
                    pixel_size_nm=pixel_size_nm,
                    force_image_id=image_id,
                )
                results[image_id] = points
                imports.extend(import_entries)
                progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
            return (results, imports)

        def _on_result(result):
            if not result:
                return
            results, imports = result
            self.controller._record_annotation_imports(imports)
            for image_id, points in results.items():
                if self.controller.annotations_are_loaded(image_id):
                    self.controller.merge_annotations(image_id, points)
                else:
                    self.controller.replace_annotations(image_id, points)
            meta = None
            for target_id, entry in imports:
                if target_id == self.primary_image.id:
                    meta = entry.get("meta")
                    if isinstance(meta, dict) and meta:
                        break
            if meta:
                self._handle_annotation_metadata(self.primary_image.id, meta)
            self._mark_dirty()
            self.controller.annotations_changed.emit()
            self._refresh_image()

        self.jobs.submit(
            _worker,
            name="Load all annotations",
            on_result=_on_result,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
        )

    def _reload_annotations_current(self) -> None:
        image_id = self.primary_image.id
        if not self.controller.annotation_entries_for_image(image_id):
            self._load_annotations_current()
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=True, pixel_size_nm=pixel_size_nm)

    def _toggle_profile_panel(self) -> None:
        self.profile_chk.setChecked(not self.profile_chk.isChecked())

    def _toggle_hist_panel(self) -> None:
        self.hist_chk.setChecked(not self.hist_chk.isChecked())

    def _toggle_left_pane(self) -> None:
        if self.dock_annotations is None:
            return
        self.dock_annotations.setVisible(not self.dock_annotations.isVisible())

    def _toggle_settings_pane(self) -> None:
        self.settings_advanced_container.setVisible(
            not self.settings_advanced_container.isVisible()
        )

    def _on_link_zoom_menu(self) -> None:
        self.link_zoom = self.link_zoom_act.isChecked()
        if not self.link_zoom:
            # reset last linked to avoid forcing 0-1 ranges
            self._last_zoom_linked = None
        self._refresh_image()

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "About Phage Annotator",
            "Phage Annotator\nMatplotlib + Qt GUI for microscopy keypoint annotation.\nFive synchronized panels, ROI, autoplay, lazy loading.",
        )

    def _show_keyboard_shortcuts(self) -> None:
        """Show keyboard shortcuts reference dialog."""
        from phage_annotator.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
        dialog = KeyboardShortcutsDialog(self)
        dialog.exec()


    def _show_profile_dialog(self) -> None:
        """Open a dialog showing line profiles (vertical, horizontal, diagonals) raw vs corrected."""
        if self.primary_image.array is None:
            return
        data = self._apply_crop(self._slice_data(self.primary_image))
        h, w = data.shape
        cy, cx = h // 2, w // 2
        vertical = data[:, cx]
        horizontal = data[cy, :]
        diag1 = np.diag(data)
        diag2 = np.diag(np.fliplr(data))

        def _correct(arr: np.ndarray) -> np.ndarray:
            if self.illum_corr_chk.isChecked():
                arr = arr - arr.min()
            if arr.max() > 0:
                arr = arr / arr.max()
            return arr

        fig, axes = plt.subplots(2, 2, figsize=(10, 6))
        axes = axes.ravel()
        for ax, arr, title in [
            (axes[0], vertical, "Vertical"),
            (axes[1], horizontal, "Horizontal"),
            (axes[2], diag1, "Diag TL-BR"),
            (axes[3], diag2, "Diag TR-BL"),
        ]:
            ax.plot(arr, label="raw")
            ax.plot(_correct(arr), label="corrected")
            ax.set_title(title)
            ax.legend()
            ax.set_xlabel("Pixel")
            ax.set_ylabel("Intensity")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Line profiles")
        layout = QtWidgets.QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.resize(900, 600)
        dlg.show()
        dlg.exec()

    def _show_bleach_dialog(self) -> None:
        """Open a dialog showing ROI mean over T with exponential fit."""
        if self.primary_image.array is None:
            return
        self.recorder.record("bleach_fit", {"image": self.primary_image.name})
        arr = self.primary_image.array
        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        crop_rect = self.crop_rect
        img_path = pathlib.Path(self.primary_image.path)
        job_gen = self._job_generation

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Computing…", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Bleaching analysis")
        layout = QtWidgets.QVBoxLayout(dlg)
        status_label = QtWidgets.QLabel("Computing ROI means…")
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        status_row = QtWidgets.QHBoxLayout()
        status_row.addWidget(status_label)
        status_row.addWidget(cancel_btn)
        layout.addLayout(status_row)
        layout.addWidget(progress_bar)

        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        def _job(progress, cancel_token):
            def _apply_crop_local(frame: np.ndarray) -> np.ndarray:
                x, y, w, h = crop_rect
                if w <= 0 or h <= 0:
                    return frame
                x0 = int(max(0, x))
                y0 = int(max(0, y))
                x1 = int(min(frame.shape[1], x + w))
                y1 = int(min(frame.shape[0], y + h))
                return frame[y0:y1, x0:x1]

            def _roi_mask_local(shape: Tuple[int, int]) -> np.ndarray:
                h, w = shape
                yy = np.arange(h)[:, None]
                xx = np.arange(w)[None, :]
                rx, ry, rw, rh = roi_rect
                if roi_shape == "circle":
                    cx, cy = rx + rw / 2, ry + rh / 2
                    r = min(rw, rh) / 2
                    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
                return (rx <= xx) & (xx <= rx + rw) & (ry <= yy) & (yy <= ry + rh)

            means = []
            total = max(1, arr.shape[0])
            for t in range(arr.shape[0]):
                if cancel_token.is_cancelled():
                    return None
                frame = arr[t, 0, :, :]
                frame_cropped = _apply_crop_local(frame)
                roi_mask = _roi_mask_local(frame_cropped.shape)
                vals = frame_cropped[roi_mask]
                means.append(float(vals.mean()) if vals.size else float("nan"))
                pct = int((t + 1) / total * 80)
                progress(pct, f"Computing means… {t+1}/{total}")
            if cancel_token.is_cancelled():
                return None
            progress(90, "Fitting…")
            try:
                xs, fit, eq = fit_bleach_curve(means)
            except Exception:
                xs = np.arange(len(means))
                fit = None
                eq = "fit failed"
            progress(100, "Done")
            return (means, xs, fit, eq, img_path, job_gen)

        def _on_progress(value: int, msg: str) -> None:
            if not dlg.isVisible():
                return
            progress_bar.setValue(value)
            if msg:
                status_label.setText(msg)

        def _on_result(result) -> None:
            if not dlg.isVisible():
                return
            if result is None:
                return
            means, xs, fit, eq, path, gen = result
            if gen != self._job_generation:
                return
            if pathlib.Path(self.primary_image.path) != path:
                return
            ax.clear()
            ax.plot(xs, means, "o-", label="ROI mean")
            if fit is not None:
                ax.plot(xs, fit, "--", label=eq)
            ax.set_xlabel("Frame")
            ax.set_ylabel("Mean intensity")
            ax.set_title("ROI mean vs frame")
            ax.legend()
            canvas.draw_idle()
            status_label.setText("Done.")

        def _on_error(err: str) -> None:
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Failed. See Logs.")
            self._append_log(f"[JOB] Bleaching analysis error\n{err}")

        token = self._submit_analysis_job(
            _job,
            name="Bleaching analysis",
            on_progress=_on_progress,
            on_result=_on_result,
            on_error=_on_error,
        )

        def _cancel() -> None:
            token.cancel()
            status_label.setText("Cancelled.")

        cancel_btn.clicked.connect(_cancel)
        dlg.finished.connect(lambda _result: token.cancel())
        dlg.resize(800, 520)
        dlg.show()
        dlg.exec()

    def _show_table_dialog(self) -> None:
        """Open a dialog with a table of file names and ROI mean; allow CSV export."""
        # Prefer last opened folder; otherwise use currently loaded images.
        candidates: List[pathlib.Path] = []
        if self._last_folder and self._last_folder.exists():
            candidates = sorted(
                [
                    p
                    for p in self._last_folder.iterdir()
                    if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")
                ]
            )
        if not candidates:
            candidates = [img.path for img in self.images]
        if not candidates:
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("ROI mean table")
        layout = QtWidgets.QVBoxLayout(dlg)
        status_label = QtWidgets.QLabel("Computing ROI means…")
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        status_row = QtWidgets.QHBoxLayout()
        status_row.addWidget(status_label)
        status_row.addWidget(cancel_btn)
        layout.addLayout(status_row)
        layout.addWidget(progress_bar)

        table = QtWidgets.QTableWidget(len(candidates), 2)
        table.setHorizontalHeaderLabels(["File", "ROI mean"])
        for i, p in enumerate(candidates):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(p.name))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem("…"))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        export_btn = QtWidgets.QPushButton("Export CSV")
        layout.addWidget(export_btn)

        rows: List[dict] = [{"file": p.name, "roi_mean": float("nan")} for p in candidates]

        def _export() -> None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export ROI means",
                str(pathlib.Path.cwd() / "roi_means.csv"),
                "CSV Files (*.csv)",
            )
            if path:
                pd.DataFrame(rows).to_csv(path, index=False)

        export_btn.clicked.connect(_export)
        export_btn.setEnabled(False)

        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        crop_rect = self.crop_rect
        job_gen = self._job_generation

        def _job(progress, cancel_token):
            total = max(1, len(candidates))
            for idx, path in enumerate(candidates):
                if cancel_token.is_cancelled():
                    return None
                roi_mean = compute_roi_mean_for_path(str(path), roi_rect, roi_shape, crop_rect)
                pct = int((idx + 1) / total * 100)
                progress(pct, f"row:{idx}:{roi_mean}")
            return "done"

        def _on_progress(value: int, msg: str) -> None:
            if not dlg.isVisible():
                return
            progress_bar.setValue(value)
            if msg.startswith("row:"):
                try:
                    _, idx_s, mean_s = msg.split(":", 2)
                    idx = int(idx_s)
                    mean_val = float(mean_s)
                except ValueError:
                    return
                if 0 <= idx < len(rows):
                    rows[idx]["roi_mean"] = mean_val
                    table.setItem(idx, 1, QtWidgets.QTableWidgetItem(f"{mean_val:.3f}"))
            status_label.setText("Computing ROI means…")

        def _on_result(_result) -> None:
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Done.")
            export_btn.setEnabled(True)

        def _on_error(err: str) -> None:
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Failed. See Logs.")
            self._append_log(f"[JOB] ROI mean table error\n{err}")

        token = self._submit_analysis_job(
            _job,
            name="ROI mean table",
            on_progress=_on_progress,
            on_result=_on_result,
            on_error=_on_error,
        )

        def _cancel() -> None:
            token.cancel()
            status_label.setText("Cancelled.")

        cancel_btn.clicked.connect(_cancel)
        dlg.finished.connect(lambda _result: token.cancel())
        dlg.resize(500, 300)
        dlg.show()
        dlg.exec()

    def _compute_roi_mean_for_path(self, path: pathlib.Path) -> float:
        """Compute ROI mean for the given TIFF path with minimal memory use."""
        try:
            return compute_roi_mean_for_path(
                str(path), self.roi_rect, self.roi_shape, self.crop_rect
            )
        except Exception:
            return float("nan")

    def _clear_cache(self) -> None:
        """Clear all lazy image data (arrays + projections) and refresh the view."""
        self.stop_playback_t()
        cleared = 0
        self.proj_cache.clear()
        for img in self.images:
            if img.array is not None or img.mean_proj is not None or img.std_proj is not None:
                cleared += 1
            self._evict_image_cache(img)
        gc.collect()
        debug_log(f"Cleared cached data for {cleared} images")
        self._set_status(f"Cleared cached image data for {cleared} images.")
        # Will lazily reload the active images after purge.
        self._refresh_image()

    def _show_smlm_panel(self) -> None:
        """Show the SMLM parameter panel."""
        if self.dock_smlm is not None:
            self.dock_smlm.setVisible(True)
            self.dock_smlm.raise_()
            if getattr(self, "smlm_panel", None) is not None:
                self.smlm_panel.tabs.setCurrentIndex(0)

    def _show_deepstorm_panel(self) -> None:
        """Show the Deep-STORM parameter panel."""
        if getattr(self, "dock_smlm", None) is not None:
            self.dock_smlm.setVisible(True)
            self.dock_smlm.raise_()
        if getattr(self, "smlm_panel", None) is not None:
            self.smlm_panel.tabs.setCurrentIndex(1)

    def _show_threshold_panel(self) -> None:
        """Show the Threshold panel."""
        if getattr(self, "dock_threshold", None) is not None:
            self.dock_threshold.setVisible(True)
            self.dock_threshold.raise_()

    def _show_analyze_particles_panel(self) -> None:
        """Show the Analyze Particles panel."""
        if getattr(self, "dock_particles", None) is not None:
            self.dock_particles.setVisible(True)
            self.dock_particles.raise_()

    def _clear_fov_list(self) -> None:
        """Remove all FOVs except the current primary to reset the list."""
        if not self.images:
            return
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        keep_idx = self.current_image_idx
        keep_img = self.images[keep_idx]
        self.controller.retain_single_image(keep_idx)
        self.fov_list.clear()
        self.primary_combo.clear()
        self.support_combo.clear()
        keep_img.id = 0
        self.fov_list.addItem(keep_img.name)
        self.primary_combo.addItem(keep_img.name)
        self.support_combo.addItem(keep_img.name)
        self.current_image_idx = 0
        self.support_image_idx = 0
        self._set_status("Cleared FOV list; kept current image.")
        self.roi_manager.rois_by_image = {0: self.roi_manager.list_rois(keep_idx)}
        self.roi_manager.set_active(self.roi_manager.active_roi_id)
        self._refresh_roi_manager()
        self._refresh_image()

    def _recent_limit(self) -> int:
        return int(self._settings.value("keepRecentImages", 10, type=int))

    def _load_recent_images(self) -> List[str]:
        recent = self._settings.value("recentImages", [], type=list)
        recent_list = [str(p) for p in recent] if recent else []
        self.controller.set_recent_images(recent_list)
        return recent_list

    def _save_recent_images(self, recent: List[str]) -> None:
        self._settings.setValue("recentImages", recent)
        self.controller.set_recent_images(recent)

    def _add_recent_images(self, paths: List[pathlib.Path]) -> None:
        recent = self._load_recent_images()
        for p in paths:
            p_str = str(p)
            if p_str in recent:
                recent.remove(p_str)
            recent.insert(0, p_str)
        limit = self._recent_limit()
        recent = recent[:limit]
        self._save_recent_images(recent)
        self._populate_recent_menu()

    def _populate_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = self._load_recent_images()
        for path in recent:
            act = self.recent_menu.addAction(path)
            act.triggered.connect(lambda _checked, p=path: self._open_recent_image(p))
        if recent:
            self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.recent_clear_act)

    def _clear_recent_images(self) -> None:
        self._save_recent_images([])
        self._populate_recent_menu()

    def _open_recent_image(self, path: str) -> None:
        p = pathlib.Path(path)
        if not p.exists():
            QtWidgets.QMessageBox.warning(self, "File not found", f"{path} does not exist.")
            self._clear_recent_images()
            return
        self._open_files_from_paths([p])

    def _open_files_from_paths(self, paths: List[pathlib.Path]) -> None:
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        self._add_recent_images(paths)
        self._last_folder = paths[0].parent
        self.roi_manager.rois_by_image.clear()
        new_images = []
        for p in paths:
            meta = read_metadata(p)
            new_images.append(meta)
        self.controller.add_images(new_images)
        for meta in new_images:
            self.fov_list.addItem(meta.name)
            self.primary_combo.addItem(meta.name)
            self.support_combo.addItem(meta.name)
            self.roi_manager.rois_by_image[meta.id] = []
        self._refresh_annotation_availability()
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._refresh_image()

    def _refresh_annotation_availability(self) -> None:
        if self.fov_list is None:
            return
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView)
        for idx, img in enumerate(self.images):
            item = self.fov_list.item(idx)
            if item is None:
                continue
            if self.controller.annotations_available(img.id):
                item.setIcon(icon)
                item.setToolTip("Annotations available")
            else:
                item.setIcon(QtGui.QIcon())
                item.setToolTip("")

    def _maybe_autoload_annotations(self, image_id: int) -> None:
        if not self._settings.value("autoLoadAnnotations", True, type=bool):
            return
        if self.controller.annotations_are_loaded(image_id):
            return
        if not self.controller.annotation_entries_for_image(image_id):
            return
        cal = self._get_calibration_state(image_id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=False, pixel_size_nm=pixel_size_nm)

    def _start_annotation_load_job(
        self, image_id: int, *, replace: bool, pixel_size_nm: Optional[float]
    ) -> None:
        existing = self._annotation_job_tokens.get(image_id)
        if existing is not None:
            existing.cancel()

        def _worker(progress, cancel):
            paths = [entry.path for entry in self.controller.annotation_entries_for_image(image_id)]
            points, imports = self.controller._parse_annotations_from_paths(
                paths,
                image_id=image_id,
                pixel_size_nm=pixel_size_nm,
                force_image_id=image_id,
            )
            return (points, imports)

        def _on_result(result):
            if result is None:
                return
            points, imports = result
            self.controller._record_annotation_imports(imports)
            if replace:
                self.controller.replace_annotations(image_id, points)
            else:
                self.controller.merge_annotations(image_id, points)
            meta = None
            for target_id, entry in imports:
                if target_id == image_id:
                    meta = entry.get("meta")
                    if isinstance(meta, dict) and meta:
                        break
            if meta:
                self._handle_annotation_metadata(image_id, meta)
            self._mark_dirty()
            self.controller.annotations_changed.emit()
            if image_id == self.primary_image.id:
                self._refresh_image()
            try:
                # Brief user feedback on completion
                self.statusBar().showMessage("Annotations loaded.", 3000)
            except Exception:
                pass

        def _on_error(err: str) -> None:
            try:
                self.statusBar().showMessage("Annotation load error (see Logs)", 4000)
            except Exception:
                pass
            self._append_log(f"[Annotations] Load error for image id={image_id}\n{err}")

        try:
            self.statusBar().showMessage("Loading annotations…", 2000)
        except Exception:
            pass
        handle = self.jobs.submit(
            _worker,
            name="Load annotations",
            on_result=_on_result,
            on_error=_on_error,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
        )
        self._annotation_job_tokens[image_id] = handle.cancel_token
        self._annotation_job_ids[image_id] = handle.job_id

    def _on_metadata_dock_visibility(self, visible: bool) -> None:
        if not visible:
            return
        self._load_full_metadata()

    def _refresh_metadata_dock(self, image_id: int) -> None:
        if getattr(self, "metadata_widget", None) is None:
            return
        summary = self.controller.get_metadata_summary(image_id)
        bundle = MetadataBundle(
            summary=summary,
            tiff_tags={},
            ome_xml=None,
            ome_parsed=None,
            micromanager=None,
            vendor_private={},
        )
        self.metadata_widget.set_bundle(bundle)
        if self.dock_metadata is not None and self.dock_metadata.isVisible():
            self._load_full_metadata()

    def _load_full_metadata(self) -> None:
        if getattr(self, "metadata_widget", None) is None:
            return
        image_id = self.primary_image.id
        bundle = self.controller.load_metadata_bundle(image_id)
        self.metadata_widget.set_bundle(bundle)

    def _handle_annotation_metadata(self, image_id: int, meta: dict) -> None:
        self._pending_annotation_meta = meta
        self._pending_annotation_meta_image_id = image_id
        self._show_annotation_meta_banner(image_id, meta)
        if self._settings.value("applyAnnotationMetaOnLoad", False, type=bool):
            self._apply_annotation_metadata(keep_banner=True)

    def _show_annotation_meta_banner(self, image_id: int, meta: dict) -> None:
        if not hasattr(self, "annotation_meta_widget") or self.annotation_meta_widget is None:
            return
        image_name = self.images[image_id].name if 0 <= image_id < len(self.images) else "image"
        self.annotation_meta_label.setText(f"Metadata detected for {image_name}.")
        self.annotation_meta_widget.setVisible(True)

    def _dismiss_annotation_meta_banner(self) -> None:
        if hasattr(self, "annotation_meta_widget") and self.annotation_meta_widget is not None:
            self.annotation_meta_widget.setVisible(False)
        self._pending_annotation_meta = None
        self._pending_annotation_meta_image_id = None

    def _apply_annotation_metadata(self, keep_banner: bool = False) -> None:
        meta = self._pending_annotation_meta
        image_id = self._pending_annotation_meta_image_id
        if not meta or image_id is None:
            return
        active_primary = self.primary_image.id
        roi = meta.get("roi")
        if isinstance(roi, dict) and image_id == active_primary:
            shape = roi.get("shape", "box")
            rect = roi.get("rect")
            if rect and len(rect) == 4:
                rect = tuple(float(v) for v in rect)
                self.controller.set_roi(rect, shape=str(shape))
                self.roi_rect = rect
                self.roi_shape = str(shape)
            elif shape == "circle":
                center = roi.get("center")
                radius = roi.get("radius")
                if center and radius is not None:
                    cx, cy = center
                    rect = (
                        float(cx - radius),
                        float(cy - radius),
                        float(radius * 2),
                        float(radius * 2),
                    )
                    self.controller.set_roi(rect, shape="circle")
                    self.roi_rect = rect
                    self.roi_shape = "circle"
        crop = meta.get("crop")
        if crop and len(crop) == 4 and image_id == active_primary:
            self.crop_rect = tuple(float(v) for v in crop)
            self.controller.set_crop(self.crop_rect)
            self._sync_crop_controls()
        if image_id == active_primary and roi is not None:
            self._sync_roi_controls()
        display = meta.get("display")
        if isinstance(display, dict):
            non_active_mapping = None
            win = display.get("win")
            if isinstance(win, dict) and "min" in win and "max" in win:
                if image_id == active_primary:
                    self.controller.set_display_mapping(
                        float(win["min"]), float(win["max"]), display.get("gamma")
                    )
                else:
                    non_active_mapping = self.controller.display_mapping.mapping_for(
                        image_id, "frame"
                    )
                    non_active_mapping.set_window(float(win["min"]), float(win["max"]))
            else:
                pct = display.get("pct")
                if (
                    isinstance(pct, dict)
                    and self.primary_image.array is not None
                    and image_id == active_primary
                ):
                    try:
                        low = float(pct.get("low", 2.0))
                        high = float(pct.get("high", 98.0))
                        data = self._slice_data(self.primary_image)
                        vmin = float(np.percentile(data, low))
                        vmax = float(np.percentile(data, high))
                        self.controller.set_display_mapping(vmin, vmax, display.get("gamma"))
                    except (TypeError, ValueError):
                        pass
            gamma = display.get("gamma")
            if gamma is not None:
                try:
                    if image_id == active_primary:
                        self.controller.set_gamma(float(gamma))
                    else:
                        if non_active_mapping is None:
                            non_active_mapping = self.controller.display_mapping.mapping_for(
                                image_id, "frame"
                            )
                        non_active_mapping.gamma = float(gamma)
                except (TypeError, ValueError):
                    pass
            mode = display.get("mode")
            if isinstance(mode, str):
                if image_id == active_primary:
                    mapping = self.controller.display_mapping.mapping_for(image_id, "frame")
                    mapping.mode = mode
                    self.controller.set_display_for_image(image_id, "frame", mapping)
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.mode = mode
            lut = display.get("lut")
            if isinstance(lut, str) and lut in lut_names():
                if image_id == active_primary:
                    self.controller.set_lut(lut_names().index(lut))
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.lut = lut_names().index(lut)
            elif isinstance(lut, int):
                if image_id == active_primary:
                    self.controller.set_lut(lut)
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.lut = lut
            invert = display.get("invert")
            if invert is not None:
                if image_id == active_primary:
                    self.controller.set_invert(bool(invert))
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.invert = bool(invert)
            if non_active_mapping is not None and image_id != active_primary:
                self.controller.set_display_for_image(image_id, "frame", non_active_mapping)
        axis = meta.get("axis")
        if isinstance(axis, str):
            self.controller.set_axis_interpretation(image_id, axis)
            if image_id == active_primary and hasattr(self, "axis_mode_combo"):
                self.axis_mode_combo.setCurrentText(axis)
        if keep_banner:
            if hasattr(self, "annotation_meta_label"):
                self.annotation_meta_label.setText("Metadata applied.")
        else:
            self._dismiss_annotation_meta_banner()
        self._refresh_image()
