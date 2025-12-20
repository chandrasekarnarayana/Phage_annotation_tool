"""Annotation import/export, indexing, and merge helpers."""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotation_index import AnnotationIndexEntry, build_index, match
from phage_annotator.annotation_metadata import (
    merge_meta,
    parse_csv_header_meta,
    parse_filename_tokens,
    parse_json_meta,
)
from phage_annotator.annotations import Keypoint, keypoints_from_csv, keypoints_from_json
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.io_annotations import detect_format, parse_legacy_csv, parse_thunderstorm_csv


class SessionAnnotationIOMixin:
    """Mixin for annotation import/export, indexing, and merge helpers."""

    def open_files(self, parent: QtWidgets.QWidget) -> List[pathlib.Path]:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            parent,
            "Open TIFF/OME-TIFF files",
            str(pathlib.Path.cwd()),
            "TIFF Files (*.tif *.tiff *.ome.tif *.ome.tiff)",
        )
        return [pathlib.Path(p) for p in paths]

    def open_folder(self, parent: QtWidgets.QWidget) -> List[pathlib.Path]:
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
        return list(self.session_state.annotation_index.get(image_id, []))

    def annotations_available(self, image_id: int) -> bool:
        return bool(self.session_state.annotation_index.get(image_id))

    def mark_annotations_loaded(self, image_id: int) -> None:
        self.session_state.annotations_loaded[image_id] = True

    def annotations_are_loaded(self, image_id: int) -> bool:
        return bool(self.session_state.annotations_loaded.get(image_id, False))

    def load_annotations(
        self,
        parent: QtWidgets.QWidget,
        image_id: int,
        pixel_size_nm: Optional[float] = None,
        *,
        force_image_id: Optional[int] = None,
    ) -> None:
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
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Load failed", str(exc))
            return
        self._record_annotation_imports(imports)
        by_image: Dict[int, List[Keypoint]] = {}
        for kp in merged:
            by_image.setdefault(kp.image_id, []).append(kp)
        for target_id, points in by_image.items():
            self.merge_annotations(target_id, points)
        self.set_dirty(True)
        self.annotations_changed.emit()

    def _parse_annotations_from_paths(
        self,
        paths: List[pathlib.Path],
        *,
        image_id: int,
        pixel_size_nm: Optional[float],
        force_image_id: Optional[int] = None,
    ) -> Tuple[List[Keypoint], List[Tuple[int, Dict[str, object]]]]:
        name_map = {img.name: img.id for img in self.session_state.images}
        merged: List[Keypoint] = []
        imports: List[Tuple[int, Dict[str, object]]] = []
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
                        pixel_size_nm=pixel_size_nm,
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
                elif kp.image_name in name_map:
                    kp.image_id = name_map[kp.image_name]
                else:
                    kp.image_id = image_id
                    kp.image_name = self.session_state.images[image_id].name
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
                        "pixel_size_nm": pixel_size_nm,
                        "meta": file_meta,
                    },
                )
            )
        return merged, imports

    def _record_annotation_imports(self, imports: List[Tuple[int, Dict[str, object]]]) -> None:
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

    def _merge_annotations(self, image_id: int, new_points: List[Keypoint]) -> None:
        pts = list(self.session_state.annotations.get(image_id, []))
        pts.extend(new_points)
        self.session_state.annotations[image_id] = self._dedup_annotations(pts)

    def _dedup_annotations(self, points: List[Keypoint], eps: float = 0.25) -> List[Keypoint]:
        seen_ids = set()
        seen_keys = set()
        deduped: List[Keypoint] = []
        for kp in points:
            if kp.annotation_id:
                if kp.annotation_id in seen_ids:
                    continue
                seen_ids.add(kp.annotation_id)
            else:
                key = (
                    int(round(kp.x_px / eps)),
                    int(round(kp.y_px / eps)),
                    int(kp.t),
                    int(kp.z),
                    kp.label,
                    kp.meta.get("import_file", ""),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
            deduped.append(kp)
        return deduped

    def load_indexed_annotations(self, image_id: int, pixel_size_nm: Optional[float]) -> List[Keypoint]:
        """Parse annotation files from the index for a single image."""
        entries = self.annotation_entries_for_image(image_id)
        if not entries:
            return []
        paths = [entry.path for entry in entries]
        points, imports = self._parse_annotations_from_paths(
            paths,
            image_id=image_id,
            pixel_size_nm=pixel_size_nm,
            force_image_id=image_id,
        )
        self._record_annotation_imports(imports)
        return points

    def replace_annotations(self, image_id: int, points: List[Keypoint]) -> None:
        """Replace annotations for an image with a deduplicated list."""
        self.session_state.annotations[image_id] = self._dedup_annotations(points)
        self.mark_annotations_loaded(image_id)

    def merge_annotations(self, image_id: int, points: List[Keypoint]) -> None:
        """Merge annotations for an image with deduplication."""
        self._merge_annotations(image_id, points)
        self.mark_annotations_loaded(image_id)

    def clear_annotations(self, image_id: int) -> None:
        """Remove all annotations for an image."""
        self.session_state.annotations[image_id] = []
