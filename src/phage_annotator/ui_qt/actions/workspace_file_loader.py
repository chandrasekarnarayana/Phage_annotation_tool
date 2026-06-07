"""Workspace, recent-file, and annotation-load actions."""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.utils.image_io import read_metadata

class WorkspaceFileLoaderMixin:
    def _open_files_from_paths(self, paths: List[pathlib.Path]) -> None:
        """Document the open_files_from_paths flow."""
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
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[GUI] Loaded {len(new_images)} image metadata record(s) from explicit paths",
                category="GUI",
            )
        self.controller.add_images(new_images)
        for meta in new_images:
            self.roi_manager.rois_by_image[meta.id] = []
        self._refresh_annotation_availability()
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._request_ui_refresh("standard-actions")
        self._update_analysis_panel_modalities()

    def _refresh_annotation_availability(self) -> None:
        """Document the refresh_annotation_availability flow."""
        tree = getattr(self, "lazy_loader_tree", None)
        if tree is None:
            return
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView)
        available_paths = {
            str(getattr(img, "path", ""))
            for img in (getattr(self, "images", []) or [])
            if self.controller.annotations_available(int(getattr(img, "id", -1)))
        }
        root = tree.invisibleRootItem()
        for row in range(root.childCount()):
            item = root.child(row)
            path = str(item.data(0, QtCore.Qt.ItemDataRole.UserRole) or "")
            if path in available_paths:
                item.setIcon(0, icon)
                item.setToolTip(0, path)
            else:
                item.setIcon(0, QtGui.QIcon())
                item.setToolTip(0, path)

    def _maybe_autoload_annotations(self, image_id: int) -> None:
        """Document the maybe_autoload_annotations flow."""
        if not self._settings.value("autoLoadAnnotations", True, type=bool):
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[Annotations] Auto-load skipped for image id={int(image_id)} (disabled in preferences)",
                    category="Annotations",
                )
            return
        if self.controller.annotations_are_loaded(image_id):
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[Annotations] Auto-load skipped for image id={int(image_id)} (already loaded)",
                    category="Annotations",
                )
            return
        if not self.controller.annotation_entries_for_image(image_id):
            img = next(
                (
                    m
                    for m in getattr(self, "images", [])
                    if int(getattr(m, "id", -1)) == int(image_id)
                ),
                None,
            )
            if img is not None:
                try:
                    self.controller.build_annotation_index(
                        pathlib.Path(str(getattr(img, "path", ""))).parent
                    )
                    if hasattr(self, "_append_log"):
                        self._append_log(
                            f"[Annotations] Rebuilt annotation index for image id={int(image_id)} "
                            f"folder={pathlib.Path(str(getattr(img, 'path', ''))).parent}",
                            category="Annotations",
                        )
                except Exception:
                    pass
        if not self.controller.annotation_entries_for_image(image_id):
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[Annotations] Auto-load found no annotation candidates for image id={int(image_id)}",
                    category="Annotations",
                )
            return
        entries = self.controller.annotation_entries_for_image(image_id)
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[Annotations] Auto-load queued for image id={int(image_id)} "
                f"with {len(entries)} candidate file(s)",
                category="Annotations",
            )
        cal = self._get_calibration_state(image_id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=False, pixel_size_nm=pixel_size_nm)
    def _start_annotation_load_job(
        self, image_id: int, *, replace: bool, pixel_size_nm: Optional[float]
    ) -> None:
        """Document the start_annotation_load_job flow."""
        existing = self._annotation_job_tokens.get(image_id)
        if existing is not None:
            existing.cancel()
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[Annotations] Cancelled previous annotation-load job for image id={int(image_id)}",
                    category="Annotations",
                )

        def _worker(progress, cancel):
            """Document the worker flow."""
            paths = [entry.path for entry in self.controller.annotation_entries_for_image(image_id)]
            points, imports = self.controller._parse_annotations_from_paths(
                paths,
                image_id=image_id,
                pixel_size_nm=pixel_size_nm,
                force_image_id=image_id,
                context_panel_key=str(getattr(self, "annotate_target", "frame")),
            )
            return (points, imports)

        def _on_result(result):
            """Document the on_result flow."""
            if result is None:
                return
            points, imports = result
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[Annotations] Loaded {len(points)} annotation point(s) for image id={int(image_id)} "
                    f"from {len(imports)} file import(s)",
                    category="Annotations",
                )
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
            target_panel = str(getattr(self, "annotate_target", "frame")).strip().lower() or "frame"
            for target_id, entry in imports:
                if int(target_id) != int(image_id):
                    continue
                path = entry.get("path")
                if not path:
                    continue
                self.controller.bind_annotation_file_to_panel(
                    target_panel,
                    str(path),
                    fmt=str(entry.get("format", "other")),
                    mtime=None,
                    annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
                )
            self._mark_dirty()
            emit_annotations_changed(self.controller, image_id=image_id)
            if image_id == self.primary_image.id:
                self._request_ui_refresh("standard-actions")
                self._refresh_table()
            self._status_success("Annotations loaded.", timeout_ms=3000, source="workspace.annotations_load")

        def _on_error(err: str) -> None:
            """Document the on_error flow."""
            self._status_error(
                "Annotation load error (see Logs)",
                timeout_ms=4000,
                source="workspace.annotations_load",
            )
            self._append_log(f"[Annotations] Load error for image id={image_id}\n{err}")

        self._status_info("Loading annotations…", timeout_ms=2000, source="workspace.annotations_load")
        if hasattr(self, "_append_log"):
            self._append_log(
                f"[Annotations] Starting annotation-load job for image id={int(image_id)} replace={bool(replace)}",
                category="Annotations",
            )
        handle = self.jobs.submit(
            _worker,
            name="Load annotations",
            on_result=_on_result,
            on_error=_on_error,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
            priority="interactive",
            replace_key=f"load-annotations-{image_id}",
        )
        self._annotation_job_tokens[image_id] = handle.cancel_token
        self._annotation_job_ids[image_id] = handle.job_id
