"""Extracted method group 1 for WorkspaceActionsMixin."""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.utils.image_io import read_metadata



class AnnotationLoadMixin:
    """Method group 1 extracted from WorkspaceActionsMixin."""

    def _recent_limit(self) -> int:
        """Handle the recent limit helper flow."""
        return int(self._settings.value("keepRecentImages", 10, type=int))
    def _load_recent_images(self) -> List[str]:
        """Load recent images for the current workflow."""
        recent = self._settings.value("recentImages", [], type=list)
        recent_list = [str(p) for p in recent] if recent else []
        self.controller.set_recent_images(recent_list)
        return recent_list
    def _save_recent_images(self, recent: List[str]) -> None:
        """Save recent images for the current workflow."""
        self._settings.setValue("recentImages", recent)
        self.controller.set_recent_images(recent)
    def _add_recent_images(self, paths: List[pathlib.Path]) -> None:
        """Add recent images for the current workflow."""
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
        """Handle the populate recent menu helper flow."""
        self.recent_menu.clear()
        recent = self._load_recent_images()
        for path in recent:
            act = self.recent_menu.addAction(path)
            act.triggered.connect(lambda _checked, p=path: self._open_recent_image(p))
        if recent:
            self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.recent_clear_act)
    def _clear_recent_images(self) -> None:
        """Clear recent images for the current workflow."""
        self._save_recent_images([])
        self._populate_recent_menu()
    def _open_recent_image(self, path: str) -> None:
        """Open recent image for the current workflow."""
        p = pathlib.Path(path)
        if not p.exists():
            QtWidgets.QMessageBox.warning(self, "File not found", f"{path} does not exist.")
            self._clear_recent_images()
            return
        self._open_files_from_paths([p])
    def _open_files_from_paths(self, paths: List[pathlib.Path]) -> None:
        """Open files from paths for the current workflow."""
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
        """Refresh annotation availability for the current workflow."""
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
        """Handle the maybe autoload annotations helper flow."""
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
