"""Project/session snapshot bridge and load/apply helpers."""

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


class SessionProjectBridgeMixin:
    """Mixin for loading project payloads into controller/session state."""

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

    def _apply_loaded_project_state(self, *, path: pathlib.Path, image_entries, images, annotations, display_per_image, rois_by_image, settings, thr_map, part_map, import_map, resolved_paths, relinked_images, missing_images) -> None:
        """Apply a deserialized project payload to session/controller state."""
        from phage_annotator.density.infer import DensityInferOptions

        self.session_state.images = images
        self.session_state.annotations = annotations
        self.session_state.annotation_index = {}
        self.session_state.annotations_loaded = {img.id: bool(self.session_state.annotations.get(img.id)) for img in images}
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
        feature_flags = settings.get("feature_flags", {})
        if isinstance(feature_flags, dict):
            self.session_state.feature_flags = {str(k): bool(v) for k, v in feature_flags.items()}
        workflow_metrics = settings.get("workflow_metrics", {})
        if isinstance(workflow_metrics, dict):
            self.session_state.workflow_metrics = dict(workflow_metrics)
        audit_log = settings.get("audit_log", [])
        if isinstance(audit_log, list):
            self.session_state.audit_log = [row for row in audit_log if isinstance(row, dict)]
        suggestion_metrics = settings.get("suggestion_metrics", {})
        if isinstance(suggestion_metrics, dict):
            self.session_state.suggestion_metrics.update({k: float(v) for k, v in suggestion_metrics.items() if isinstance(v, (int, float))})
        self.session_state.suggestion_strategy = str(settings.get("suggestion_strategy", "current_view"))
        self.session_state.suggestion_score_threshold = float(settings.get("suggestion_score_threshold", 0.0))
        self.session_state.suggestion_auto_retrain_enabled = bool(settings.get("suggestion_auto_retrain_enabled", True))
        self.session_state.suggestion_auto_retrain_min_labels = int(settings.get("suggestion_auto_retrain_min_labels", 25))
        self.session_state.annotation_space = str(settings.get("annotation_space", "stack"))
        self.session_state.generation_space = str(settings.get("generation_space", "stack"))
        self.session_state.assist_min_total_labels = int(settings.get("assist_min_total_labels", 30))
        self.session_state.assist_min_positive_labels = int(settings.get("assist_min_positive_labels", 15))
        self.session_state.assist_min_negative_labels = int(settings.get("assist_min_negative_labels", 15))
        self.session_state.assist_min_labels_per_context = int(settings.get("assist_min_labels_per_context", 10))
        self.session_state.evidence_layer_config = dict(settings.get("evidence_layer_config", {}))
        self.session_state.evidence_layer_presets = dict(settings.get("evidence_layer_presets", {}))
        self.session_state.disable_bulk_accept_when_stale = bool(settings.get("disable_bulk_accept_when_stale", True))
        self.session_state.smlm_runbook_enabled = bool(settings.get("smlm_runbook_enabled", False))
        if isinstance(settings.get("smlm_runbook_locked_profiles", {}), dict):
            self.session_state.smlm_runbook_locked_profiles = dict(settings.get("smlm_runbook_locked_profiles", {}))
        if isinstance(settings.get("smlm_runbook_provenance", []), list):
            self.session_state.smlm_runbook_provenance = list(settings.get("smlm_runbook_provenance", []))
        for store_name, payload_name in (("suggestions", "suggestions_by_image"), ("suggestion_history", "suggestion_history_by_image")):
            payload = settings.get(payload_name, {})
            if isinstance(payload, dict):
                for image_id, rows in payload.items():
                    if not isinstance(rows, list):
                        continue
                    try:
                        iid = int(image_id)
                    except (TypeError, ValueError):
                        continue
                    if iid not in getattr(self.session_state, store_name):
                        getattr(self.session_state, store_name)[iid] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        getattr(self.session_state, store_name)[iid].append(
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
                                supporting_modalities=list(row.get("supporting_modalities", []) or []),
                                cross_modality_consistency_score=row.get("cross_modality_consistency_score"),
                                control_contradiction_score=row.get("control_contradiction_score"),
                                scale_sigma=float(row.get("scale_sigma", 1.0)),
                                psf_radius=float(row.get("psf_radius", 6.0)),
                                roi_id=row.get("roi_id"),
                                uncertainty_score=row.get("uncertainty_score"),
                                uncertainty_reason=str(row.get("uncertainty_reason", "") or ""),
                                density_context=dict(row.get("density_context", {}) or {}),
                                score_components=dict(row.get("score_components", {})),
                                status=str(row.get("status", "proposed")),
                                meta=dict(row.get("meta", {})),
                            )
                        )
        self.session_state.suggestion_ranker_state = dict(settings.get("suggestion_ranker_state", {}))
        samples = settings.get("suggestion_training_samples", [])
        if isinstance(samples, list):
            self.session_state.suggestion_training_samples = [row for row in samples if isinstance(row, dict)]
        self.session_state.suggestion_training_pending = int(settings.get("suggestion_training_pending", 0))
        context_stats = settings.get("suggestion_context_stats", {})
        if isinstance(context_stats, dict):
            self.session_state.suggestion_context_stats = {
                str(k): {"total": int(dict(v).get("total", 0)), "pos": int(dict(v).get("pos", 0)), "neg": int(dict(v).get("neg", 0))}
                for k, v in context_stats.items()
                if isinstance(v, dict)
            }
        if hasattr(self, "restore_suggestion_ranker"):
            self.restore_suggestion_ranker()
        if isinstance(settings.get("density_config"), dict):
            self.density_config = DensityConfig(**settings.get("density_config"))
        if isinstance(settings.get("density_infer_options"), dict):
            self.density_infer_options = DensityInferOptions(**settings.get("density_infer_options"))
        self.density_model_path = settings.get("density_model_path")
        self.density_device = settings.get("density_device", "auto")
        self.density_target_panel = settings.get("density_target_panel", "frame")
        self._settings.setValue("autoRoiShape", settings.get("auto_roi_shape", "box"))
        self._settings.setValue("autoRoiMode", settings.get("auto_roi_mode", "W/H"))
        self._settings.setValue("autoRoiW", int(settings.get("auto_roi_w", 100)))
        self._settings.setValue("autoRoiH", int(settings.get("auto_roi_h", 100)))
        self._settings.setValue("autoRoiArea", int(settings.get("auto_roi_area", 100 * 100)))
        workspace_snapshot = settings.get("workspace_snapshot")
        snapshot_has_display_mapping = False
        if isinstance(workspace_snapshot, dict):
            self.session_state.workspace_snapshot = dict(workspace_snapshot)
            snapshot_session_layer = workspace_snapshot.get("session_workspace", {})
            snapshot_has_display_mapping = bool(isinstance(snapshot_session_layer, dict) and isinstance(snapshot_session_layer.get("display_mapping_frame"), dict) and snapshot_session_layer.get("display_mapping_frame"))
            apply_workspace_snapshot_to_controller(self, workspace_snapshot)
        elif isinstance(settings.get("ui_workspace_state"), dict):
            self.session_state.workspace_snapshot = {"schema": "workspace_snapshot.v1", "session_workspace": {"ui_workspace": dict(settings.get("ui_workspace_state", {}))}}
        if isinstance(settings.get("workspace_layer_registry"), dict):
            self.session_state.workspace_layer_registry = dict(settings.get("workspace_layer_registry"))
        self._undo_stack.clear()
        self._redo_stack.clear()
        if not snapshot_has_display_mapping:
            lut = settings.get("lut", 0)
            if isinstance(lut, str) and lut in self._colormaps:
                self.set_lut(self._colormaps.index(lut))
            else:
                try:
                    self.set_lut(int(lut))
                except (TypeError, ValueError):
                    self.set_lut(0)
        self.set_dirty(False)
        unresolved_rows = list(
            dict(getattr(self.session_state, "project_relink_report", {}) or {}).get("unresolved", []) or []
        )
        self._set_project_relink_report(
            path=path,
            loaded_count=len(images),
            relinked_images=relinked_images,
            missing_images=missing_images,
            unresolved_rows=unresolved_rows,
            partial_load=bool(missing_images),
        )
        emit_state_changed(self)
        emit_annotations_changed(self)
