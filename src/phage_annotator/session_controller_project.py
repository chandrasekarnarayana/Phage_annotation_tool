"""Project persistence and recovery helpers."""

from __future__ import annotations

from datetime import datetime
import pathlib
from typing import Optional
from phage_annotator.project_io import load_project, save_project
from phage_annotator.session_state import SessionState


class SessionProjectMixin:
    """Mixin for project persistence and recovery helpers."""
    
    def set_dirty(self, dirty: bool = True) -> None:
    """Mark the session as dirty (or clean)."""
        if self.session_state.dirty == dirty:
            return
        self.session_state.dirty = dirty
        self.state_changed.emit()

    def set_project_path(self, path: Optional[pathlib.Path]) -> None:
        """Set the current project path."""
        if self.session_state.project_path == path:
            return
            self.session_state.project_path = path
            self.state_changed.emit()

    def set_project_save_time(self, ts: Optional[float]) -> None:
        """Set the project save timestamp."""
        if self.session_state.project_save_time == ts:
            return
            self.session_state.project_save_time = ts
            self.state_changed.emit()

    def set_last_folder(self, folder: Optional[pathlib.Path]) -> None:
        """Update the last-used folder."""
        if self.session_state.last_folder == folder:
            return
            self.session_state.last_folder = folder
            self.state_changed.emit()

    def set_recent_images(self, recent: List[str]) -> None:
        """Update the recent images list."""
        self.session_state.recent_images = list(recent)
        self.state_changed.emit()

    def save_project(
        self,
        parent: QtWidgets.QWidget,
        path: pathlib.Path,
        settings: dict,
        rois_by_image: Optional[Dict[int, List[Roi]]] = None,
        ) -> None:
            display_mappings = {}
            for image_id, panels in self.display_mapping.per_image.items():
                display_mappings[image_id] = {panel: mapping_to_dict(mapping) for panel, mapping in panels.items()}
                save_project(
                    path,
                    self.session_state.images,
                    self.session_state.annotations,
                    settings,
                    display_mappings,
                    rois_by_image,
                    self.session_state.threshold_configs_by_image,
                    self.session_state.particles_configs_by_image,
                    self.session_state.annotation_imports,
                    )
                self.session_state.project_path = path
                self.session_state.project_save_time = path.stat().st_mtime if path.exists() else None
                self.set_dirty(False)

    def load_project(self, parent: QtWidgets.QWidget, path: pathlib.Path, read_metadata) -> bool:
        try:
            image_entries, settings, ann_map, roi_map, thr_map, part_map, import_map = load_project(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Load project failed", str(exc))
            return False
            images = []
            annotations: Dict[int, List[Keypoint]] = {}
            display_per_image: Dict[int, Dict[str, DisplayMapping]] = {}
            rois_by_image: Dict[int, List[Roi]] = {}
            for idx, entry in enumerate(image_entries):
                meta = read_metadata(pathlib.Path(entry["path"]))
                meta.id = idx
                meta.interpret_3d_as = entry.get("interpret_3d_as", meta.interpret_3d_as)
                images.append(meta)
                annotations[idx] = []
                entry_mapping = entry.get("display_mapping", {})
                if isinstance(entry_mapping, dict) and entry_mapping:
                    display_per_image[idx] = {
                        panel: mapping_from_dict(mdict, self.display_mapping.clone())
                        for panel, mdict in entry_mapping.items()
                        if isinstance(mdict, dict)
                        }
                    if idx in roi_map:
                        rois_by_image[idx] = [roi_from_dict(r, ridx) for ridx, r in enumerate(roi_map[idx]) if isinstance(r, dict)]
                        for idx, ann_path in ann_map.items():
                            if ann_path and ann_path.exists():
                                try:
                                    annotations[idx] = keypoints_from_json(ann_path)
                                except Exception:
                                    annotations[idx] = []
                                    self.session_state.images = images
                                    self.session_state.annotations = annotations
                                    self.session_state.annotation_index = {}
                                    self.session_state.annotations_loaded = {
                                        img.id: bool(self.session_state.annotations.get(img.id)) for img in images
                                        }
                                    self.session_state.image_states = {img.id: self._build_image_state(img) for img in images}
                                    if display_per_image:
                                        self.display_mapping.per_image = display_per_image
                                        if rois_by_image:
                                            self.rois_by_image = rois_by_image
                                            if thr_map:
                                                self.session_state.threshold_configs_by_image = {int(k): v for k, v in thr_map.items()}
                                                if part_map:
                                                    self.session_state.particles_configs_by_image = {int(k): v for k, v in part_map.items()}
                                                    if import_map:
                                                        self.session_state.annotation_imports = {int(k): v for k, v in import_map.items()}
                                                        self.session_state.project_path = path
                                                        self.session_state.project_save_time = path.stat().st_mtime if path.exists() else None
                                                        self.session_state.active_primary_id = int(settings.get("last_fov_index", 0))
                                                        self.session_state.active_support_id = int(settings.get("last_support_index", min(1, len(images) - 1)))
                                                        self.session_state.smlm_runs = list(settings.get("smlm_runs", []))
                                                        self.session_state.threshold_settings = dict(settings.get("threshold_settings", {}))
                                                        self.session_state.threshold_configs_by_image = dict(settings.get("threshold_configs_by_image", {}))
                                                        self.session_state.particles_configs_by_image = dict(settings.get("particles_configs_by_image", {}))
                                                        density_cfg = settings.get("density_config")
                                                        if isinstance(density_cfg, dict):
                                                            self.density_config = DensityConfig(**density_cfg)
                                                            infer_opts = settings.get("density_infer_options")
                                                            if isinstance(infer_opts, dict):
                                                                from phage_annotator.density_infer import DensityInferOptions

                                                                self.density_infer_options = DensityInferOptions(**infer_opts)
                                                                self.density_model_path = settings.get("density_model_path")
                                                                self.density_device = settings.get("density_device", "auto")
                                                                self.density_target_panel = settings.get("density_target_panel", "frame")
                                                                self._undo_stack.clear()
                                                                self._redo_stack.clear()
                                                                lut = settings.get("lut", 0)
                                                                if isinstance(lut, str) and lut in self._colormaps:
                                                                    self.set_lut(self._colormaps.index(lut))
                                                                    else:
                                                                        try:
                                                                            self.set_lut(int(lut))
                                                                        except (TypeError, ValueError):
                                                                            self.set_lut(0)
                                                                            self.set_dirty(False)
                                                                            self.state_changed.emit()
                                                                            self.annotations_changed.emit()
                                                                            return True

    def autosave_if_needed(self, parent: QtWidgets.QWidget, current_keypoints) -> Optional[pathlib.Path]:
        if not self._settings.value("autosaveRecoveryEnabled", True, type=bool):
            return None
            if not self.session_state.dirty:
                return None
                if self.session_state.project_path is None:
                    return None
                    project_dir = self.session_state.project_path.parent
                    recovery_dir = project_dir / ".recovery"
                    recovery_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    primary_name = pathlib.Path(self.session_state.images[self.session_state.active_primary_id].name).stem
                    recovery_path = recovery_dir / f"{ts}_{primary_name}.annotations.json"
                    points = current_keypoints()
                    save_keypoints_json(points, recovery_path)
                    return recovery_path

    def check_recovery(self, parent: QtWidgets.QWidget) -> None:
        if not self._settings.value("autosaveRecoveryEnabled", True, type=bool):
            return
            if self.session_state.project_path is None or self.session_state.project_save_time is None:
                return
                recovery_dir = self.session_state.project_path.parent / ".recovery"
                if not recovery_dir.exists():
                    return
                    candidates = sorted(recovery_dir.glob("*.annotations.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if not candidates:
                        return
                        latest = candidates[0]
                        if latest.stat().st_mtime <= self.session_state.project_save_time:
                            return
                            resp = QtWidgets.QMessageBox.question(
                                parent,
                                "Recovery available",
                                f"A recovery file newer than the project was found:\n{latest.name}\nRestore it?",
                                )
                            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                                return
                                try:
                                    kps = keypoints_from_json(latest)
                                    self.apply_recovery_points(kps)
                                    self.set_dirty(True)
                                except Exception as exc:
                                    QtWidgets.QMessageBox.critical(parent, "Recovery failed", str(exc))

    def apply_recovery_points(self, kps: Iterable[Keypoint]) -> None:
        """Apply recovered annotations by matching image names."""
        by_name: Dict[str, List[Keypoint]] = {}
        for kp in kps:
            by_name.setdefault(kp.image_name, []).append(kp)
            for img in self.session_state.images:
                if img.name in by_name:
                    updated = []
                    for kp in by_name[img.name]:
                        kp.image_id = img.id
                        updated.append(kp)
                        self.session_state.annotations[img.id] = updated
                        self.annotations_changed.emit()
