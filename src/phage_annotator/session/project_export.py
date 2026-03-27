"""Annotation export metadata and file export helpers."""

from __future__ import annotations

from datetime import datetime
import pathlib
from typing import Dict, Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotation.core import save_keypoints_csv, save_keypoints_json


class SessionProjectExportMixin:
    """Mixin for annotation export metadata and file export helpers."""

    def _annotation_export_timestamp(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _current_annotation_target(self) -> str:
        target = str(getattr(self, "annotate_target", "frame")).strip()
        return target or "frame"

    def _active_annotation_export_context(self) -> Dict[str, object]:
        """Return the current annotation context used for save/export."""
        if hasattr(self, "current_annotation_context"):
            return dict(self.current_annotation_context() or {})
        image_id = int(getattr(self.session_state, "active_primary_id", 0))
        return {
            "context_key": f"img:{image_id}|panel:frame|space:{getattr(self.session_state, 'annotation_space', 'stack')}",
            "panel_key": self._current_annotation_target(),
            "source_image_id": image_id,
            "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            "mode": "independent",
        }

    def _image_export_context(self, image_id: int) -> Dict[str, object]:
        image = next((img for img in self.session_state.images if int(getattr(img, "id", -1)) == int(image_id)), None)
        if image is None:
            return {"image_id": int(image_id)}
        return {
            "image_id": int(getattr(image, "id", image_id)),
            "image_name": str(getattr(image, "name", "")),
            "image_path": str(pathlib.Path(str(getattr(image, "path", ""))).resolve()),
            "shape": list(getattr(image, "shape", ()) or ()),
            "dtype": str(getattr(image, "dtype", "")),
            "has_time": bool(getattr(image, "has_time", False)),
            "has_z": bool(getattr(image, "has_z", False)),
            "ome_axes": str(getattr(image, "ome_axes", "") or ""),
            "interpret_3d_as": str(getattr(image, "interpret_3d_as", "auto")),
        }

    def build_annotation_export_metadata(self, image_id: int, *, export_format: str, export_path: Optional[pathlib.Path] = None) -> Dict[str, object]:
        """Build rich export metadata for CSV/JSON annotations."""
        image_ctx = self._image_export_context(image_id)
        base = self.build_annotation_metadata(image_id)
        display_by_panel: Dict[str, object] = {}
        for panel, mapping in self.display_mapping.per_image.get(image_id, {}).items():
            display_by_panel[str(panel)] = {
                "min": float(mapping.min_val),
                "max": float(mapping.max_val),
                "gamma": float(mapping.gamma),
                "lut": int(mapping.lut),
                "invert": bool(mapping.invert),
            }
        payload: Dict[str, object] = {
            "tool": "PhageAnnotator",
            "schema": "annotation_export.v1",
            "exported_at": self._annotation_export_timestamp(),
            "export_format": str(export_format),
            "annotation_count": int(
                len(
                    self.annotations_for_panel(str(self._active_annotation_export_context().get("panel_key", "frame")))
                    if hasattr(self, "annotations_for_panel")
                    else self.session_state.annotations.get(image_id, [])
                )
            ),
            "linked_image": image_ctx,
            "annotation_context": {
                "context_key": str(self._active_annotation_export_context().get("context_key", "")),
                "mode": str(self._active_annotation_export_context().get("mode", "independent")),
                "scope": str(getattr(self.view_state, "annotation_scope", "current")),
                "target": self._current_annotation_target(),
                "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
                "t": int(getattr(self.view_state, "t", 0)),
                "z": int(getattr(self.view_state, "z", 0)),
            },
            "capture": {
                "roi": base.get("roi"),
                "crop": base.get("crop"),
                "display_frame": base.get("display"),
                "display_by_panel": display_by_panel,
            },
        }
        if export_path is not None:
            payload["export_path"] = str(pathlib.Path(export_path).resolve())
        return payload

    def build_annotation_metadata(self, image_id: int) -> Dict[str, object]:
        """Build metadata dict from current ROI, crop, and display settings."""
        meta: Dict[str, object] = {}
        roi = self.view_state.roi_spec
        if roi and roi.shape != "none":
            meta["roi"] = {"shape": roi.shape}
            if roi.shape == "box":
                meta["roi"]["rect"] = (roi.x, roi.y, roi.w, roi.h)
            elif roi.shape == "circle":
                meta["roi"]["center"] = (roi.x + roi.w / 2, roi.y + roi.h / 2)
                meta["roi"]["radius"] = roi.w / 2
        crop = self.view_state.crop_rect
        if crop and crop != (0, 0, 0, 0):
            meta["crop"] = crop
        if any(int(getattr(img, "id", -1)) == int(image_id) for img in self.session_state.images):
            mapping = self.display_mapping.mapping_for(int(image_id), "frame")
            meta["display"] = {"win": {"min": mapping.min_val, "max": mapping.max_val}, "gamma": mapping.gamma, "lut": mapping.lut}
        return meta

    def save_csv(self, parent: QtWidgets.QWidget, path: pathlib.Path) -> None:
        """Save annotations for the active image to CSV."""
        context = self._active_annotation_export_context()
        image_id = int(context.get("source_image_id", self.session_state.active_primary_id))
        try:
            meta = self.build_annotation_export_metadata(image_id, export_format="csv", export_path=path)
            include_provenance = bool(
                hasattr(self, "feature_enabled")
                and self.feature_enabled("annotation_provenance_schema", True)
            )
            points = (
                self.annotations_for_panel(str(context.get("panel_key", "frame")))
                if hasattr(self, "annotations_for_panel")
                else self.session_state.annotations.get(image_id, [])
            )
            save_keypoints_csv(points, path, meta=meta, include_provenance=include_provenance)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Save CSV failed", str(exc))
            return
        if hasattr(self, "bind_annotation_file_to_panel"):
            self.bind_annotation_file_to_panel(
                str(context.get("panel_key", "frame")),
                str(path),
                fmt="csv",
                mtime=path.stat().st_mtime if path.exists() else None,
                annotation_space=str(context.get("annotation_space", "stack")),
            )
        self.set_dirty(False)

    def save_json(self, parent: QtWidgets.QWidget, path: pathlib.Path) -> None:
        """Save annotations for the active image to JSON."""
        context = self._active_annotation_export_context()
        image_id = int(context.get("source_image_id", self.session_state.active_primary_id))
        try:
            meta = self.build_annotation_export_metadata(image_id, export_format="json", export_path=path)
            include_provenance = bool(
                hasattr(self, "feature_enabled")
                and self.feature_enabled("annotation_provenance_schema", True)
            )
            points = (
                self.annotations_for_panel(str(context.get("panel_key", "frame")))
                if hasattr(self, "annotations_for_panel")
                else self.session_state.annotations.get(image_id, [])
            )
            save_keypoints_json(points, path, meta=meta, include_provenance=include_provenance)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Save JSON failed", str(exc))
            return
        if hasattr(self, "bind_annotation_file_to_panel"):
            self.bind_annotation_file_to_panel(
                str(context.get("panel_key", "frame")),
                str(path),
                fmt="json",
                mtime=path.stat().st_mtime if path.exists() else None,
                annotation_space=str(context.get("annotation_space", "stack")),
            )
        self.set_dirty(False)
