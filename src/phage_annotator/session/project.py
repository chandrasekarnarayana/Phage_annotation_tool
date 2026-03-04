"""Project persistence and recovery helpers."""

from __future__ import annotations

from datetime import datetime
import pathlib
from typing import Dict, Iterable, List, Optional

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.annotation.core import (
    Keypoint,
    PointSuggestion,
    keypoints_from_json,
    save_keypoints_csv,
    save_keypoints_json,
)
from phage_annotator.data.display_mapping import DisplayMapping, mapping_from_dict, mapping_to_dict
from phage_annotator.config.density import DensityConfig
from phage_annotator.io.projects import load_project, save_project
from phage_annotator.roi.manager import Roi, roi_from_dict


class SessionProjectMixin:
    """Mixin for project persistence and recovery helpers."""

    @staticmethod
    def _resolve_project_image_path(
        entry: Dict[str, object], project_dir: pathlib.Path
    ) -> pathlib.Path:
        """Resolve moved/relocated image path from project entry."""
        raw = pathlib.Path(str(entry.get("path", "")))
        if raw.exists():
            return raw
        rel = entry.get("path_relative")
        if isinstance(rel, str) and rel.strip():
            candidate = (project_dir / rel).resolve()
            if candidate.exists():
                return candidate
        image_name = str(entry.get("image_name", raw.name)).strip()
        if image_name:
            direct = (project_dir / image_name).resolve()
            if direct.exists():
                return direct
            # Best-effort recursive search under project dir for renamed/moved roots.
            matches = list(project_dir.rglob(image_name))
            for candidate in matches:
                if candidate.is_file():
                    return candidate.resolve()
        return raw

    @staticmethod
    def _prompt_relink_missing_images(
        parent: QtWidgets.QWidget,
        missing_entries: List[tuple[int, Dict[str, object], pathlib.Path]],
        *,
        mode: str = "ask",
    ) -> Dict[int, pathlib.Path]:
        """Prompt user to relink missing images (folder scan or per-file selection)."""
        if not missing_entries:
            return {}
        names = []
        for _, entry, fallback in missing_entries:
            image_name = str(entry.get("image_name", fallback.name)).strip()
            if image_name:
                names.append(image_name)
        if not names:
            return {}
        relinked: Dict[int, pathlib.Path] = {}
        if mode not in {"ask", "auto", "manual"}:
            mode = "ask"
        resp = QtWidgets.QMessageBox.StandardButton.Yes
        if mode == "ask":
            resp = QtWidgets.QMessageBox.question(
                parent,
                "Missing images",
                (
                    f"{len(missing_entries)} project image(s) were not found.\n"
                    "Yes = select one folder for auto-relink\n"
                    "No = select each missing file manually"
                ),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
        elif mode == "manual":
            resp = QtWidgets.QMessageBox.StandardButton.No
        else:
            resp = QtWidgets.QMessageBox.StandardButton.Yes
        if resp == QtWidgets.QMessageBox.StandardButton.Cancel:
            return relinked
        if resp == QtWidgets.QMessageBox.StandardButton.Yes:
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                parent,
                "Select folder containing relocated images",
                str(pathlib.Path.cwd()),
            )
            if not folder:
                return relinked
            folder_path = pathlib.Path(folder)
            for idx, entry, fallback in missing_entries:
                image_name = str(entry.get("image_name", fallback.name)).strip()
                if not image_name:
                    continue
                direct = (folder_path / image_name).resolve()
                if direct.exists() and direct.is_file():
                    relinked[idx] = direct
                    continue
                matches = [p for p in folder_path.rglob(image_name) if p.is_file()]
                if matches:
                    relinked[idx] = matches[0].resolve()
            return relinked
        for idx, entry, fallback in missing_entries:
            image_name = str(entry.get("image_name", fallback.name)).strip()
            start_dir = str(pathlib.Path.cwd())
            if image_name:
                start_dir = str(pathlib.Path.cwd() / image_name)
            selected, _ = QtWidgets.QFileDialog.getOpenFileName(
                parent,
                f"Locate image: {image_name or fallback.name}",
                start_dir,
                "Image files (*.tif *.tiff *.ome.tif *.ome.tiff);;All files (*)",
            )
            if selected:
                selected_path = pathlib.Path(selected).resolve()
                if selected_path.exists() and selected_path.is_file():
                    relinked[idx] = selected_path
        return relinked

    def _annotation_export_timestamp(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _current_annotation_target(self) -> str:
        target = str(getattr(self, "annotate_target", "frame")).strip()
        return target or "frame"

    def _image_export_context(self, image_id: int) -> Dict[str, object]:
        image = next(
            (
                img
                for img in self.session_state.images
                if int(getattr(img, "id", -1)) == int(image_id)
            ),
            None,
        )
        if image is None:
            return {"image_id": int(image_id)}
        shape = list(getattr(image, "shape", ()) or ())
        return {
            "image_id": int(getattr(image, "id", image_id)),
            "image_name": str(getattr(image, "name", "")),
            "image_path": str(pathlib.Path(str(getattr(image, "path", ""))).resolve()),
            "shape": shape,
            "dtype": str(getattr(image, "dtype", "")),
            "has_time": bool(getattr(image, "has_time", False)),
            "has_z": bool(getattr(image, "has_z", False)),
            "ome_axes": str(getattr(image, "ome_axes", "") or ""),
            "interpret_3d_as": str(getattr(image, "interpret_3d_as", "auto")),
        }

    def build_annotation_export_metadata(
        self,
        image_id: int,
        *,
        export_format: str,
        export_path: Optional[pathlib.Path] = None,
    ) -> Dict[str, object]:
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
        annotation_count = len(self.session_state.annotations.get(image_id, []))
        payload: Dict[str, object] = {
            "tool": "PhageAnnotator",
            "schema": "annotation_export.v1",
            "exported_at": self._annotation_export_timestamp(),
            "export_format": str(export_format),
            "annotation_count": int(annotation_count),
            "linked_image": image_ctx,
            "annotation_context": {
                "scope": str(getattr(self.view_state, "annotation_scope", "current")),
                "target": self._current_annotation_target(),
                "annotation_space": str(
                    getattr(self.session_state, "annotation_space", "stack")
                ),
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

        # Add ROI if set
        roi = self.view_state.roi_spec
        if roi and roi.shape != "none":
            meta["roi"] = {
                "shape": roi.shape,
            }
            if roi.shape == "box":
                meta["roi"]["rect"] = (roi.x, roi.y, roi.w, roi.h)
            elif roi.shape == "circle":
                center_x = roi.x + roi.w / 2
                center_y = roi.y + roi.h / 2
                radius = roi.w / 2
                meta["roi"]["center"] = (center_x, center_y)
                meta["roi"]["radius"] = radius

        # Add crop if set
        crop = self.view_state.crop_rect
        if crop and crop != (0, 0, 0, 0):
            meta["crop"] = crop

        # Add display settings for the current image
        if any(int(getattr(img, "id", -1)) == int(image_id) for img in self.session_state.images):
            mapping = self.display_mapping.mapping_for(int(image_id), "frame")
            meta["display"] = {
                "win": {
                    "min": mapping.min_val,
                    "max": mapping.max_val,
                },
                "gamma": mapping.gamma,
                "lut": mapping.lut,
            }

        return meta

    def save_csv(self, parent: QtWidgets.QWidget, path: pathlib.Path) -> None:
        """Save annotations for the active image to CSV."""
        image_id = self.session_state.active_primary_id
        points = self.session_state.annotations.get(image_id, [])
        try:
            meta = self.build_annotation_export_metadata(
                image_id,
                export_format="csv",
                export_path=path,
            )
            save_keypoints_csv(points, path, meta=meta)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Save CSV failed", str(exc))
            return
        self.set_dirty(False)

    def save_json(self, parent: QtWidgets.QWidget, path: pathlib.Path) -> None:
        """Save annotations for the active image to JSON."""
        image_id = self.session_state.active_primary_id
        points = self.session_state.annotations.get(image_id, [])
        try:
            meta = self.build_annotation_export_metadata(
                image_id,
                export_format="json",
                export_path=path,
            )
            save_keypoints_json(points, path, meta=meta)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Save JSON failed", str(exc))
            return
        self.set_dirty(False)

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
        display_mappings: Dict[int, Dict[str, dict]] = {}
        for image_id, panels in self.display_mapping.per_image.items():
            display_mappings[image_id] = {panel: mapping_to_dict(mapping) for panel, mapping in panels.items()}

        # Phase ι: Pass modality_manager for persistence
        modality_manager = getattr(self.session_state, "modality_manager", None)
        channel_display_settings = getattr(
            self.session_state, "channel_display_settings", None
        )

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
            modality_manager=modality_manager,
            channel_display_settings=channel_display_settings,
        )
        self.session_state.project_path = path
        self.session_state.project_save_time = path.stat().st_mtime if path.exists() else None
        self.set_dirty(False)

    def load_project(
        self,
        parent: QtWidgets.QWidget,
        path: pathlib.Path,
        read_metadata,
        *,
        relink_mode: str = "ask",
    ) -> bool:
        try:
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
            ) = load_project(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(parent, "Load project failed", str(exc))
            return False
        
        # Phase ι: Restore modality_manager if present
        from phage_annotator.session.modality import ModalityManager
        if modality_manager_data is not None:
            try:
                self.session_state.modality_manager = ModalityManager.from_dict(modality_manager_data)
            except Exception as e:
                # Graceful fallback if deserialization fails
                self.session_state.modality_manager = None
        else:
            self.session_state.modality_manager = None
        self.session_state.channel_display_settings = channel_display_settings
        
        images = []
        annotations: Dict[int, List[Keypoint]] = {}
        display_per_image: Dict[int, Dict[str, DisplayMapping]] = {}
        rois_by_image: Dict[int, List[Roi]] = {}
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
            manual = self._prompt_relink_missing_images(
                parent,
                missing_entries,
                mode=relink_mode,
            )
            for idx, relinked in manual.items():
                resolved_paths[idx] = relinked
                original_path = pathlib.Path(str(image_entries[idx].get("path", "")))
                if original_path and original_path != relinked:
                    relinked_images.append(f"{original_path} -> {relinked}")
        for idx, entry in enumerate(image_entries):
            img_path = resolved_paths.get(idx)
            if img_path is None:
                fallback = self._resolve_project_image_path(entry, path.parent)
                missing_images.append(str(fallback))
                continue
            try:
                meta = read_metadata(img_path)
            except Exception as e:
                missing_images.append(f"{img_path} (error: {e})")
                continue
                
            meta.id = len(images)  # Use actual index, not entry index
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
            # Use entry idx for roi_map lookup, but store with actual image id
            if idx in roi_map:
                rois_by_image[meta.id] = [
                    roi_from_dict(r, ridx) for ridx, r in enumerate(roi_map[idx]) if isinstance(r, dict)
                ]
        
        # Show warning if any images are missing
        if missing_images:
            msg = f"Loaded {len(images)} images, but {len(missing_images)} could not be found:\n\n"
            msg += "\n".join(missing_images[:10])  # Show first 10
            if len(missing_images) > 10:
                msg += f"\n... and {len(missing_images) - 10} more"
            if relinked_images:
                msg += "\n\nRelinked images:\n"
                msg += "\n".join(relinked_images[:5])
                if len(relinked_images) > 5:
                    msg += f"\n... and {len(relinked_images) - 5} more"
            QtWidgets.QMessageBox.warning(parent, "Some images not found", msg)
        
        # If no images loaded at all, fail
        if not images:
            unresolved_rows = []
            for idx, entry in enumerate(image_entries):
                if idx not in resolved_paths:
                    fallback = self._resolve_project_image_path(entry, path.parent)
                    unresolved_rows.append(
                        {
                            "index": int(idx),
                            "image_name": str(entry.get("image_name", fallback.name)),
                            "original_path": str(entry.get("path", fallback)),
                            "resolved_attempt": str(fallback),
                        }
                    )
            self.session_state.project_relink_report = {
                "project_path": str(path),
                "loaded_count": 0,
                "relinked": list(relinked_images),
                "missing": list(missing_images),
                "unresolved": unresolved_rows,
            }
            QtWidgets.QMessageBox.critical(parent, "Load failed", "No images could be loaded from the project.")
            return False
            
        for idx, ann_path in ann_map.items():
            # Map entry idx to actual image id by matching paths
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
        self.session_state.images = images
        self.session_state.annotations = annotations
        self.session_state.annotation_index = {}
        self.session_state.annotations_loaded = {
            img.id: bool(self.session_state.annotations.get(img.id)) for img in images
        }
        self.session_state.suggestions = {img.id: [] for img in images}
        self.session_state.suggestion_history = {img.id: [] for img in images}
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
        default_support = min(1, len(images) - 1)
        requested_primary = int(settings.get("last_fov_index", 0))
        requested_support = int(settings.get("last_support_index", default_support))
        max_id = max(0, len(images) - 1)
        self.session_state.active_primary_id = min(max(0, requested_primary), max_id)
        self.session_state.active_support_id = min(max(0, requested_support), max_id)
        self.session_state.smlm_runs = list(settings.get("smlm_runs", []))
        self.session_state.threshold_settings = dict(settings.get("threshold_settings", {}))
        self.session_state.threshold_configs_by_image = dict(settings.get("threshold_configs_by_image", {}))
        self.session_state.particles_configs_by_image = dict(settings.get("particles_configs_by_image", {}))
        self.session_state.current_user = str(settings.get("current_user", "local_user"))
        audit_log = settings.get("audit_log", [])
        if isinstance(audit_log, list):
            self.session_state.audit_log = [row for row in audit_log if isinstance(row, dict)]
        suggestion_metrics = settings.get("suggestion_metrics", {})
        if isinstance(suggestion_metrics, dict):
            self.session_state.suggestion_metrics.update(
                {k: float(v) for k, v in suggestion_metrics.items() if isinstance(v, (int, float))}
            )
        self.session_state.suggestion_strategy = str(settings.get("suggestion_strategy", "current_view"))
        self.session_state.suggestion_score_threshold = float(
            settings.get("suggestion_score_threshold", 0.0)
        )
        self.session_state.suggestion_auto_retrain_enabled = bool(
            settings.get("suggestion_auto_retrain_enabled", True)
        )
        self.session_state.suggestion_auto_retrain_min_labels = int(
            settings.get("suggestion_auto_retrain_min_labels", 25)
        )
        self.session_state.annotation_space = str(settings.get("annotation_space", "stack"))
        self.session_state.generation_space = str(settings.get("generation_space", "stack"))
        self.session_state.assist_min_total_labels = int(
            settings.get("assist_min_total_labels", 30)
        )
        self.session_state.assist_min_positive_labels = int(
            settings.get("assist_min_positive_labels", 15)
        )
        self.session_state.assist_min_negative_labels = int(
            settings.get("assist_min_negative_labels", 15)
        )
        self.session_state.assist_min_labels_per_context = int(
            settings.get("assist_min_labels_per_context", 10)
        )
        self.session_state.evidence_layer_config = dict(
            settings.get("evidence_layer_config", {})
        )
        self.session_state.evidence_layer_presets = dict(
            settings.get("evidence_layer_presets", {})
        )
        self.session_state.disable_bulk_accept_when_stale = bool(
            settings.get("disable_bulk_accept_when_stale", True)
        )
        self.session_state.smlm_runbook_enabled = bool(
            settings.get("smlm_runbook_enabled", False)
        )
        runbook_locked = settings.get("smlm_runbook_locked_profiles", {})
        if isinstance(runbook_locked, dict):
            self.session_state.smlm_runbook_locked_profiles = dict(runbook_locked)
        runbook_prov = settings.get("smlm_runbook_provenance", [])
        if isinstance(runbook_prov, list):
            self.session_state.smlm_runbook_provenance = list(runbook_prov)
        suggestion_payload = settings.get("suggestions_by_image", {})
        if isinstance(suggestion_payload, dict):
            for image_id, rows in suggestion_payload.items():
                if not isinstance(rows, list):
                    continue
                try:
                    iid = int(image_id)
                except (TypeError, ValueError):
                    continue
                if iid not in self.session_state.suggestions:
                    self.session_state.suggestions[iid] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    self.session_state.suggestions[iid].append(
                        PointSuggestion(
                            image_id=int(row.get("image_id", iid)),
                            image_name=str(row.get("image_name", "")),
                            t=int(row.get("t", -1)),
                            z=int(row.get("z", -1)),
                            y=float(row.get("y", 0.0)),
                            x=float(row.get("x", 0.0)),
                            score=float(row.get("score", row.get("confidence", 0.0))),
                            label=str(row.get("label", "phage")),
                            suggestion_id=str(row.get("suggestion_id", "")),
                            source_model=str(row.get("source_model", "unknown")),
                            source_modality=str(row.get("source_modality", "raw")),
                            scale_sigma=float(row.get("scale_sigma", 1.0)),
                            psf_radius=float(row.get("psf_radius", 6.0)),
                            roi_id=row.get("roi_id"),
                            score_components=dict(row.get("score_components", {})),
                            status=str(row.get("status", "proposed")),
                            meta=dict(row.get("meta", {})),
                        )
                    )
        suggestion_history_payload = settings.get("suggestion_history_by_image", {})
        if isinstance(suggestion_history_payload, dict):
            for image_id, rows in suggestion_history_payload.items():
                if not isinstance(rows, list):
                    continue
                try:
                    iid = int(image_id)
                except (TypeError, ValueError):
                    continue
                if iid not in self.session_state.suggestion_history:
                    self.session_state.suggestion_history[iid] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    self.session_state.suggestion_history[iid].append(
                        PointSuggestion(
                            image_id=int(row.get("image_id", iid)),
                            image_name=str(row.get("image_name", "")),
                            t=int(row.get("t", -1)),
                            z=int(row.get("z", -1)),
                            y=float(row.get("y", 0.0)),
                            x=float(row.get("x", 0.0)),
                            score=float(row.get("score", row.get("confidence", 0.0))),
                            label=str(row.get("label", "phage")),
                            suggestion_id=str(row.get("suggestion_id", "")),
                            source_model=str(row.get("source_model", "unknown")),
                            source_modality=str(row.get("source_modality", "raw")),
                            scale_sigma=float(row.get("scale_sigma", 1.0)),
                            psf_radius=float(row.get("psf_radius", 6.0)),
                            roi_id=row.get("roi_id"),
                            score_components=dict(row.get("score_components", {})),
                            status=str(row.get("status", "proposed")),
                            meta=dict(row.get("meta", {})),
                        )
                    )
        self.session_state.suggestion_ranker_state = dict(
            settings.get("suggestion_ranker_state", {})
        )
        samples = settings.get("suggestion_training_samples", [])
        if isinstance(samples, list):
            self.session_state.suggestion_training_samples = [
                row for row in samples if isinstance(row, dict)
            ]
        self.session_state.suggestion_training_pending = int(
            settings.get("suggestion_training_pending", 0)
        )
        context_stats = settings.get("suggestion_context_stats", {})
        if isinstance(context_stats, dict):
            self.session_state.suggestion_context_stats = {
                str(k): {
                    "total": int(dict(v).get("total", 0)),
                    "pos": int(dict(v).get("pos", 0)),
                    "neg": int(dict(v).get("neg", 0)),
                }
                for k, v in context_stats.items()
                if isinstance(v, dict)
            }
        if hasattr(self, "restore_suggestion_ranker"):
            self.restore_suggestion_ranker()
        density_cfg = settings.get("density_config")
        if isinstance(density_cfg, dict):
            self.density_config = DensityConfig(**density_cfg)
        infer_opts = settings.get("density_infer_options")
        if isinstance(infer_opts, dict):
            from phage_annotator.density.infer import DensityInferOptions

            self.density_infer_options = DensityInferOptions(**infer_opts)
        self.density_model_path = settings.get("density_model_path")
        self.density_device = settings.get("density_device", "auto")
        self.density_target_panel = settings.get("density_target_panel", "frame")
        self._settings.setValue("autoRoiShape", settings.get("auto_roi_shape", "box"))
        self._settings.setValue("autoRoiMode", settings.get("auto_roi_mode", "W/H"))
        self._settings.setValue("autoRoiW", int(settings.get("auto_roi_w", 100)))
        self._settings.setValue("autoRoiH", int(settings.get("auto_roi_h", 100)))
        self._settings.setValue("autoRoiArea", int(settings.get("auto_roi_area", 100 * 100)))

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
        unresolved_rows = []
        for idx, entry in enumerate(image_entries):
            if idx not in resolved_paths:
                fallback = self._resolve_project_image_path(entry, path.parent)
                unresolved_rows.append(
                    {
                        "index": int(idx),
                        "image_name": str(entry.get("image_name", fallback.name)),
                        "original_path": str(entry.get("path", fallback)),
                        "resolved_attempt": str(fallback),
                    }
                )
        self.session_state.project_relink_report = {
            "project_path": str(path),
            "loaded_count": int(len(images)),
            "relinked": list(relinked_images),
            "missing": list(missing_images),
            "unresolved": unresolved_rows,
        }
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

    def find_recovery_file(self, current_keypoints) -> Optional[pathlib.Path]:
        """Return the newest recovery file if it is newer than the project save."""
        if not self._settings.value("autosaveRecoveryEnabled", True, type=bool):
            return None
        if self.session_state.project_path is None or self.session_state.project_save_time is None:
            return None
        recovery_dir = self.session_state.project_path.parent / ".recovery"
        if not recovery_dir.exists():
            return None
        candidates = sorted(recovery_dir.glob("*.annotations.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            return None
        latest = candidates[0]
        if latest.stat().st_mtime <= self.session_state.project_save_time:
            return None
        return latest

    def restore_recovery(self, path: pathlib.Path) -> None:
        """Load a recovery file and apply annotations."""
        kps = keypoints_from_json(path)
        self.apply_recovery_points(kps)
        self.set_dirty(True)

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
