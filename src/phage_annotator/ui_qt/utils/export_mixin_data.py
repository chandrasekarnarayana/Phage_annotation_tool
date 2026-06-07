"""Extracted method group 4 for ExportMixin."""

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




class ExportMixinDataMixin:
    """Method group 4 extracted from ExportMixin."""

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
