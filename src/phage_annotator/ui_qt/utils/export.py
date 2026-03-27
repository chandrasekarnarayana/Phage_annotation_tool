"""Export and project save/load helpers."""

from __future__ import annotations

import base64
import pathlib
import re
from datetime import datetime
from typing import Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import compute_projection
from phage_annotator.core.workspace_snapshot import (
    build_workspace_snapshot,
    extract_ui_workspace_state,
    workspace_layer_registry,
)
from phage_annotator.io.metadata.annotation import format_tokens
from phage_annotator.data.display_mapping import build_norm
from phage_annotator.ui_qt.rendering.export_view import (
    ExportOptions, render_view_to_array, render_layer_to_array,
    render_chunk_to_array, calculate_export_chunks, create_streaming_writer
)
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import cmap_for
from phage_annotator.rendering.scalebar import ScaleBarSpec


class ExportMixin:
    """Mixin for saving/loading annotations and projects."""

    @staticmethod
    def _tokenize_filename_value(value: object) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"[^a-z0-9._-]+", "-", text)
        return text.strip("-") or "na"

    def _annotation_filename_context_tokens(self) -> str:
        context = (
            dict(self.controller.current_annotation_context() or {})
            if hasattr(self.controller, "current_annotation_context")
            else {}
        )
        image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", -1)))
        base_meta = self.controller.build_annotation_metadata(image_id)
        scope = self._tokenize_filename_value(
            getattr(self, "annotation_scope", "current")
        )
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        target = self._tokenize_filename_value(context.get("panel_key", getattr(self, "annotate_target", default_target)))
        space = self._tokenize_filename_value(
            context.get("annotation_space", getattr(self.controller.session_state, "annotation_space", "stack"))
        )
        context_key = self._tokenize_filename_value(context.get("context_key", ""))
        t_val = int(getattr(self.controller.view_state, "t", 0))
        z_val = int(getattr(self.controller.view_state, "z", 0))
        roi = base_meta.get("roi")
        roi_token = "none"
        if isinstance(roi, dict):
            roi_token = self._tokenize_filename_value(roi.get("shape", "set"))
        crop = base_meta.get("crop")
        crop_token = "0"
        if isinstance(crop, (list, tuple)) and len(crop) == 4:
            crop_token = "1"
        return (
            f"__scope={scope}"
            f"__target={target}"
            f"__space={space}"
            f"__ctx={context_key}"
            f"__t={t_val}"
            f"__z={z_val}"
            f"__roi={roi_token}"
            f"__crop={crop_token}"
        )

    @staticmethod
    def _serialize_suggestion(suggestion) -> dict:
        return {
            "image_id": int(getattr(suggestion, "image_id", -1)),
            "image_name": str(getattr(suggestion, "image_name", "")),
            "t": int(getattr(suggestion, "t", -1)),
            "z": int(getattr(suggestion, "z", -1)),
            "y": float(getattr(suggestion, "y", 0.0)),
            "x": float(getattr(suggestion, "x", 0.0)),
            "score": float(getattr(suggestion, "score", getattr(suggestion, "confidence", 0.0))),
            "label": str(getattr(suggestion, "label", "phage")),
            "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
            "source_model": str(getattr(suggestion, "source_model", "unknown")),
            "source_modality": str(getattr(suggestion, "source_modality", "raw")),
            "supporting_modalities": list(getattr(suggestion, "supporting_modalities", []) or []),
            "cross_modality_consistency_score": getattr(suggestion, "cross_modality_consistency_score", None),
            "control_contradiction_score": getattr(suggestion, "control_contradiction_score", None),
            "scale_sigma": float(getattr(suggestion, "scale_sigma", 1.0)),
            "psf_radius": float(getattr(suggestion, "psf_radius", 6.0)),
            "roi_id": getattr(suggestion, "roi_id", None),
            "uncertainty_score": getattr(suggestion, "uncertainty_score", None),
            "uncertainty_reason": str(getattr(suggestion, "uncertainty_reason", "") or ""),
            "density_context": dict(getattr(suggestion, "density_context", {}) or {}),
            "score_components": dict(getattr(suggestion, "score_components", {})),
            "status": str(getattr(suggestion, "status", "proposed")),
            "meta": dict(getattr(suggestion, "meta", {})),
        }

    @staticmethod
    def _encode_qbytearray(value) -> str:
        """Encode a QByteArray-like value to ASCII base64 string."""
        if value is None:
            return ""
        try:
            raw = bytes(value)
            if not raw:
                return ""
            return base64.b64encode(raw).decode("ascii")
        except Exception:
            return ""

    @staticmethod
    def _decode_qbytearray(value: object):
        """Decode ASCII base64 string to bytes for Qt restore methods."""
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return base64.b64decode(value.encode("ascii"))
        except Exception:
            return None

    def _capture_ui_workspace_state(self) -> dict:
        """Capture UI-level workspace state for exact project restore."""
        linked_zoom_bounds = None
        zoom_state = getattr(self, "_last_zoom_linked", None)
        if (
            isinstance(zoom_state, tuple)
            and len(zoom_state) == 2
            and all(isinstance(bounds, tuple) and len(bounds) == 2 for bounds in zoom_state)
        ):
            linked_zoom_bounds = {
                "xlim": [float(zoom_state[0][0]), float(zoom_state[0][1])],
                "ylim": [float(zoom_state[1][0]), float(zoom_state[1][1])],
            }
        state = {
            "panel_visibility": dict(getattr(self, "_panel_visibility", {}) or {}),
            "annotation_panel_visibility": dict(
                getattr(self, "_annotation_panel_visibility", {}) or {}
            ),
            "canvas_layout_rows": int(getattr(self, "_canvas_layout_rows", 0) or 0),
            "canvas_layout_cols": int(getattr(self, "_canvas_layout_cols", 0) or 0),
            "active_layout_preset": str(getattr(self, "_active_layout_preset", "Default") or "Default"),
            "sidebar_collapsed": bool(getattr(self, "_sidebar_collapsed", False)),
            "right_sidebar_collapsed": bool(getattr(self, "_right_sidebar_collapsed", False)),
            "sidebar_index": int(getattr(getattr(self, "sidebar_stack", None), "currentIndex", lambda: 0)()),
            "window_geometry_b64": self._encode_qbytearray(self.saveGeometry()),
            "window_state_b64": self._encode_qbytearray(self.saveState()),
            "linked_zoom_bounds": linked_zoom_bounds,
        }
        return state

    def _restore_ui_workspace_state(self, ui_state: dict) -> None:
        """Restore UI-level workspace state captured in project snapshot."""
        if not isinstance(ui_state, dict) or not ui_state:
            return

        panel_visibility = ui_state.get("panel_visibility")
        if isinstance(panel_visibility, dict):
            self._panel_visibility.update({str(k): bool(v) for k, v in panel_visibility.items()})

        point_visibility = ui_state.get("annotation_panel_visibility")
        if isinstance(point_visibility, dict):
            self._annotation_panel_visibility = {
                str(k): bool(v) for k, v in point_visibility.items()
            }

        self._canvas_layout_rows = int(ui_state.get("canvas_layout_rows", self._canvas_layout_rows))
        self._canvas_layout_cols = int(ui_state.get("canvas_layout_cols", self._canvas_layout_cols))
        self._active_layout_preset = str(
            ui_state.get("active_layout_preset", getattr(self, "_active_layout_preset", "Default"))
        )

        if bool(ui_state.get("sidebar_collapsed", False)) and hasattr(self, "_collapse_sidebar"):
            self._collapse_sidebar()
        elif hasattr(self, "_expand_sidebar"):
            self._expand_sidebar()

        if bool(ui_state.get("right_sidebar_collapsed", False)) and hasattr(self, "_collapse_right_sidebar"):
            self._collapse_right_sidebar()
        elif hasattr(self, "_expand_right_sidebar"):
            self._expand_right_sidebar()

        stack_idx = int(ui_state.get("sidebar_index", 0) or 0)
        if getattr(self, "sidebar_stack", None) is not None:
            stack_idx = max(0, min(stack_idx, max(0, self.sidebar_stack.count() - 1)))
            self.sidebar_stack.setCurrentIndex(stack_idx)

        linked_zoom_bounds = ui_state.get("linked_zoom_bounds")
        if isinstance(linked_zoom_bounds, dict):
            try:
                xlim = tuple(float(v) for v in linked_zoom_bounds.get("xlim", ()))
                ylim = tuple(float(v) for v in linked_zoom_bounds.get("ylim", ()))
                if len(xlim) == 2 and len(ylim) == 2:
                    self._last_zoom_linked = (xlim, ylim)
            except Exception:
                pass

        if hasattr(self, "_rebuild_canvas_for_layout"):
            self._rebuild_canvas_for_layout()
        if hasattr(self, "_refresh_panel_policy_controls"):
            self._refresh_panel_policy_controls()
        if hasattr(self, "_sync_panel_visibility_state"):
            self._sync_panel_visibility_state()

        # Geometry/state restore is optional best-effort and may be skipped in edge cases.
        geometry_bytes = self._decode_qbytearray(ui_state.get("window_geometry_b64"))
        state_bytes = self._decode_qbytearray(ui_state.get("window_state_b64"))
        if geometry_bytes:
            try:
                self.restoreGeometry(geometry_bytes)
            except Exception:
                pass
        if state_bytes:
            try:
                self.restoreState(state_bytes)
            except Exception:
                pass

    def _save_csv(self) -> None:
        csv_path, _ = self._default_export_paths()
        self.controller.save_csv(self, csv_path)
        self._status_success(f"Saved CSV to {csv_path}", source="export.save_csv")
        self._mark_dirty(False)

    def _quick_save_csv(self) -> None:
        """Quick-save annotations CSV to the default path."""
        csv_path, _ = self._default_export_paths()
        self.controller.save_csv(self, csv_path)
        self._status_success(f"Saved CSV to {csv_path}", source="export.quick_save_csv")
        self._mark_dirty(False)

    def _save_json(self) -> None:
        _, json_path = self._default_export_paths()
        self.controller.save_json(self, json_path)
        self._status_success(f"Saved JSON to {json_path}", source="export.save_json")
        self._mark_dirty(False)

    def _default_export_paths(self) -> Tuple[pathlib.Path, pathlib.Path]:
        context = (
            dict(self.controller.current_annotation_context() or {})
            if hasattr(self.controller, "current_annotation_context")
            else {}
        )
        panel_key = str(context.get("panel_key", getattr(self, "annotate_target", "frame")) or "frame")
        binding = (
            self.controller.annotation_binding_for_panel(panel_key)
            if hasattr(self.controller, "annotation_binding_for_panel")
            else {}
        )
        if binding.get("path"):
            bound_path = pathlib.Path(str(binding["path"]))
            csv_path = bound_path if bound_path.suffix.lower() == ".csv" else bound_path.with_suffix(".csv")
            json_path = bound_path if bound_path.suffix.lower() == ".json" else bound_path.with_suffix(".json")
            return csv_path, json_path
        source_image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", 0)))
        source_image = next(
            (
                img for img in getattr(self, "images", [])
                if int(getattr(img, "id", -1)) == source_image_id
            ),
            self.primary_image,
        )
        first = source_image.path
        csv_path = pathlib.Path(first).with_suffix(".annotations.csv")
        json_path = pathlib.Path(first).with_suffix(".annotations.json")
        export_meta = self.controller.build_annotation_export_metadata(
            self.primary_image.id,
            export_format="bundle",
        )
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        img_name = pathlib.Path(str(getattr(source_image, "name", "image"))).stem
        core_tokens = (
            f"__ann__img={self._tokenize_filename_value(img_name)}"
            f"__ts={ts}{self._annotation_filename_context_tokens()}"
        )
        csv_path = csv_path.with_name(f"{csv_path.stem}{core_tokens}{csv_path.suffix}")
        json_path = json_path.with_name(f"{json_path.stem}{core_tokens}{json_path.suffix}")
        if self._settings.value("encodeAnnotationMetaFilename", False, type=bool):
            meta = self.controller.build_annotation_metadata(self.primary_image.id)
            tokens = format_tokens(meta)
            if tokens:
                csv_path = csv_path.with_name(f"{csv_path.stem}{tokens}{csv_path.suffix}")
                json_path = json_path.with_name(f"{json_path.stem}{tokens}{json_path.suffix}")
        return csv_path, json_path

    def _save_project(self) -> None:
        """Save a .phageproj plus per-image annotations."""
        if hasattr(self, "_sync_runbook_state_to_session"):
            self._sync_runbook_state_to_session()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save project",
            str(pathlib.Path.cwd() / "session.phageproj"),
            "Phage project (*.phageproj)",
        )
        if not path:
            return
        settings = {
            "last_fov_index": self.current_image_idx,
            "last_support_index": self.support_image_idx,
            "smlm_runs": list(self._smlm_run_history),
            "threshold_settings": dict(self._threshold_settings),
            "threshold_configs_by_image": dict(
                self.controller.session_state.threshold_configs_by_image
            ),
            "particles_configs_by_image": dict(
                self.controller.session_state.particles_configs_by_image
            ),
            "density_config": (
                self.controller.density_config.__dict__ if self.controller.density_config else {}
            ),
            "density_infer_options": (
                self.controller.density_infer_options.__dict__
                if self.controller.density_infer_options
                else {}
            ),
            "density_model_path": self.controller.density_model_path,
            "density_device": self.controller.density_device,
            "density_target_panel": self._density_last_panel,
            "auto_roi_shape": self.auto_roi_shape_combo.currentText()
            if getattr(self, "auto_roi_shape_combo", None) is not None
            else "box",
            "auto_roi_mode": self.auto_roi_mode_combo.currentText()
            if getattr(self, "auto_roi_mode_combo", None) is not None
            else "W/H",
            "auto_roi_w": int(self.auto_roi_w_spin.value())
            if getattr(self, "auto_roi_w_spin", None) is not None
            else 100,
            "auto_roi_h": int(self.auto_roi_h_spin.value())
            if getattr(self, "auto_roi_h_spin", None) is not None
            else 100,
            "auto_roi_area": int(self.auto_roi_area_spin.value())
            if getattr(self, "auto_roi_area_spin", None) is not None
            else 100 * 100,
            "current_user": self.controller.session_state.current_user,
            "audit_log": list(self.controller.session_state.audit_log),
            "feature_flags": dict(getattr(self.controller.session_state, "feature_flags", {}) or {}),
            "workflow_metrics": dict(getattr(self.controller.session_state, "workflow_metrics", {}) or {}),
            "suggestion_metrics": dict(self.controller.session_state.suggestion_metrics),
            "suggestions_by_image": {
                int(image_id): [self._serialize_suggestion(s) for s in items]
                for image_id, items in self.controller.session_state.suggestions.items()
            },
            "suggestion_history_by_image": {
                int(image_id): [self._serialize_suggestion(s) for s in items]
                for image_id, items in self.controller.session_state.suggestion_history.items()
            },
            "suggestion_strategy": str(getattr(self, "_suggestion_strategy", "current_view")),
            "suggestion_score_threshold": float(
                getattr(self, "_suggestion_score_threshold", 0.0)
            ),
            "suggestion_ranker_state": dict(self.controller.suggestion_ranker.to_dict())
            if hasattr(self.controller, "suggestion_ranker")
            else {},
            "suggestion_training_samples": list(
                getattr(self.controller.session_state, "suggestion_training_samples", [])
            ),
            "suggestion_training_pending": int(
                getattr(self.controller.session_state, "suggestion_training_pending", 0)
            ),
            "suggestion_context_stats": dict(
                getattr(self.controller.session_state, "suggestion_context_stats", {})
            ),
            "suggestion_auto_retrain_enabled": bool(
                getattr(self.controller.session_state, "suggestion_auto_retrain_enabled", True)
            ),
            "suggestion_auto_retrain_min_labels": int(
                getattr(self.controller.session_state, "suggestion_auto_retrain_min_labels", 25)
            ),
            "annotation_space": str(
                getattr(self.controller.session_state, "annotation_space", "stack")
            ),
            "generation_space": str(
                getattr(self.controller.session_state, "generation_space", "stack")
            ),
            "assist_min_total_labels": int(
                getattr(self.controller.session_state, "assist_min_total_labels", 30)
            ),
            "assist_min_positive_labels": int(
                getattr(self.controller.session_state, "assist_min_positive_labels", 15)
            ),
            "assist_min_negative_labels": int(
                getattr(self.controller.session_state, "assist_min_negative_labels", 15)
            ),
            "assist_min_labels_per_context": int(
                getattr(self.controller.session_state, "assist_min_labels_per_context", 10)
            ),
            "evidence_layer_config": dict(getattr(self, "_evidence_layer_config", {}) or {}),
            "evidence_layer_presets": dict(getattr(self, "_evidence_layer_presets", {}) or {}),
            "disable_bulk_accept_when_stale": bool(
                getattr(self, "_disable_bulk_accept_when_stale", True)
            ),
            "smlm_runbook_enabled": bool(
                getattr(self.controller.session_state, "smlm_runbook_enabled", False)
            ),
            "smlm_runbook_locked_profiles": dict(
                getattr(self.controller.session_state, "smlm_runbook_locked_profiles", {})
            ),
            "smlm_runbook_provenance": list(
                getattr(self.controller.session_state, "smlm_runbook_provenance", [])
            ),
        }
        settings["ui_workspace_state"] = self._capture_ui_workspace_state()
        settings["workspace_snapshot"] = build_workspace_snapshot(
            self.controller,
            settings,
            ui_workspace_state=settings.get("ui_workspace_state", {}),
        )
        settings["workspace_layer_registry"] = workspace_layer_registry()
        self.controller.save_project(
            self, pathlib.Path(path), settings, self.roi_manager.rois_by_image
        )
        self._status_success(f"Saved project to {path}", source="export.save_project")
        self._mark_dirty(False)

    def _load_project(self) -> None:
        """Load a .phageproj and restore image list, annotations, and settings."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load project", str(pathlib.Path.cwd()), "Phage project (*.phageproj)"
        )
        if not path:
            return
        self._last_loaded_project_path = pathlib.Path(path)
        self._load_project_path(self._last_loaded_project_path, relink_mode="ask")

    def _load_project_path(self, project_path: pathlib.Path, *, relink_mode: str = "ask") -> bool:
        """Load project from a concrete path and refresh UI state."""
        self._last_loaded_project_path = pathlib.Path(project_path)
        self._cancel_all_jobs()
        self._bump_job_generation()
        if not self.controller.load_project(
            self,
            pathlib.Path(project_path),
            read_metadata,
            relink_mode=relink_mode,
        ):
            return False
        self._apply_loaded_project_to_ui()
        self._show_project_relink_summary_panel(pathlib.Path(project_path))
        return True

    def _apply_loaded_project_to_ui(self) -> None:
        """Apply controller-loaded project state to UI widgets/docks."""
        self.stop_playback_t()
        self.current_image_idx = self.controller.session_state.active_primary_id
        self.support_image_idx = self.controller.session_state.active_support_id
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
        self.speed_slider.setValue(int(self.controller.session_state.fps))
        mapping = self.controller.display_mapping.mapping_for(self.primary_image.id, "frame")
        self.current_cmap_idx = mapping.lut
        if self.lut_combo is not None:
            idx = min(self.current_cmap_idx, self.lut_combo.count() - 1)
            self.lut_combo.setCurrentIndex(idx)
        if self.lut_invert_chk is not None:
            self.lut_invert_chk.setChecked(mapping.invert)
        if hasattr(self, "_sync_auto_roi_controls_from_settings"):
            self._sync_auto_roi_controls_from_settings()
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if self.controller.rois_by_image:
            self.roi_manager.rois_by_image = self.controller.rois_by_image
        self._smlm_run_history = list(self.controller.session_state.smlm_runs)
        self._last_smlm_run = self._smlm_run_history[-1] if self._smlm_run_history else None
        if self.smlm_panel is not None and self._last_smlm_run:
            backend = str(self._last_smlm_run.get("backend", "internal"))
            backend_cfg = dict(self._last_smlm_run.get("backend_config", {}) or {})
            thunder = self.smlm_panel.thunder
            idx = thunder.backend_combo.findText(backend)
            if idx >= 0:
                thunder.backend_combo.setCurrentIndex(idx)
            plugin_id = str(backend_cfg.get("plugin_id", ""))
            plugin_idx = thunder.plugin_combo.findData(plugin_id)
            if plugin_idx >= 0:
                thunder.plugin_combo.setCurrentIndex(plugin_idx)
            thunder.fiji_exec_edit.setText(str(backend_cfg.get("fiji_executable", "")))
            thunder.fiji_macro_edit.setText(str(backend_cfg.get("fiji_macro_path", "")))
            thunder.thunderstorm_jar_edit.setText(
                str(
                    backend_cfg.get(
                        "plugin_jar_path",
                        backend_cfg.get("thunderstorm_jar_path", ""),
                    )
                )
            )
            thunder.fiji_command_template_edit.setText(
                str(backend_cfg.get("fiji_command_template", ""))
            )
            thunder.pyimagej_app_edit.setText(str(backend_cfg.get("pyimagej_app_path", "")))
        self._threshold_settings = dict(self.controller.session_state.threshold_settings)
        if self.threshold_panel is not None and self._threshold_settings:
            self._apply_threshold_settings(self._threshold_settings)
        if self.controller.session_state.threshold_configs_by_image:
            image_id = self.primary_image.id
            cfg = self.controller.session_state.threshold_configs_by_image.get(image_id)
            if cfg:
                self._apply_threshold_settings(cfg)
        self._suggestion_strategy = str(
            getattr(self.controller.session_state, "suggestion_strategy", "current_view")
        )
        self._suggestion_score_threshold = float(
            getattr(self.controller.session_state, "suggestion_score_threshold", 0.0)
        )
        self._evidence_layer_config = dict(
            getattr(self.controller.session_state, "evidence_layer_config", {}) or {}
        )
        self._evidence_layer_presets = dict(
            getattr(self.controller.session_state, "evidence_layer_presets", {}) or {}
        )
        self._disable_bulk_accept_when_stale = bool(
            getattr(self.controller.session_state, "disable_bulk_accept_when_stale", True)
        )
        if getattr(self, "generation_space_combo", None) is not None:
            self.generation_space_combo.setCurrentText(
                str(getattr(self.controller.session_state, "generation_space", "stack"))
            )
        if getattr(self, "disable_bulk_accept_when_stale_chk", None) is not None:
            self.disable_bulk_accept_when_stale_chk.setChecked(
                bool(getattr(self.controller.session_state, "disable_bulk_accept_when_stale", True))
            )
        if getattr(self, "interactive_learning_experimental_chk", None) is not None:
            self.interactive_learning_experimental_chk.setChecked(
                bool(self.controller.feature_enabled("interactive_learning_experimental", False))
            )
        if getattr(self, "_smlm_runbook_state", None) is None:
            from phage_annotator.smlm.reproducibility import ReproducibilityRunbookState

            self._smlm_runbook_state = ReproducibilityRunbookState()
        self._smlm_runbook_state.enabled = bool(
            getattr(self.controller.session_state, "smlm_runbook_enabled", False)
        )
        self._smlm_runbook_state.locked_profiles = dict(
            getattr(self.controller.session_state, "smlm_runbook_locked_profiles", {}) or {}
        )
        self._smlm_runbook_state.provenance_events = list(
            getattr(self.controller.session_state, "smlm_runbook_provenance", []) or []
        )
        if getattr(self, "smlm_panel", None) is not None:
            self.smlm_panel.thunder.repro_mode_chk.blockSignals(True)
            self.smlm_panel.thunder.repro_mode_chk.setChecked(self._smlm_runbook_state.enabled)
            self.smlm_panel.thunder.repro_mode_chk.blockSignals(False)
        if hasattr(self, "annotation_space_combo"):
            self.annotation_space_combo.blockSignals(True)
            self.annotation_space_combo.setCurrentText(
                str(getattr(self.controller.session_state, "annotation_space", "stack"))
            )
            self.annotation_space_combo.blockSignals(False)
        if hasattr(self, "suggestion_auto_retrain_chk"):
            self.suggestion_auto_retrain_chk.blockSignals(True)
            self.suggestion_auto_retrain_chk.setChecked(
                bool(
                    getattr(
                        self.controller.session_state,
                        "suggestion_auto_retrain_enabled",
                        True,
                    )
                )
            )
            self.suggestion_auto_retrain_chk.blockSignals(False)
        if hasattr(self, "suggestion_min_labels_spin"):
            self.suggestion_min_labels_spin.blockSignals(True)
            self.suggestion_min_labels_spin.setValue(
                int(
                    getattr(
                        self.controller.session_state,
                        "suggestion_auto_retrain_min_labels",
                        25,
                    )
                )
            )
            self.suggestion_min_labels_spin.blockSignals(False)
        if hasattr(self, "assist_min_total_spin"):
            self.assist_min_total_spin.blockSignals(True)
            self.assist_min_positive_spin.blockSignals(True)
            self.assist_min_negative_spin.blockSignals(True)
            self.assist_min_context_spin.blockSignals(True)
            self.assist_min_total_spin.setValue(
                int(getattr(self.controller.session_state, "assist_min_total_labels", 30))
            )
            self.assist_min_positive_spin.setValue(
                int(getattr(self.controller.session_state, "assist_min_positive_labels", 15))
            )
            self.assist_min_negative_spin.setValue(
                int(getattr(self.controller.session_state, "assist_min_negative_labels", 15))
            )
            self.assist_min_context_spin.setValue(
                int(getattr(self.controller.session_state, "assist_min_labels_per_context", 10))
            )
            self.assist_min_total_spin.blockSignals(False)
            self.assist_min_positive_spin.blockSignals(False)
            self.assist_min_negative_spin.blockSignals(False)
            self.assist_min_context_spin.blockSignals(False)
        if hasattr(self, "_sync_channel_panel_for_active_image"):
            self._sync_channel_panel_for_active_image()
        if self.density_panel is not None:
            cfg = self.controller.density_config
            self.density_panel.normalize_combo.setCurrentText(cfg.normalize)
            self.density_panel.p_low_spin.setValue(cfg.p_low)
            self.density_panel.p_high_spin.setValue(cfg.p_high)
            self.density_panel.invert_chk.setChecked(cfg.invert)
            if self.controller.density_infer_options:
                opts = self.controller.density_infer_options
                self.density_panel.tile_spin.setValue(opts.tile_size)
                self.density_panel.overlap_spin.setValue(opts.overlap)
                self.density_panel.batch_spin.setValue(opts.batch_tiles)
                self.density_panel.roi_only_chk.setChecked(opts.use_roi_only)
            if self.controller.density_model_path:
                self.density_panel.model_path_edit.setText(self.controller.density_model_path)
            self.density_panel.device_combo.setCurrentText(self.controller.density_device)
            target = self.controller.density_target_panel
            if isinstance(target, str):
                self.density_panel.target_combo.setCurrentText(target.capitalize())
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        if hasattr(self, "_refresh_modality_layers_panel"):
            self._refresh_modality_layers_panel()
        workspace_snapshot = getattr(self.controller.session_state, "workspace_snapshot", {})
        if isinstance(workspace_snapshot, dict):
            self._restore_ui_workspace_state(extract_ui_workspace_state(workspace_snapshot))
        self._request_ui_refresh("export", metadata=True)
        self._mark_dirty(False)
        self._check_recovery()

    def _show_project_relink_summary_panel(self, project_path: pathlib.Path) -> None:
        """Update/open persistent Project Relink panel after load."""
        report = dict(getattr(self.controller.session_state, "project_relink_report", {}) or {})
        if not report:
            return
        relinked = list(report.get("relinked", []) or [])
        unresolved = list(report.get("unresolved", []) or [])
        if not relinked and not unresolved:
            return
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
        self.open_panel("advanced_settings", reason="project_relink:load")
        self._status_warning(
            f"Project relink summary: {len(relinked)} relinked, {len(unresolved)} unresolved.",
            timeout_ms=5000,
            source="export.project_relink_summary",
        )

    def _retry_project_relink(self, mode: str) -> None:
        """Retry project load with explicit relink mode."""
        path = getattr(self, "_last_loaded_project_path", None)
        if path is None:
            self._status_warning("No loaded project to relink.", source="export.retry_project_relink")
            return
        mode_value = str(mode or "ask").strip().lower()
        if mode_value not in {"ask", "auto", "manual"}:
            mode_value = "ask"
        ok = self._load_project_path(pathlib.Path(path), relink_mode=mode_value)
        if ok:
            self._status_success(
                "Project reloaded after "
                + ("manual relink." if mode_value == "manual" else "auto relink retry."),
                source="export.retry_project_relink",
            )

    def _export_view_dialog(self) -> None:
        if self.primary_image.array is None:
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Export View")
        dlg.setObjectName("export_dialog")
        layout = QtWidgets.QFormLayout(dlg)
        panel_combo = QtWidgets.QComboBox()
        panel_combo.setObjectName("export_dialog_combo_panel")
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        if not panel_map and hasattr(self, "_current_layout_spec"):
            try:
                self._current_layout_spec()
            except Exception:
                pass
            panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        panel_visibility = dict(getattr(self, "_panel_visibility", {}) or {})
        added = 0
        for key, modality in panel_map.items():
            if not str(key).startswith("modality_"):
                continue
            if not bool(panel_visibility.get(str(key), False)):
                continue
            label = str(getattr(modality, "display_name", key))
            panel_combo.addItem(label, str(key))
            added += 1
        if added <= 0:
            for key, modality in panel_map.items():
                if not str(key).startswith("modality_"):
                    continue
                label = str(getattr(modality, "display_name", key))
                panel_combo.addItem(label, str(key))
                added += 1
        if added <= 0:
            panel_combo.addItem("Modality 1", "modality_0")
        default_target = str(
            getattr(
                self,
                "annotate_target",
                self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0",
            )
        ).strip()
        idx = panel_combo.findData(default_target)
        if idx >= 0:
            panel_combo.setCurrentIndex(idx)
        scope_combo = QtWidgets.QComboBox()
        scope_combo.setObjectName("export_dialog_combo_scope")
        scope_combo.addItems(["Current slice", "T range", "All frames"])
        t_start = QtWidgets.QSpinBox()
        t_start.setObjectName("export_dialog_spinbox_t_start")
        t_end = QtWidgets.QSpinBox()
        t_end.setObjectName("export_dialog_spinbox_t_end")
        t_start.setRange(0, max(0, self.primary_image.array.shape[0] - 1))
        t_end.setRange(0, max(0, self.primary_image.array.shape[0] - 1))
        t_start.setValue(self.t_slider.value())
        t_end.setValue(self.t_slider.value())
        region_combo = QtWidgets.QComboBox()
        region_combo.setObjectName("export_dialog_combo_region")
        region_combo.addItems(["Full view", "Crop", "ROI bounds", "ROI mask-clipped"])
        roi_outline_chk = QtWidgets.QCheckBox("ROI outline")
        roi_outline_chk.setObjectName("export_dialog_checkbox_roi_outline")
        roi_outline_chk.setChecked(bool(self.roi_rect))
        roi_fill_chk = QtWidgets.QCheckBox("ROI fill")
        roi_fill_chk.setObjectName("export_dialog_checkbox_roi_fill")
        ann_chk = QtWidgets.QCheckBox("Annotation points")
        ann_chk.setObjectName("export_dialog_checkbox_annotations")
        ann_chk.setChecked(True)
        ann_label_chk = QtWidgets.QCheckBox("Annotation labels")
        ann_label_chk.setObjectName("export_dialog_checkbox_annotation_labels")
        particle_chk = QtWidgets.QCheckBox("Particle outlines")
        particle_chk.setObjectName("export_dialog_checkbox_particles")
        scalebar_chk = QtWidgets.QCheckBox("Scale bar")
        scalebar_chk.setObjectName("export_dialog_checkbox_scalebar")
        scalebar_chk.setChecked(self.scale_bar_enabled and self.scale_bar_include_in_export)
        overlay_text_chk = QtWidgets.QCheckBox("Overlay text")
        overlay_text_chk.setObjectName("export_dialog_checkbox_overlay_text")
        marker_spin = QtWidgets.QDoubleSpinBox()
        marker_spin.setObjectName("export_dialog_spinbox_marker_size")
        marker_spin.setRange(1.0, 200.0)
        marker_spin.setValue(float(self.marker_size))
        roi_lw_spin = QtWidgets.QDoubleSpinBox()
        roi_lw_spin.setObjectName("export_dialog_spinbox_roi_linewidth")
        roi_lw_spin.setRange(0.5, 6.0)
        roi_lw_spin.setValue(1.5)
        dpi_spin = QtWidgets.QSpinBox()
        dpi_spin.setObjectName("export_dialog_spinbox_dpi")
        dpi_spin.setRange(72, 600)
        dpi_spin.setValue(150)
        fmt_combo = QtWidgets.QComboBox()
        fmt_combo.setObjectName("export_dialog_combo_format")
        fmt_combo.addItems(["PNG", "TIFF"])
        overlay_only_chk = QtWidgets.QCheckBox("Overlay only (transparent)")
        overlay_only_chk.setObjectName("export_dialog_checkbox_overlay_only")
        transparent_chk = QtWidgets.QCheckBox("Transparent background")
        transparent_chk.setObjectName("export_dialog_checkbox_transparent")
        transparent_chk.setChecked(True)
        # P3.4: Export as separate layer files
        export_layers_chk = QtWidgets.QCheckBox("Export as separate layers")
        export_layers_chk.setObjectName("export_dialog_checkbox_layers")
        export_layers_chk.setToolTip("Generate separate PNG files for base image, annotations, ROI, particles, and scalebar with alpha channel")

        layout.addRow("Panel", panel_combo)
        layout.addRow("Scope", scope_combo)
        range_row = QtWidgets.QHBoxLayout()
        range_row.addWidget(QtWidgets.QLabel("Start"))
        range_row.addWidget(t_start)
        range_row.addWidget(QtWidgets.QLabel("End"))
        range_row.addWidget(t_end)
        layout.addRow("T range", range_row)
        layout.addRow("Region", region_combo)
        layout.addRow(roi_outline_chk)
        layout.addRow(roi_fill_chk)
        layout.addRow(ann_chk)
        layout.addRow(ann_label_chk)
        layout.addRow(particle_chk)
        layout.addRow(scalebar_chk)
        layout.addRow(overlay_text_chk)
        layout.addRow("Marker size", marker_spin)
        layout.addRow("ROI line width", roi_lw_spin)
        layout.addRow("DPI", dpi_spin)
        layout.addRow("Format", fmt_combo)
        layout.addRow(overlay_only_chk)
        layout.addRow(transparent_chk)
        layout.addRow(export_layers_chk)  # P3.4
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("export_dialog_buttonbox")
        layout.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        fmt = fmt_combo.currentText().lower()
        default_name = pathlib.Path(self.primary_image.path).with_suffix(f".export.{fmt}")
        panel_key = str(panel_combo.currentData() or panel_combo.currentText() or "").strip()
        opts = ExportOptions(
            panel=panel_key,
            region=region_combo.currentText().lower(),
            include_roi_outline=roi_outline_chk.isChecked(),
            include_roi_fill=roi_fill_chk.isChecked(),
            include_annotations=ann_chk.isChecked(),
            include_annotation_labels=ann_label_chk.isChecked(),
            include_particles=particle_chk.isChecked(),
            include_scalebar=scalebar_chk.isChecked(),
            include_overlay_text=overlay_text_chk.isChecked(),
            marker_size=float(marker_spin.value()),
            roi_line_width=float(roi_lw_spin.value()),
            dpi=int(dpi_spin.value()),
            fmt=fmt,
            overlay_only=overlay_only_chk.isChecked(),
            transparent_bg=transparent_chk.isChecked(),
            export_as_layers=export_layers_chk.isChecked(),  # P3.4
            roi_mask_clip=region_combo.currentText().lower() == "roi mask-clipped",
        )
        scope = scope_combo.currentText()
        t_values = self._export_t_values(scope, t_start.value(), t_end.value())

        # P1.5: Export guardrails and preflight validation
        # 1) ROI-based region requires a valid ROI
        if opts.region in ("roi bounds", "roi mask-clipped"):
            if self.roi_shape == "none" or self.roi_rect[2] <= 0 or self.roi_rect[3] <= 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Export blocked",
                    "ROI region requested but no valid ROI is set.",
                )
                return
        # 2) Overlay-only requires at least one overlay to be selected
        if opts.overlay_only:
            has_any_overlay = (
                opts.include_roi_outline
                or opts.include_roi_fill
                or opts.include_annotations
                or opts.include_annotation_labels
                or opts.include_particles
                or opts.include_scalebar
                or opts.include_overlay_text
            )
            if not has_any_overlay:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Export blocked",
                    "Overlay-only is selected but no overlays are enabled.",
                )
                return
        # 3) Ensure we actually have frames to export
        if not t_values:
            QtWidgets.QMessageBox.warning(
                self,
                "Export blocked",
                "No frames selected for export.",
            )
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export View", str(default_name))
        if not path:
            return
        self._export_view_job(pathlib.Path(path), t_values, opts)

    def _export_t_values(self, scope: str, t_start: int, t_end: int) -> list[int]:
        if scope == "Current slice":
            return [self.t_slider.value()]
        if scope == "All frames":
            return list(range(self.primary_image.array.shape[0]))
        if t_end < t_start:
            t_start, t_end = t_end, t_start
        return list(range(t_start, t_end + 1))

    def _export_view_job(
        self, base_path: pathlib.Path, t_values: list[int], opts: ExportOptions
    ) -> None:
        prim = self.primary_image
        if prim.array is None:
            return
        z_idx = self.z_slider.value()
        cal = self._get_calibration_state(prim.id)
        scalebar_spec = ScaleBarSpec(
            enabled=opts.include_scalebar,
            length_um=self.scale_bar_length_um,
            thickness_px=self.scale_bar_thickness_px,
            location=self.scale_bar_location,
            padding_px=self.scale_bar_padding_px,
            show_text=self.scale_bar_show_text,
            text_offset_px=self.scale_bar_text_offset_px,
            background_box=self.scale_bar_background_box,
        )
        crop_rect = (
            self.crop_rect if opts.region in ("crop", "roi bounds", "roi mask-clipped") else None
        )
        roi_rect = self.roi_rect if opts.region in ("roi bounds", "roi mask-clipped") else None
        roi_shape = self.roi_shape

        def _job(progress, cancel_token):
            total = len(t_values)
            for idx, t_idx in enumerate(t_values):
                if cancel_token.is_cancelled():
                    return None
                frame = self._export_panel_frame(t_idx, z_idx, opts.panel, crop_rect)
                if frame is None:
                    continue
                frame, offset = self._apply_roi_region(
                    frame, roi_rect, roi_shape, opts.region, crop_rect
                )
                annotations = self._export_annotations(t_idx, offset, opts)
                annotation_labels = self._export_annotation_labels(annotations, opts)
                annotation_points = [(x, y, color) for x, y, color, _ in annotations]
                roi_overlays = self._export_roi_overlays(offset, opts)
                particle_overlays = (
                    self._particles_overlays
                    if opts.include_particles and t_idx == self.t_slider.value()
                    else []
                )
                overlay_text = self._build_overlay_text() if opts.include_overlay_text else None
                panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
                modality = panel_map.get(str(opts.panel))
                mapping_image_id = int(getattr(modality, "image_id", prim.id))
                mapping = self._get_display_mapping(mapping_image_id, opts.panel, frame)
                norm = build_norm(mapping)
                cmap = cmap_for(mapping.lut, mapping.invert)
                
                # P4: Check for streaming chunk-based export
                if opts.export_as_chunked:
                    self._export_view_job_chunked(
                        frame, offset, t_idx, z_idx, cmap, norm,
                        annotation_points, annotation_labels, roi_overlays, particle_overlays,
                        overlay_text, scalebar_spec, cal.pixel_size_um_per_px, opts,
                        base_path, total, idx, progress, cancel_token
                    )
                else:
                    image = render_view_to_array(
                        frame,
                        cmap=cmap,
                        norm=norm,
                        overlays=[],
                        annotations=annotation_points,
                        annotation_labels=annotation_labels,
                        roi_overlays=roi_overlays,
                        particle_overlays=particle_overlays,
                        overlay_text=overlay_text,
                        scalebar_spec=scalebar_spec if opts.include_scalebar else None,
                        pixel_size_um=cal.pixel_size_um_per_px,
                        options=opts,
                    )
                    image = self._apply_roi_mask_clip(image, frame, roi_rect, roi_shape, opts, offset)
                    out_path = self._export_frame_path(
                        base_path, t_idx, opts, multiple=len(t_values) > 1
                    )
                    
                    # P3.4: Export as separate layers if requested
                    if opts.export_as_layers:
                        self._export_layers(
                            out_path,
                            frame,
                            cmap,
                            norm,
                            annotation_points,
                            annotation_labels,
                            roi_overlays,
                            particle_overlays,
                            overlay_text,
                            scalebar_spec,
                            cal.pixel_size_um_per_px,
                            opts,
                        )
                    else:
                        _save_image(out_path, image, opts)
                
                progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
            return True

        self.jobs.submit(
            _job,
            name="Export view",
            timeout_sec=600.0,
            priority="normal",
            replace_key="export-view",
        )
    
    def _export_view_job_chunked(
        self, frame, offset, t_idx, z_idx, cmap, norm,
        annotation_points, annotation_labels, roi_overlays, particle_overlays,
        overlay_text, scalebar_spec, pixel_size_um, opts,
        base_path, total, idx, progress, cancel_token
    ) -> None:
        """Export frame using streaming chunk-based approach (P4a).
        
        Parameters
        ----------
        frame : ndarray
            Frame data
        offset : tuple
            ROI offset
        t_idx : int
            Time index
        z_idx : int
            Z index
        cmap : matplotlib colormap
            Color map
        norm : matplotlib norm
            Normalization
        annotation_points : list
            Point annotations
        annotation_labels : list
            Annotation labels
        roi_overlays : list
            ROI overlay items
        particle_overlays : list
            Particle overlay items
        overlay_text : str
            Overlay text
        scalebar_spec : ScaleBarSpec
            Scalebar specification
        pixel_size_um : float
            Pixel size in micrometers
        opts : ExportOptions
            Export options
        base_path : pathlib.Path
            Base export path
        total : int
            Total frames
        idx : int
            Current frame index
        progress : callable
            Progress callback
        cancel_token : CancelToken
            Cancellation token
        """
        out_path = self._export_frame_path(
            base_path, t_idx, opts, multiple=total > 1
        )
        
        # Create streaming writer
        image_shape = frame.shape
        writer = create_streaming_writer(opts.fmt, out_path, image_shape)
        
        # Calculate chunks
        chunks = calculate_export_chunks(image_shape, chunk_size=256)
        num_chunks = len(chunks)
        
        # Render and write each chunk
        for chunk_idx, (x0, y0, x1, y1) in enumerate(chunks):
            if cancel_token.is_cancelled():
                return None
            
            # Render chunk with filtered overlays
            chunk = render_chunk_to_array(
                frame,
                crop_box=(x0, y0, x1, y1),
                cmap=cmap,
                norm=norm,
                overlays=[],
                annotations=annotation_points,
                annotation_labels=annotation_labels,
                roi_overlays=roi_overlays,
                particle_overlays=particle_overlays,
                overlay_text=overlay_text,
                scalebar_spec=scalebar_spec,
                pixel_size_um=pixel_size_um,
                options=opts,
            )
            
            # Write chunk
            writer.write_chunk(chunk, (y0, x0))
            
            # Update progress with chunk progress
            chunk_progress = int((chunk_idx + 1) / num_chunks * 100)
            frame_progress = int((idx + chunk_progress / 100) / total * 100)
            progress(frame_progress, f"{idx + 1}/{total} (chunk {chunk_idx + 1}/{num_chunks})")
        
        # Finalize writer
        writer.finalize()


    def _export_panel_frame(self, t_idx: int, z_idx: int, panel: str, crop_rect):
        panel_key = str(panel or "").strip()
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(panel_key)
        if modality is None:
            return None
        img = self._image_obj_from_id(int(getattr(modality, "image_id", -1)))
        if img is None:
            return None
        if img.array is None:
            self._ensure_loaded(img.id)
            if img.array is None:
                return None
        projection = str(getattr(getattr(modality, "projection_type", None), "value", "raw")).strip().lower()
        axis = str(
            getattr(getattr(modality, "display_settings", None), "projection_axis", "t")
        ).strip().lower()
        if projection == "raw":
            data = self._build_multichannel_frame(img, t_idx, z_idx)
            if data is None:
                t_safe = max(0, min(int(t_idx), int(img.array.shape[0]) - 1))
                z_safe = max(0, min(int(z_idx), int(img.array.shape[1]) - 1))
                data = img.array[t_safe, z_safe, :, :]
        else:
            data = compute_projection(np.asarray(img.array), projection, axis=axis)
        return self._apply_crop_rect(data, crop_rect, data.shape)

    def _apply_roi_region(
        self, frame: np.ndarray, roi_rect, roi_shape: str, region: str, crop_rect
    ):
        offset = (crop_rect[0], crop_rect[1]) if crop_rect else (0.0, 0.0)
        if roi_rect is None:
            return frame, offset
        if region not in ("roi bounds", "roi mask-clipped"):
            return frame, offset
        x, y, w, h = roi_rect
        x0 = int(max(0, x - offset[0]))
        y0 = int(max(0, y - offset[1]))
        x1 = int(min(frame.shape[1], x0 + w))
        y1 = int(min(frame.shape[0], y0 + h))
        return frame[y0:y1, x0:x1], (offset[0] + x0, offset[1] + y0)

    def _export_annotations(self, t_idx: int, offset, opts: ExportOptions):
        if not opts.include_annotations:
            return []
        points = []
        for kp in self._current_keypoints():
            if kp.t not in (-1, t_idx) or kp.z not in (-1, self.z_slider.value()):
                continue
            x = kp.x - offset[0]
            y = kp.y - offset[1]
            points.append((x, y, self._label_color(kp.label, faded=False), kp.label))
        return points

    def _export_annotation_labels(self, annotations, opts: ExportOptions):
        if not opts.include_annotation_labels:
            return []
        return [(x, y, label) for x, y, _, label in annotations]

    def _export_roi_overlays(self, offset, opts: ExportOptions):
        overlays = []
        roi_active = self.roi_shape != "none" and self.roi_rect[2] > 0 and self.roi_rect[3] > 0
        if roi_active and (opts.include_roi_outline or opts.include_roi_fill):
            x, y, w, h = self.roi_rect
            rect = (x - offset[0], y - offset[1], w, h)
            if self.roi_shape == "circle":
                overlays.append(("circle", rect, "#00c0ff"))
            else:
                overlays.append(("box", rect, "#00c0ff"))
        return overlays

    def _apply_roi_mask_clip(
        self,
        image: np.ndarray,
        frame: np.ndarray,
        roi_rect,
        roi_shape: str,
        opts: ExportOptions,
        offset,
    ):
        if not opts.roi_mask_clip or roi_rect is None:
            return image
        mask = np.ones(frame.shape, dtype=bool)
        rx, ry, rw, rh = roi_rect
        rx -= offset[0]
        ry -= offset[1]
        rx = max(0, rx)
        ry = max(0, ry)
        if roi_shape == "circle":
            cx, cy = rx + rw / 2, ry + rh / 2
            r = min(rw, rh) / 2
            yy, xx = np.ogrid[: frame.shape[0], : frame.shape[1]]
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
        else:
            x0 = int(max(0, rx))
            y0 = int(max(0, ry))
            x1 = int(min(frame.shape[1], rx + rw))
            y1 = int(min(frame.shape[0], ry + rh))
            mask = np.zeros(frame.shape, dtype=bool)
            mask[y0:y1, x0:x1] = True
        if image.shape[-1] == 4:
            if opts.transparent_bg:
                image[..., 3] = np.where(mask, image[..., 3], 0)
            else:
                image[~mask] = 0
        return image

    def _export_layers(
        self,
        base_path: pathlib.Path,
        frame: np.ndarray,
        cmap,
        norm,
        annotation_points,
        annotation_labels,
        roi_overlays,
        particle_overlays,
        overlay_text,
        scalebar_spec,
        pixel_size_um,
        opts: ExportOptions,
    ) -> None:
        """Export each overlay as a separate PNG file with alpha channel (P3.4).
        
        Creates files like:
        - base_t0000_base.png (base image)
        - base_t0000_annotations.png (annotations with alpha)
        - base_t0000_roi.png (ROI with alpha)
        - base_t0000_particles.png (particles with alpha)
        - base_t0000_scalebar.png (scalebar with alpha)
        """
        stem = base_path.stem
        parent = base_path.parent
        image_shape = frame.shape[:2]
        
        # Always export base layer
        if not opts.overlay_only:
            base_layer = render_layer_to_array(
                image_shape,
                layer_type="base",
                cmap=cmap,
                norm=norm,
                image=frame,
                options=opts,
            )
            base_file = parent / f"{stem}_base.png"
            _save_image(base_file, base_layer, opts)
        
        # Export annotations layer
        if opts.include_annotations and annotation_points:
            ann_layer = render_layer_to_array(
                image_shape,
                layer_type="annotations",
                annotations=annotation_points,
                annotation_labels=annotation_labels if opts.include_annotation_labels else [],
                options=opts,
            )
            ann_file = parent / f"{stem}_annotations.png"
            _save_image(ann_file, ann_layer, opts)
        
        # Export ROI layer
        if (opts.include_roi_outline or opts.include_roi_fill) and roi_overlays:
            roi_layer = render_layer_to_array(
                image_shape,
                layer_type="roi",
                roi_overlays=roi_overlays,
                options=opts,
            )
            roi_file = parent / f"{stem}_roi.png"
            _save_image(roi_file, roi_layer, opts)
        
        # Export particles layer
        if opts.include_particles and particle_overlays:
            particles_layer = render_layer_to_array(
                image_shape,
                layer_type="particles",
                particle_overlays=particle_overlays,
                options=opts,
            )
            particles_file = parent / f"{stem}_particles.png"
            _save_image(particles_file, particles_layer, opts)
        
        # Export scalebar layer
        if opts.include_scalebar and scalebar_spec:
            scalebar_layer = render_layer_to_array(
                image_shape,
                layer_type="scalebar",
                scalebar_spec=scalebar_spec,
                pixel_size_um=pixel_size_um,
                options=opts,
            )
            scalebar_file = parent / f"{stem}_scalebar.png"
            _save_image(scalebar_file, scalebar_layer, opts)
        
        # Export text overlay layer
        if opts.include_overlay_text and overlay_text:
            text_layer = render_layer_to_array(
                image_shape,
                layer_type="text",
                overlay_text=overlay_text,
                options=opts,
            )
            text_file = parent / f"{stem}_text.png"
            _save_image(text_file, text_layer, opts)

    def _export_frame_path(
        self, base: pathlib.Path, t_idx: int, opts: ExportOptions, *, multiple: bool
    ) -> pathlib.Path:
        if not multiple:
            return base
        stem = base.stem
        return base.with_name(f"{stem}_t{t_idx:04d}{base.suffix}")


def _save_image(path: pathlib.Path, image: np.ndarray, opts: ExportOptions) -> None:
    if opts.fmt == "tiff":
        import tifffile as tif

        tif.imwrite(str(path), image)
        return
    import matplotlib.pyplot as plt

    plt.imsave(str(path), image)
