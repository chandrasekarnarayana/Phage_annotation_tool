"""Extracted method group 1 for SessionAnnotationIOMixin."""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.io.metadata.index import AnnotationIndexEntry, build_index, match
from phage_annotator.io.metadata.annotation import (
    merge_meta,
    parse_csv_header_meta,
    parse_filename_tokens,
    parse_json_meta,
)
from phage_annotator.annotation.core import Keypoint, keypoints_from_csv, keypoints_from_json
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.io.readers.annotations import (
    detect_format,
    parse_legacy_csv,
    parse_thunderstorm_csv,
)
from phage_annotator.session.signal_hub import emit_annotations_changed



class FileIoMixin:
    """Method group 1 extracted from SessionAnnotationIOMixin."""

    def open_files(self, parent: QtWidgets.QWidget) -> List[pathlib.Path]:
        """Open files for the current workflow."""
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            parent,
            "Open TIFF/OME-TIFF files",
            str(pathlib.Path.cwd()),
            "TIFF Files (*.tif *.tiff *.ome.tif *.ome.tiff)",
        )
        return [pathlib.Path(p) for p in paths]
    def open_folder(self, parent: QtWidgets.QWidget) -> List[pathlib.Path]:
        """Open folder for the current workflow."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(parent, "Open folder", str(pathlib.Path.cwd()))
        if not folder:
            return []
        folder_path = pathlib.Path(folder)
        paths = sorted(
            [
                p
                for p in folder_path.iterdir()
                if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")
            ]
        )
        if not paths:
            QtWidgets.QMessageBox.warning(parent, "No images", "Folder contains no supported TIFF files.")
        return paths
    def build_annotation_index(self, folder: pathlib.Path) -> None:
        """Index annotation files near the current image list."""
        index = build_index(folder)
        self.session_state.annotation_index = {}
        for img in self.session_state.images:
            entries = match(pathlib.Path(img.path), index)
            if entries:
                self.session_state.annotation_index[img.id] = entries
                self.session_state.annotations_loaded[img.id] = False
    def annotation_entries_for_image(self, image_id: int) -> List[AnnotationIndexEntry]:
        """Run the annotation entries for image workflow."""
        return list(self.session_state.annotation_index.get(image_id, []))
    def annotations_available(self, image_id: int) -> bool:
        """Run the annotations available workflow."""
        return bool(self.session_state.annotation_index.get(image_id))
    def mark_annotations_loaded(self, image_id: int) -> None:
        """Mark annotations loaded for the current workflow."""
        self.session_state.annotations_loaded[image_id] = True
    def annotations_are_loaded(self, image_id: int) -> bool:
        """Run the annotations are loaded workflow."""
        return bool(self.session_state.annotations_loaded.get(image_id, False))
    def load_annotations(
        self,
        parent: QtWidgets.QWidget,
        image_id: int,
        pixel_size_nm: Optional[float] = None,
        *,
        force_image_id: Optional[int] = None,
        context_panel_key: Optional[str] = None,
    ) -> None:
        """Load annotations for the current workflow."""
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            parent,
            "Load annotations",
            str(pathlib.Path.cwd()),
            "Annotation Files (*.csv *.json)",
        )
        if not paths:
            return
        try:
            merged, imports = self._parse_annotations_from_paths(
                [pathlib.Path(p) for p in paths],
                image_id=image_id,
                pixel_size_nm=pixel_size_nm,
                force_image_id=force_image_id,
                context_panel_key=context_panel_key,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Load failed", str(exc))
            return
        self._record_annotation_imports(imports)
        if hasattr(self, "record_workflow_event"):
            self.record_workflow_event(
                "annotations_imported",
                image_id=image_id,
                count=len(merged),
                file_count=len(paths),
            )
        by_image: Dict[int, List[Keypoint]] = {}
        for kp in merged:
            by_image.setdefault(kp.image_id, []).append(kp)
        for target_id, points in by_image.items():
            self.merge_annotations(target_id, points)
        self.set_dirty(True)
        emit_annotations_changed(self)
        if hasattr(self, "refresh_provenance_coverage_metrics"):
            self.refresh_provenance_coverage_metrics()
    def _parse_annotations_from_paths(
        self,
        paths: List[pathlib.Path],
        *,
        image_id: int,
        pixel_size_nm: Optional[float],
        force_image_id: Optional[int] = None,
        context_panel_key: Optional[str] = None,
    ) -> Tuple[List[Keypoint], List[Tuple[int, Dict[str, object]]]]:
        """Parse annotations from paths for the current workflow."""
        name_map = {img.name: img.id for img in self.session_state.images}
        merged: List[Keypoint] = []
        imports: List[Tuple[int, Dict[str, object]]] = []
        effective_pixel_size_nm = self._resolve_import_pixel_size_nm(pixel_size_nm)
        context_key = ""
        if context_panel_key and hasattr(self, "annotation_context_key_for_panel"):
            context_key = str(
                self.annotation_context_key_for_panel(
                    str(context_panel_key),
                    annotation_space=str(getattr(self.session_state, "annotation_space", "stack")),
                )
            )
        for path in paths:
            file_meta: Dict[str, object] = {}
            fmt = "other"
            points: List[Keypoint]
            if path.suffix.lower() == ".csv":
                fmt = detect_format(path)
                file_meta = merge_meta(parse_csv_header_meta(path), parse_filename_tokens(path))
                if fmt == "thunderstorm":
                    points = parse_thunderstorm_csv(
                        path,
                        self.session_state.images[image_id].name,
                        pixel_size_nm=effective_pixel_size_nm,
                    )
                elif fmt == "legacy":
                    points = parse_legacy_csv(path, self.session_state.images[image_id].name)
                else:
                    points = keypoints_from_csv(path)
            else:
                points = keypoints_from_json(path)
                fmt = "json"
                file_meta = merge_meta(parse_json_meta(path), parse_filename_tokens(path))

            for kp in points:
                if force_image_id is not None:
                    kp.image_id = force_image_id
                    kp.image_name = self.session_state.images[force_image_id].name
                    kp.annotation_context = context_key
                elif kp.image_name in name_map:
                    kp.image_id = name_map[kp.image_name]
                else:
                    kp.image_id = image_id
                    kp.image_name = self.session_state.images[image_id].name
                    if context_key:
                        kp.annotation_context = context_key
                if not kp.image_key:
                    kp.image_key = kp.image_name
                kp.meta.setdefault("import_file", str(path.resolve()))
                merged.append(kp)

            if points:
                target_id = points[0].image_id
            else:
                target_id = image_id
            imports.append(
                (
                    target_id,
                    {
                        "format": fmt,
                        "path": str(path.resolve()),
                        "pixel_size_nm": effective_pixel_size_nm,
                        "meta": file_meta,
                    },
                )
            )
        return merged, imports
    def _resolve_import_pixel_size_nm(self, pixel_size_nm: Optional[float]) -> Optional[float]:
        """Resolve import conversion scale in nm/px.

        Priority:
        1) Explicit value passed by caller.
        2) Application setting ``defaultPixelSizeUmPerPx`` converted to nm/px.
        """
        if pixel_size_nm is not None:
            try:
                parsed = float(pixel_size_nm)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                pass

        settings = getattr(self, "_settings", None)
        if settings is None:
            return None
        try:
            default_um_per_px = settings.value("defaultPixelSizeUmPerPx", 0.069, type=float)
            if default_um_per_px is None:
                return None
            parsed_um = float(default_um_per_px)
            if parsed_um <= 0:
                return None
            return parsed_um * 1000.0
        except Exception:
            return None
    def _record_annotation_imports(self, imports: List[Tuple[int, Dict[str, object]]]) -> None:
        """Record annotation imports for the current workflow."""
        for image_id, entry in imports:
            import_list = self.session_state.annotation_imports.setdefault(image_id, [])
            import_list.append(entry)
    def latest_annotation_meta(self, image_id: int) -> Optional[Dict[str, object]]:
        """Return the latest imported annotation metadata for an image."""
        entries = self.session_state.annotation_imports.get(image_id)
        if not entries:
            return None
        meta = entries[-1].get("meta")
        return meta if isinstance(meta, dict) and meta else None
    def clear_stale_analysis_results(self, image_id: int) -> None:
        """Clear SMLM/density results when image changes to prevent stale overlays."""
        # Mark results as stale - GUI will check and clear overlays
        if hasattr(self, "_last_smlm_image_id") and self._last_smlm_image_id != image_id:
            if hasattr(self, "smlm_result"):
                self.smlm_result = None
        if hasattr(self, "_last_density_image_id") and self._last_density_image_id != image_id:
            if hasattr(self, "density_result"):
                self.density_result = None
    def _merge_annotations(self, image_id: int, new_points: List[Keypoint]) -> None:
        """Merge annotations for the current workflow."""
        pts = list(self.session_state.annotations.get(image_id, []))
        pts.extend(new_points)
        self.session_state.annotations[image_id] = self._dedup_annotations(pts)
