"""Method group 1 split from project_bridge.py."""

from __future__ import annotations

import pathlib
from typing import Dict, List

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotation.core import PointSuggestion, keypoints_from_json
from phage_annotator.config.density import DensityConfig
from phage_annotator.core.workspace_snapshot import apply_workspace_snapshot_to_controller
from phage_annotator.data.display_mapping import mapping_from_dict
from phage_annotator.roi.manager import roi_from_dict
from phage_annotator.session.signal_hub import emit_annotations_changed, emit_state_changed


class _SessionProjectBridgeMixinMethods1:
    """Methods split from SessionProjectBridgeMixin."""

    def _set_project_relink_report(
        self,
        *,
        path: pathlib.Path,
        loaded_count: int,
        relinked_images: list[str],
        missing_images: list[str],
        unresolved_rows: list[dict[str, object]],
        partial_load: bool,
    ) -> None:
        """Persist structured relink and partial-load state for recovery UI."""
        self.session_state.project_relink_report = {
            "project_path": str(path),
            "loaded_count": int(loaded_count),
            "relinked": list(relinked_images),
            "missing": list(missing_images),
            "unresolved": list(unresolved_rows),
            "partial_load": bool(partial_load),
            "skipped_count": int(len(missing_images)),
        }

    def load_project(self, parent: QtWidgets.QWidget, path: pathlib.Path, read_metadata, *, relink_mode: str = "ask") -> bool:
        """Load a project payload and apply it to the controller state."""
        payload = self._load_project_payload(parent, path)
        if payload is None:
            return False
        (
            image_entries,
            settings,
            ann_map,
            roi_map,
            thr_map,
            part_map,
            import_map,
            modality_manager_data,
            channel_display_settings,
        ) = payload
        from phage_annotator.session.modality import ModalityManager

        if modality_manager_data is not None:
            try:
                self.session_state.modality_manager = ModalityManager.from_dict(modality_manager_data)
            except Exception:
                self.session_state.modality_manager = None
        else:
            self.session_state.modality_manager = None
        self.session_state.channel_display_settings = channel_display_settings

        images = []
        annotations: Dict[int, List] = {}
        display_per_image: Dict[int, Dict[str, object]] = {}
        rois_by_image: Dict[int, List] = {}
        missing_images = []
        relinked_images: List[str] = []
        resolved_paths: Dict[int, pathlib.Path] = {}
        missing_entries: List[tuple[int, Dict[str, object], pathlib.Path]] = []
        for idx, entry in enumerate(image_entries):
            img_path = self._resolve_project_image_path(entry, path.parent)
            if img_path.exists():
                resolved_paths[idx] = img_path
                original_path = pathlib.Path(str(entry.get("path", "")))
                if original_path and original_path != img_path:
                    relinked_images.append(f"{original_path} -> {img_path}")
            else:
                missing_entries.append((idx, entry, img_path))
        if missing_entries:
            manual = self._prompt_relink_missing_images(parent, missing_entries, mode=relink_mode)
            for idx, relinked in manual.items():
                resolved_paths[idx] = relinked
                original_path = pathlib.Path(str(image_entries[idx].get("path", "")))
                if original_path and original_path != relinked:
                    relinked_images.append(f"{original_path} -> {relinked}")
        for idx, entry in enumerate(image_entries):
            img_path = resolved_paths.get(idx)
            if img_path is None:
                missing_images.append(str(self._resolve_project_image_path(entry, path.parent)))
                continue
            try:
                meta = read_metadata(img_path)
            except Exception as e:
                missing_images.append(f"{img_path} (error: {e})")
                continue
            meta.id = len(images)
            meta.interpret_3d_as = entry.get("interpret_3d_as", meta.interpret_3d_as)
            images.append(meta)
            annotations[meta.id] = []
            entry_mapping = entry.get("display_mapping", {})
            if isinstance(entry_mapping, dict) and entry_mapping:
                display_per_image[meta.id] = {
                    panel: mapping_from_dict(mdict, self.display_mapping.clone())
                    for panel, mdict in entry_mapping.items()
                    if isinstance(mdict, dict)
                }
            if idx in roi_map:
                rois_by_image[meta.id] = [roi_from_dict(r, ridx) for ridx, r in enumerate(roi_map[idx]) if isinstance(r, dict)]
        if missing_images:
            msg = f"Loaded {len(images)} images, but {len(missing_images)} could not be found:\n\n" + "\n".join(missing_images[:10])
            if len(missing_images) > 10:
                msg += f"\n... and {len(missing_images) - 10} more"
            if relinked_images:
                msg += "\n\nRelinked images:\n" + "\n".join(relinked_images[:5])
                if len(relinked_images) > 5:
                    msg += f"\n... and {len(relinked_images) - 5} more"
            QtWidgets.QMessageBox.warning(parent, "Some images not found", msg)
        if not images:
            unresolved_rows = []
            for idx, entry in enumerate(image_entries):
                if idx not in resolved_paths:
                    fallback = self._resolve_project_image_path(entry, path.parent)
                    unresolved_rows.append({"index": int(idx), "image_name": str(entry.get("image_name", fallback.name)), "original_path": str(entry.get("path", fallback)), "resolved_attempt": str(fallback)})
            self._set_project_relink_report(
                path=path,
                loaded_count=0,
                relinked_images=relinked_images,
                missing_images=missing_images,
                unresolved_rows=unresolved_rows,
                partial_load=False,
            )
            QtWidgets.QMessageBox.critical(parent, "Load failed", "No images could be loaded from the project.")
            return False
        unresolved_rows = []
        for idx, entry in enumerate(image_entries):
            if idx in resolved_paths:
                continue
            fallback = self._resolve_project_image_path(entry, path.parent)
            unresolved_rows.append(
                {
                    "index": int(idx),
                    "image_name": str(entry.get("image_name", fallback.name)),
                    "original_path": str(entry.get("path", fallback)),
                    "resolved_attempt": str(fallback),
                }
            )
        self._set_project_relink_report(
            path=path,
            loaded_count=len(images),
            relinked_images=relinked_images,
            missing_images=missing_images,
            unresolved_rows=unresolved_rows,
            partial_load=bool(missing_images),
        )
        for idx, ann_path in ann_map.items():
            if idx < len(image_entries):
                actual_id = None
                entry_path = pathlib.Path(str(image_entries[idx].get("path", "")))
                entry_name = str(image_entries[idx].get("image_name", entry_path.name))
                for img in images:
                    img_path = pathlib.Path(str(getattr(img, "path", "")))
                    if img_path == entry_path or img_path.name == entry_name:
                        actual_id = img.id
                        break
                if actual_id is not None and ann_path and ann_path.exists():
                    try:
                        loaded_points = keypoints_from_json(ann_path)
                        for kp in loaded_points:
                            kp.image_id = actual_id
                            if not kp.image_name:
                                kp.image_name = images[actual_id].name
                            if not kp.image_key:
                                kp.image_key = kp.image_name
                        annotations[actual_id] = loaded_points
                    except Exception:
                        annotations[actual_id] = []
        self._apply_loaded_project_state(
            path=path,
            image_entries=image_entries,
            images=images,
            annotations=annotations,
            display_per_image=display_per_image,
            rois_by_image=rois_by_image,
            settings=settings,
            thr_map=thr_map,
            part_map=part_map,
            import_map=import_map,
            resolved_paths=resolved_paths,
            relinked_images=relinked_images,
            missing_images=missing_images,
        )
        return True
