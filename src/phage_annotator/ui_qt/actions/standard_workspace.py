"""Workspace, recent-file, and annotation-load actions."""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtGui, QtWidgets

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.utils.image_io import read_metadata


class WorkspaceActionsMixin:
    """Mixin for workspace I/O, recent files, and metadata dock updates."""

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
        self._request_ui_refresh("standard-actions")
        self._update_analysis_panel_modalities()

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
                except Exception:
                    pass
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
                context_panel_key=str(getattr(self, "annotate_target", "frame")),
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
            self._status_error(
                "Annotation load error (see Logs)",
                timeout_ms=4000,
                source="workspace.annotations_load",
            )
            self._append_log(f"[Annotations] Load error for image id={image_id}\n{err}")

        self._status_info("Loading annotations…", timeout_ms=2000, source="workspace.annotations_load")
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
        self._request_ui_refresh("standard-actions")
