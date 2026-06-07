"""Extracted method group 3 for ExportMixin."""

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




class ExportMixinImagesMixin:
    """Method group 3 extracted from ExportMixin."""

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
