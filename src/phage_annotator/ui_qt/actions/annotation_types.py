"""Extracted method group 2 for WorkspaceActionsMixin."""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.io.metadata.reader import MetadataBundle
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.utils.image_io import read_metadata



class AnnotationTypesMixin:
    """Method group 2 extracted from WorkspaceActionsMixin."""

    def _start_annotation_load_job(
        self, image_id: int, *, replace: bool, pixel_size_nm: Optional[float]
    ) -> None:
        """Start annotation load job for the current workflow."""
        existing = self._annotation_job_tokens.get(image_id)
        if existing is not None:
            existing.cancel()
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[Annotations] Cancelled previous annotation-load job for image id={int(image_id)}",
                    category="Annotations",
                )

        def _worker(progress, cancel):
            """Handle the worker helper flow."""
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
            """Handle the on result helper flow."""
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
            """Handle the on error helper flow."""
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
    def _on_metadata_dock_visibility(self, visible: bool) -> None:
        """Handle the on metadata dock visibility helper flow."""
        if not visible:
            return
        self._load_full_metadata()
    def _refresh_metadata_dock(self, image_id: int) -> None:
        """Refresh metadata dock for the current workflow."""
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
        """Load full metadata for the current workflow."""
        if getattr(self, "metadata_widget", None) is None:
            return
        image_id = self.primary_image.id
        bundle = self.controller.load_metadata_bundle(image_id)
        self.metadata_widget.set_bundle(bundle)
    def _handle_annotation_metadata(self, image_id: int, meta: dict) -> None:
        """Handle annotation metadata for the current workflow."""
        self._pending_annotation_meta = meta
        self._pending_annotation_meta_image_id = image_id
        self._show_annotation_meta_banner(image_id, meta)
        if self._settings.value("applyAnnotationMetaOnLoad", False, type=bool):
            self._apply_annotation_metadata(keep_banner=True)
    def _show_annotation_meta_banner(self, image_id: int, meta: dict) -> None:
        """Show annotation meta banner for the current workflow."""
        if not hasattr(self, "annotation_meta_widget") or self.annotation_meta_widget is None:
            return
        image_name = self.images[image_id].name if 0 <= image_id < len(self.images) else "image"
        self.annotation_meta_label.setText(f"Metadata detected for {image_name}.")
        self.annotation_meta_widget.setVisible(True)
    def _dismiss_annotation_meta_banner(self) -> None:
        """Handle the dismiss annotation meta banner helper flow."""
        if hasattr(self, "annotation_meta_widget") and self.annotation_meta_widget is not None:
            self.annotation_meta_widget.setVisible(False)
        self._pending_annotation_meta = None
        self._pending_annotation_meta_image_id = None
