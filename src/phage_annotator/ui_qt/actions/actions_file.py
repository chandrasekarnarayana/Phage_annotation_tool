"""File open, folder load, and annotation load/reload actions."""

from __future__ import annotations

import logging
import pathlib
from typing import List, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.actions import assist_generation

logger = logging.getLogger(__name__)


class ActionsMixinFile:
    """Mixin for file open, folder loading, and annotation import actions."""

    def _open_files(self) -> None:
        """Open files for the current workflow."""
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_files(self)
        if paths:
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[GUI] Open files from main import ({len(paths)} selected)",
                    category="GUI",
                )
            self.recorder.record("open_files", {"count": len(paths)})
            self._open_files_from_paths(paths)

    def _open_folder(self) -> None:
        """Open folder for the current workflow."""
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_folder(self)
        if paths:
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[GUI] Open folder from main import ({len(paths)} files discovered)",
                    category="GUI",
                )
            self.recorder.record("open_folder", {"count": len(paths)})
            # Load metadata for all files in the background with progress + cancel (P1.3)
            files = list(paths)

            def _worker(progress, cancel):
                """Handle the worker helper flow."""
                from phage_annotator.ui_qt.utils.image_io import read_metadata

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
                """Handle the on result helper flow."""
                if not result:
                    return
                new_images = result
                if hasattr(self, "_append_log"):
                    self._append_log(
                        f"[GUI] Folder load completed ({len(new_images)} image(s) added)",
                        category="GUI",
                    )
                # Add images and update UI on GUI thread
                self.controller.add_images(new_images)
                for meta in new_images:
                    self.roi_manager.rois_by_image[meta.id] = []
                # Build annotation index (lightweight) and update availability
                try:
                    self.controller.build_annotation_index(files[0].parent)
                    if hasattr(self, "_append_log"):
                        self._append_log(
                            f"[Annotations] Indexed annotation files in {files[0].parent}",
                            category="Annotations",
                        )
                except Exception:
                    logger.warning("Failed to build annotation index after opening folder", exc_info=True)
                self._refresh_annotation_availability()
                self._refresh_roi_manager()
                self._refresh_metadata_dock(self.primary_image.id)
                self._request_ui_refresh("standard-actions")
                self._maybe_autoload_annotations(self.primary_image.id)

            self.jobs.submit(
                _worker,
                name="Open folder",
                on_result=_on_result,
                timeout_sec=300.0,
                retries=2,
                retry_delay_sec=1.0,
                priority="interactive",
                replace_key="open-folder",
            )

    def _reset_confirmations(self) -> None:
        """Re-enable all confirmation dialogs."""
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
        """Load annotations current for the current workflow."""
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            force_image_id=self.primary_image.id,
            context_panel_key=str(getattr(self, "annotate_target", "frame")),
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._request_ui_refresh("standard-actions", table=True)
        self._refresh_table()

    def _load_annotations_multi(self) -> None:
        """Load annotations multi for the current workflow."""
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            context_panel_key=str(getattr(self, "annotate_target", "frame")),
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._request_ui_refresh("standard-actions", table=True)
        self._refresh_table()

    def _load_annotations_all(self) -> None:
        """Load annotations all for the current workflow."""
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
            """Handle the worker helper flow."""
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
            """Handle the on result helper flow."""
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
            emit_annotations_changed(self.controller, image_id=self.primary_image.id)
            self._request_ui_refresh("standard-actions", table=True)
            self._refresh_table()

        self.jobs.submit(
            _worker,
            name="Load all annotations",
            on_result=_on_result,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
            priority="interactive",
            replace_key="load-all-annotations",
        )

    def _reload_annotations_current(self) -> None:
        """Handle the reload annotations current helper flow."""
        image_id = self.primary_image.id
        if not self.controller.annotation_entries_for_image(image_id):
            self._load_annotations_current()
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=True, pixel_size_nm=pixel_size_nm)
