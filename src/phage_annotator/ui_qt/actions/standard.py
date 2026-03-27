"""Menu and dialog actions for the GUI."""

from __future__ import annotations

import gc
import json
import logging
import os
import pathlib
import time
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.assist_context import AssistContextMixin
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.actions.assist_strategy import AssistStrategyMixin
from phage_annotator.ui_qt.actions.standard_workspace import WorkspaceActionsMixin
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.actions.dock_actions import DockActionsMixin
from phage_annotator.ui_qt.actions.export_actions import ExportActionsMixin
from phage_annotator.ui_qt.actions.navigation_actions import NavigationActionsMixin
from phage_annotator.ui_qt.actions.qc_actions import QCActionsMixin
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.io.metadata.reader import MetadataBundle


logger = logging.getLogger(__name__)


class ActionsMixin(
    AssistContextMixin,
    AssistStrategyMixin,
    WorkspaceActionsMixin,
    NavigationActionsMixin,
    ExportActionsMixin,
    DockActionsMixin,
    QCActionsMixin,
):
    """Mixin for File/View/Analyze actions and dialogs."""

    def _current_annotation_write_context(self) -> tuple[str, str]:
        """Return the current write context as (context_key, panel_key)."""
        context = (
            dict(self.controller.current_annotation_context() or {})
            if hasattr(self.controller, "current_annotation_context")
            else {}
        )
        return (
            str(context.get("context_key", "img:0|panel:frame|space:stack")),
            str(context.get("panel_key", getattr(self, "annotate_target", "frame"))),
        )

    def _mark_annotation_context_changed(self, reason: str) -> None:
        """Mark write context as changed and requiring explicit confirmation."""
        self._annotation_write_context_pending = True
        self._annotation_context_change_reason = str(reason or "context changed")
        self._annotation_write_context_pending_value = self._current_annotation_write_context()
        self._update_status()

    def _is_annotation_context_guard_pending(self) -> bool:
        """True when write actions should request confirmation before commit."""
        pending = bool(getattr(self, "_annotation_write_context_pending", False))
        confirmed = getattr(self, "_annotation_write_context_confirmed", None)
        current = self._current_annotation_write_context()
        if pending and isinstance(confirmed, tuple) and tuple(confirmed) == current:
            self._annotation_write_context_pending = False
            self._annotation_context_change_reason = ""
            self._annotation_write_context_pending_value = None
            pending = False
        if pending:
            return True
        return confirmed is not None and tuple(confirmed) != current

    def _ensure_annotation_write_context_confirmed(self, action_label: str) -> bool:
        """Prompt before write if annotation context changed since last confirmation."""
        current = self._current_annotation_write_context()
        confirmed = getattr(self, "_annotation_write_context_confirmed", None)
        needs_confirm = self._is_annotation_context_guard_pending()
        if not needs_confirm:
            self._annotation_write_context_confirmed = current
            return True

        reason = str(
            getattr(self, "_annotation_context_change_reason", "")
            or "annotation context changed"
        )
        prev_txt = (
            f"{confirmed[0]} / {confirmed[1]}"
            if isinstance(confirmed, tuple) and len(confirmed) == 2
            else "unknown"
        )
        cur_txt = f"{current[0]} / {current[1]}"
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Confirm Annotation Write Context")
        msg.setText(f"{action_label} will write annotations in a new context.")
        msg.setInformativeText(
            f"Previous confirmed context: {prev_txt}\n"
            f"Current context: {cur_txt}\n"
            f"Reason: {reason}\n\n"
            "Proceed with this write?"
        )
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel
        )
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        if msg.exec() != QtWidgets.QMessageBox.Yes:
            self._status_warning(
                "Write cancelled: context confirmation required.",
                timeout_ms=3000,
                source="standard.write_context",
            )
            return False
        self._annotation_write_context_confirmed = current
        self._annotation_write_context_pending = False
        self._annotation_context_change_reason = ""
        self._annotation_write_context_pending_value = None
        self._update_status()
        return True

    def _open_files(self) -> None:
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_files(self)
        if paths:
            self.recorder.record("open_files", {"count": len(paths)})
            self._open_files_from_paths(paths)

    def _open_folder(self) -> None:
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        paths = self.controller.open_folder(self)
        if paths:
            self.recorder.record("open_folder", {"count": len(paths)})
            # Load metadata for all files in the background with progress + cancel (P1.3)
            files = list(paths)

            def _worker(progress, cancel):
                from phage_annotator.ui_qt.utils.image_io import read_metadata

                metas = []
                total = len(files)
                for idx, p in enumerate(files):
                    if cancel.is_cancelled():
                        return None
                    meta = read_metadata(p)
                    metas.append(meta)
                    progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
                return metas

            def _on_result(result):
                if not result:
                    return
                new_images = result
                # Add images and update UI on GUI thread
                self.controller.add_images(new_images)
                for meta in new_images:
                    self.roi_manager.rois_by_image[meta.id] = []
                # Build annotation index (lightweight) and update availability
                try:
                    self.controller.build_annotation_index(files[0].parent)
                except Exception:
                    logger.warning("Failed to build annotation index after opening folder", exc_info=True)
                self._refresh_annotation_availability()
                self._refresh_roi_manager()
                self._refresh_metadata_dock(self.primary_image.id)
                self._request_ui_refresh("standard-actions")
                self._maybe_autoload_annotations(self.primary_image.id)

            self.jobs.submit(
                _worker,
                name="Open folder",
                on_result=_on_result,
                timeout_sec=300.0,
                retries=2,
                retry_delay_sec=1.0,
                priority="interactive",
                replace_key="open-folder",
            )

    def _reset_confirmations(self) -> None:
        """Re-enable all confirmation dialogs."""
        self._settings.setValue("confirmApplyDisplayMapping", True)
        self._settings.setValue("confirmApplyThreshold", True)
        self._settings.setValue("confirmClearROI", True)
        self._settings.setValue("confirmDeleteAnnotations", True)
        self._settings.setValue("confirmOverwriteFile", True)
        QtWidgets.QMessageBox.information(
            self,
            "Confirmations Reset",
            "All confirmation prompts have been re-enabled.\n\nYou will now be asked before:\n• Applying display settings\n• Applying threshold\n• Clearing ROI\n• Deleting annotations\n• Overwriting files"
        )

    def _load_annotations_current(self) -> None:
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            force_image_id=self.primary_image.id,
            context_panel_key=str(getattr(self, "annotate_target", "frame")),
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._request_ui_refresh("standard-actions", table=True)
        self._refresh_table()

    def _load_annotations_multi(self) -> None:
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(
            self,
            self.primary_image.id,
            pixel_size_nm=pixel_size_nm,
            context_panel_key=str(getattr(self, "annotate_target", "frame")),
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._request_ui_refresh("standard-actions", table=True)
        self._refresh_table()

    def _load_annotations_all(self) -> None:
        targets = []
        for img in self.images:
            if self.controller.annotation_entries_for_image(img.id):
                targets.append(img.id)
        if not targets:
            QtWidgets.QMessageBox.information(
                self, "No annotations", "No indexed annotations were found."
            )
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None

        def _worker(progress, cancel):
            results = {}
            imports = []
            total = len(targets)
            for idx, image_id in enumerate(targets):
                if cancel.is_cancelled():
                    return None
                paths = [
                    entry.path for entry in self.controller.annotation_entries_for_image(image_id)
                ]
                points, import_entries = self.controller._parse_annotations_from_paths(
                    paths,
                    image_id=image_id,
                    pixel_size_nm=pixel_size_nm,
                    force_image_id=image_id,
                )
                results[image_id] = points
                imports.extend(import_entries)
                progress(int((idx + 1) / max(1, total) * 100), f"{idx + 1}/{total}")
            return (results, imports)

        def _on_result(result):
            if not result:
                return
            results, imports = result
            self.controller._record_annotation_imports(imports)
            for image_id, points in results.items():
                if self.controller.annotations_are_loaded(image_id):
                    self.controller.merge_annotations(image_id, points)
                else:
                    self.controller.replace_annotations(image_id, points)
            meta = None
            for target_id, entry in imports:
                if target_id == self.primary_image.id:
                    meta = entry.get("meta")
                    if isinstance(meta, dict) and meta:
                        break
            if meta:
                self._handle_annotation_metadata(self.primary_image.id, meta)
            self._mark_dirty()
            emit_annotations_changed(self.controller, image_id=self.primary_image.id)
            self._request_ui_refresh("standard-actions", table=True)
            self._refresh_table()

        self.jobs.submit(
            _worker,
            name="Load all annotations",
            on_result=_on_result,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
            priority="interactive",
            replace_key="load-all-annotations",
        )

    def _reload_annotations_current(self) -> None:
        image_id = self.primary_image.id
        if not self.controller.annotation_entries_for_image(image_id):
            self._load_annotations_current()
            return
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=True, pixel_size_nm=pixel_size_nm)

    def _toggle_left_pane(self) -> None:
        if self.dock_sidebar is None:
            return
        self._set_panel_visibility("sidebar")

    def _toggle_settings_pane(self) -> None:
        dock = getattr(self, "dock_advanced_settings", None)
        if dock is None:
            return
        visible = bool(dock.isVisible())
        if hasattr(self, "_toggle_right_sidebar_panel"):
            if visible:
                self._toggle_right_sidebar_panel("advanced_settings")
            else:
                self.open_panel("advanced_settings", reason="menu:advanced_settings")
                try:
                    dock.raise_()
                except Exception:
                    pass
        else:
            dock.setVisible(not visible)

    def _on_link_zoom_menu(self) -> None:
        self.link_zoom = self.link_zoom_act.isChecked()
        if not self.link_zoom:
            # reset last linked to avoid forcing 0-1 ranges
            self._last_zoom_linked = None
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
        if getattr(self, "view_sync", None) is not None:
            self._apply_view_sync_selection()
        self._request_ui_refresh("standard-actions")

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "About Phage Annotator",
            "Phage Annotator\nMatplotlib + Qt GUI for microscopy keypoint annotation.\nFive synchronized panels, ROI, autoplay, lazy loading.",
        )

    def _show_keyboard_shortcuts(self) -> None:
        """Show keyboard shortcuts reference dialog."""
        from phage_annotator.ui_qt.widgets.keyboard_shortcuts_dialog import (
            KeyboardShortcutsDialog,
        )
        dialog = KeyboardShortcutsDialog(self)
        dialog.exec()

    def _show_contextual_help(self) -> None:
        """Show concise context-aware help for faster discovery."""
        queue_count = 0
        if hasattr(self, "_visible_suggestions_uncertain_first"):
            try:
                queue_count = len(self._visible_suggestions_uncertain_first())
            except Exception:
                queue_count = 0
        mode = "Review" if getattr(self, "dock_review_queue", None) is not None and self.dock_review_queue.isVisible() else "Annotate"
        current_panel = "Unknown"
        for act in getattr(self, "sidebar_actions", []) or []:
            if act.isChecked():
                current_panel = str(act.text())
                break
        assist_state = assist_state_label(self._canonical_assist_state())
        QtWidgets.QMessageBox.information(
            self,
            "Contextual Help",
            (
                f"Mode: {mode} | Sidebar panel: {current_panel} | Assist: {assist_state}\n"
                "Quick actions:\n"
                f"- Review queue visible suggestions: {queue_count}\n"
                "- A/R: accept/reject current suggestion (when suggestions are visible)\n"
                "- N/P: next/previous uncertain suggestion\n"
                "- Use right-dock panels: Annotation Table, Review Queue, Suggestion Rationale.\n"
                "- Use Layouts button near playback for quick presets."
            ),
        )

    def _visible_suggestions(self) -> list[PointSuggestion]:
        """Return suggestions visible on active image and T/Z slice."""
        return self.controller.get_visible_suggestions(
            self.primary_image.id,
            t_index=int(self.t_slider.value()),
            z_index=int(self.z_slider.value()),
            min_score=float(getattr(self, "_suggestion_score_threshold", 0.0)),
        )

    def _suggestions_for_current_tz(self) -> list[PointSuggestion]:
        """Return all suggestions for active image and current T/Z, including decided history rows."""
        return self.controller.get_slice_suggestions(
            int(self.primary_image.id),
            t_index=int(self.t_slider.value()),
            z_index=int(self.z_slider.value()),
        )

    def _candidate_suggestion_strategies(self) -> list[str]:
        """Return available suggestion strategies for the current context."""
        options = [
            "current_view",
            "raw",
            "corrected",
            "mean_projection",
            "max_projection",
            "evidence_consensus",
            "evidence_contradiction",
        ]
        image = getattr(self, "primary_image", None)
        if image is not None and int(getattr(image, "channel_count", 1)) >= 2:
            options.extend(
                [
                    "channel_a_only",
                    "channel_b_only",
                    "channel_a_peak_b_low",
                    "channel_b_peak_a_low",
                ]
            )
        return options

    def _available_modality_frames(self, image, t_idx: int, z_idx: int) -> dict[str, np.ndarray]:
        """Build a modality/evidence frame map for suggestion generation."""
        out: dict[str, np.ndarray] = {}
        raw = self._slice_data(image, t_override=t_idx, z_override=z_idx)
        if raw is None:
            return out
        out["current_view"] = np.asarray(raw)
        out["raw"] = np.asarray(raw)
        model = getattr(self, "_suggestion_model", None)
        if model is not None and hasattr(model, "_corrected_image"):
            try:
                out["corrected"] = np.asarray(model._corrected_image(np.asarray(raw)))
            except Exception:
                pass
        if image.array is not None and image.array.ndim >= 4:
            stack_t = np.asarray(image.array[t_idx, :, :, :], dtype=np.float32)
            out["mean_projection"] = np.nanmean(stack_t, axis=0)
            out["max_projection"] = np.nanmax(stack_t, axis=0)
            # Store full stack for stack-aware suggestion methods
            out["_full_stack_t"] = stack_t
        config = dict(getattr(self, "_evidence_layer_config", {}) or {})
        filtered: dict[str, np.ndarray] = {}
        for modality_id, frame in out.items():
            entry = dict(config.get(modality_id, {}) or {})
            visible = bool(entry.get("visible", True))
            role = str(entry.get("role", "proposal evidence"))
            if not visible:
                continue
            if role.strip().lower() == "view only":
                continue
            filtered[modality_id] = frame
        return filtered or out

    def _default_evidence_layer_config(self) -> dict[str, dict]:
        """Return default layer config for modality/evidence controls."""
        default_lut = lut_names()[0] if lut_names() else "gray"
        return {
            "current_view": {"visible": True, "opacity": 1.0, "lut": default_lut, "role": "proposal evidence"},
            "raw": {"visible": True, "opacity": 1.0, "lut": default_lut, "role": "proposal evidence"},
            "corrected": {"visible": True, "opacity": 1.0, "lut": default_lut, "role": "proposal evidence"},
            "mean_projection": {"visible": True, "opacity": 1.0, "lut": default_lut, "role": "proposal evidence"},
            "max_projection": {"visible": True, "opacity": 1.0, "lut": default_lut, "role": "proposal evidence"},
        }

    def _refresh_modality_layers_panel(self) -> None:
        """Normalize evidence-layer config with defaults.

        The Modality Layers panel has been removed from the UI, but evidence
        layer settings still exist in session state for suggestion generation.
        """
        base = self._default_evidence_layer_config()
        current = dict(getattr(self, "_evidence_layer_config", {}) or {})
        for key, value in current.items():
            base[str(key)] = {
                "visible": bool(dict(value).get("visible", True)),
                "opacity": float(dict(value).get("opacity", 1.0)),
                "lut": str(dict(value).get("lut", base.get(str(key), {}).get("lut", "gray"))),
                "role": str(dict(value).get("role", "proposal evidence")),
            }
        self._evidence_layer_config = base

    def _on_modality_layer_changed(
        self,
        modality_id: str,
        visible: bool,
        opacity: float,
        lut: str,
        role: str,
    ) -> None:
        """Persist one layer-row update and refresh dependent views."""
        config = dict(getattr(self, "_evidence_layer_config", {}) or {})
        config[str(modality_id)] = {
            "visible": bool(visible),
            "opacity": float(max(0.0, min(1.0, opacity))),
            "lut": str(lut),
            "role": str(role),
        }
        self._evidence_layer_config = config
        self._active_evidence_preset_name = "custom"
        self.controller.set_evidence_layer_config(dict(config))
        self._status_info(
            f"Layer updated: {modality_id} ({role}, visible={visible}).",
            timeout_ms=2500,
            source="standard.modality_layer",
        )
        self._request_ui_refresh("standard-actions")
        self._append_assist_change_log(
            "modality_layer_changed",
            modality_id=str(modality_id),
            visible=bool(visible),
            opacity=float(opacity),
            lut=str(lut),
            role=str(role),
        )
        self._maybe_emit_assist_context_delta("modality_layer")

    def _save_modality_layer_preset(self, name: str) -> None:
        """Save current layer config as a named preset."""
        preset_name = str(name or "default").strip() or "default"
        presets = dict(getattr(self, "_evidence_layer_presets", {}) or {})
        presets[preset_name] = dict(getattr(self, "_evidence_layer_config", {}) or {})
        self._evidence_layer_presets = presets
        self._active_evidence_preset_name = preset_name
        self.controller.set_evidence_layer_presets(dict(presets))
        if getattr(self, "_settings", None) is not None:
            self._settings.setValue("evidenceLayerPresets", json.dumps(presets))
        self._status_success(
            f"Saved modality/evidence preset: {preset_name}.",
            timeout_ms=3000,
            source="standard.modality_preset",
        )
        self._append_assist_change_log("modality_preset_saved", preset=preset_name)
        self._maybe_emit_assist_context_delta("preset_save")

    def _load_modality_layer_preset(self, name: str) -> None:
        """Load a named layer preset if present."""
        preset_name = str(name or "default").strip() or "default"
        presets = dict(getattr(self, "_evidence_layer_presets", {}) or {})
        if not presets and getattr(self, "_settings", None) is not None:
            raw = self._settings.value("evidenceLayerPresets", "", type=str)
            if raw:
                try:
                    presets = dict(json.loads(raw))
                except Exception:
                    presets = {}
                self._evidence_layer_presets = presets
        preset = dict(presets.get(preset_name, {}) or {})
        if not preset:
            self._status_warning(
                f"No modality/evidence preset named '{preset_name}'.",
                timeout_ms=3000,
                source="standard.modality_preset",
            )
            return
        self._evidence_layer_config = preset
        self._active_evidence_preset_name = preset_name
        self.controller.set_evidence_layer_config(dict(preset))
        self._refresh_modality_layers_panel()
        self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Loaded modality/evidence preset: {preset_name}.",
            timeout_ms=3000,
            source="standard.modality_preset",
        )
        self._append_assist_change_log("modality_preset_loaded", preset=preset_name)
        self._maybe_emit_assist_context_delta("preset_load")

    def _compare_modality_layer_presets(self, preset_a: str, preset_b: str) -> None:
        """One-click A/B compare mode for modality-layer presets with preserved camera."""
        a_name = str(preset_a or "default").strip() or "default"
        b_name = str(preset_b or "default").strip() or "default"
        toggle = int(getattr(self, "_modality_compare_toggle_state", 0))
        target = a_name if toggle % 2 == 0 else b_name
        xlim = None
        ylim = None
        frame_ax = None
        if getattr(self, "renderer", None) is not None:
            frame_ax = self.renderer.get_axis("frame")
        if frame_ax is not None:
            try:
                xlim = tuple(frame_ax.get_xlim())
                ylim = tuple(frame_ax.get_ylim())
            except Exception:
                xlim = None
                ylim = None
        self._modality_compare_toggle_state = toggle + 1
        self._load_modality_layer_preset(target)
        if frame_ax is not None and xlim is not None and ylim is not None:
            try:
                frame_ax.set_xlim(xlim)
                frame_ax.set_ylim(ylim)
                if getattr(self, "canvas", None) is not None:
                    self.canvas.draw_idle()
            except Exception:
                pass
        self._status_info(
            f"A/B compare: loaded {target}.",
            timeout_ms=2500,
            source="standard.modality_compare",
        )
        self._append_assist_change_log("modality_preset_compare", preset=target, a=a_name, b=b_name)

    def _merge_modal_consensus(
        self,
        modality_candidates: dict[str, list[PointSuggestion]],
        *,
        k_required: int = 2,
    ) -> list[PointSuggestion]:
        """Merge per-modality candidates and require evidence in >= K modalities."""
        if not modality_candidates:
            return []
        modality_ids = list(modality_candidates.keys())
        seed_modality = "current_view" if "current_view" in modality_ids else modality_ids[0]
        seeds = list(modality_candidates.get(seed_modality, []))
        radius = float(getattr(self._suggestion_model, "min_distance_px", 6))
        r2 = radius * radius
        merged: list[PointSuggestion] = []
        for seed in seeds:
            bundle = {seed_modality: dict(seed.score_components)}
            votes = 1
            score_sum = float(seed.score)
            for modality_id, rows in modality_candidates.items():
                if modality_id == seed_modality:
                    continue
                hit = None
                for row in rows:
                    dx = float(row.x) - float(seed.x)
                    dy = float(row.y) - float(seed.y)
                    if dx * dx + dy * dy <= r2:
                        hit = row
                        break
                if hit is not None:
                    votes += 1
                    score_sum += float(hit.score)
                    bundle[modality_id] = dict(hit.score_components)
            if votes < int(max(1, k_required)):
                continue
            combined = PointSuggestion(
                image_id=seed.image_id,
                image_name=seed.image_name,
                t=seed.t,
                z=seed.z,
                y=seed.y,
                x=seed.x,
                score=float(score_sum / votes),
                label=seed.label,
                suggestion_id=seed.suggestion_id,
                source_model=seed.source_model,
                source_modality="consensus",
                supporting_modalities=sorted(bundle.keys()),
                cross_modality_consistency_score=float(votes / max(1, len(modality_candidates))),
                control_contradiction_score=0.0,
                scale_sigma=seed.scale_sigma,
                psf_radius=seed.psf_radius,
                roi_id=seed.roi_id,
                uncertainty_score=seed.uncertainty_score,
                uncertainty_reason=seed.uncertainty_reason,
                density_context=dict(getattr(seed, "density_context", {}) or {}),
                score_components=dict(seed.score_components),
                status=seed.status,
                meta=dict(seed.meta),
            )
            combined.meta["features"] = bundle
            combined.meta["consensus_votes"] = int(votes)
            combined.meta["supporting_modalities"] = list(combined.supporting_modalities)
            merged.append(combined)
        return merged

    def _gating_strategy_candidates(
        self,
        *,
        image,
        t_idx: int,
        z_idx: int,
        strategy: str,
        label: str,
    ) -> list[PointSuggestion]:
        """Generate candidates using generalized modality evidence strategies."""
        model = getattr(self, "_suggestion_model", None)
        if model is None or not hasattr(model, "predict"):
            return []
        frames = self._available_modality_frames(image, t_idx, z_idx)
        if not frames:
            return []
        strategy_key = str(strategy or "current_view").lower()
        generation_space = str(
            getattr(self.controller.session_state, "generation_space", "stack")
        ).strip().lower()
        roi_id = "active_roi" if self.roi_shape != "none" else None
        roi_shape = str(self.roi_shape)
        roi_rect = tuple(self.roi_rect)

        def _predict_one(modality_id: str, frame: np.ndarray) -> list[PointSuggestion]:
            rows = model.predict(
                frame,
                image_id=image.id,
                image_name=image.name,
                t=t_idx,
                z=z_idx,
                label=label,
                strategy="raw",
                roi_id=roi_id,
                roi_shape=roi_shape,
                roi_rect=roi_rect,
            )
            for row in rows:
                row.source_modality = modality_id
                row.meta.setdefault("features", {})
                row.meta["features"][modality_id] = dict(row.score_components)
            return rows

        # Projection-space generation changes the evidence basis without
        # changing the annotation truth path. It stays deterministic for
        # identical inputs and avoids hidden count-based suppression.
        if (
            generation_space == "projection"
            and "_full_stack_t" in frames
            and hasattr(model, "predict_from_stack")
        ):
            try:
                rows = model.predict_from_stack(
                    frames["_full_stack_t"],
                    image_id=image.id,
                    image_name=image.name,
                    label=label,
                    z_frame=z_idx,
                    strategy="raw",
                    roi_id=roi_id,
                    roi_shape=roi_shape,
                    roi_rect=roi_rect,
                    refine_from_stack=False,
                )
                for row in rows:
                    row.source_modality = f"{strategy_key}_projection"
                    row.meta.setdefault("features", {})
                    row.meta["generation_space"] = "projection"
                    row.meta["features"][row.source_modality] = dict(row.score_components)
                return rows
            except Exception:
                pass

        # Stack-aware detection: uses full temporal/z stack for enhanced SNR
        if strategy_key in ("stack_aware", "stack-aware"):
            full_stack = frames.get("_full_stack_t")
            if full_stack is not None and hasattr(model, "predict_from_stack"):
                try:
                    rows = model.predict_from_stack(
                        full_stack,
                        image_id=image.id,
                        image_name=image.name,
                        label=label,
                        z_frame=z_idx,
                        strategy="raw",
                        roi_id=roi_id,
                        roi_shape=roi_shape,
                        roi_rect=roi_rect,
                        refine_from_stack=False,  # Optimized: mean projection is optimal
                    )
                    for row in rows:
                        row.source_modality = "stack_aware"
                        row.meta.setdefault("features", {})
                        row.meta["features"]["stack_aware"] = dict(row.score_components)
                    return rows
                except Exception as exc:
                    import sys
                    print(f"Warning: stack-aware prediction failed: {exc}", file=sys.stderr)
            # Fall back to raw if stack unavailable
            return _predict_one("raw", frames["raw"])

        if strategy_key in frames:
            return _predict_one(strategy_key, frames[strategy_key])

        if strategy_key in ("evidence_consensus", "consensus"):
            use_modalities = [mid for mid in ("raw", "corrected", "mean_projection") if mid in frames]
            modality_candidates = {mid: _predict_one(mid, frames[mid]) for mid in use_modalities}
            return self._merge_modal_consensus(modality_candidates, k_required=2)

        if strategy_key in ("evidence_contradiction",):
            base_ids = [mid for mid in ("raw", "corrected", "mean_projection") if mid in frames]
            modality_candidates = {mid: _predict_one(mid, frames[mid]) for mid in base_ids}
            seeds = self._merge_modal_consensus(modality_candidates, k_required=1)
            cfg = getattr(self, "_suggestion_rule_config", None)
            if cfg is None:
                return seeds
            rule = getattr(cfg, "semantic_rules", {}).get(strategy_key)
            if rule is None:
                return seeds
            for suggestion in seeds:
                features = dict(suggestion.meta.get("features", {}))
                penalty = 0.0
                support_modalities = set(getattr(suggestion, "supporting_modalities", []) or [])
                for modality_id, threshold in dict(rule.positive_modalities).items():
                    peak = float(dict(features.get(modality_id, {})).get("peak", -np.inf))
                    if peak < float(threshold):
                        penalty += 0.15
                    else:
                        support_modalities.add(str(modality_id))
                contradiction = 0.0
                for modality_id, threshold in dict(rule.negative_modalities).items():
                    peak = float(dict(features.get(modality_id, {})).get("peak", 0.0))
                    if peak > float(threshold):
                        contradiction = max(
                            contradiction,
                            min(1.0, (peak - float(threshold)) / max(abs(float(threshold)), 1.0)),
                        )
                        support_modalities.add(str(modality_id))
                suggestion.supporting_modalities = sorted(support_modalities)
                suggestion.control_contradiction_score = float(max(getattr(suggestion, "control_contradiction_score", 0.0) or 0.0, contradiction))
                suggestion.cross_modality_consistency_score = float(max(0.0, 1.0 - penalty - contradiction))
                suggestion.score_components["control_contradiction_score"] = float(suggestion.control_contradiction_score)
                suggestion.score_components["cross_modality_consistency_score"] = float(suggestion.cross_modality_consistency_score)
                suggestion.meta["supporting_modalities"] = list(suggestion.supporting_modalities)
                suggestion.meta["control_contradiction_score"] = float(suggestion.control_contradiction_score)
                suggestion.meta["cross_modality_consistency_score"] = float(suggestion.cross_modality_consistency_score)
                if contradiction > 0.0:
                    suggestion.uncertainty_reason = ",".join(
                        filter(
                            None,
                            dict.fromkeys(
                                [str(getattr(suggestion, "uncertainty_reason", "") or "").strip(), "control_contradiction"]
                            ),
                        )
                    )
                    suggestion.meta["uncertainty_reason"] = suggestion.uncertainty_reason
                    suggestion.uncertainty_score = float(max(float(getattr(suggestion, "uncertainty_score", 0.0) or 0.0), min(1.0, contradiction)))
                    suggestion.meta["uncertainty_score"] = float(suggestion.uncertainty_score)
            return seeds

        # Legacy channel strategies still supported via existing gating.
        seed_id = "current_view" if "current_view" in frames else next(iter(frames.keys()))
        seeded = _predict_one(seed_id, frames[seed_id])
        if strategy_key.startswith("channel_"):
            return self._apply_cross_channel_gating(
                seeded,
                strategy=strategy_key,
                t_idx=t_idx,
                z_idx=z_idx,
            )
        return seeded

    def _load_suggestion_rule_config_dialog(self) -> None:
        """Load JSON/YAML experiment rule config for cross-channel gating."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Suggestion Rule Config",
            str(pathlib.Path.cwd()),
            "Config Files (*.json *.yaml *.yml)",
        )
        if not path:
            return
        try:
            self._suggestion_rule_config = load_suggestion_rule_config(pathlib.Path(path))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Rule config load failed", str(exc))
            return
        self._status_success(
            f"Loaded suggestion rule config: {pathlib.Path(path).name}.",
            timeout_ms=3000,
            source="standard.suggestion_rules",
        )

    def _apply_cross_channel_gating(
        self, suggestions: list[PointSuggestion], *, strategy: str, t_idx: int, z_idx: int
    ) -> list[PointSuggestion]:
        """Filter proposals by per-channel peak/low constraints."""
        strategy_key = str(strategy or "raw").lower()
        if strategy_key not in (
            "channel_a_only",
            "channel_b_only",
            "channel_a_peak_b_low",
            "channel_b_peak_a_low",
        ):
            return suggestions
        image = self.primary_image
        if int(getattr(image, "channel_count", 1)) < 2:
            return suggestions
        if not hasattr(self, "_get_channel_stack"):
            return suggestions
        ch0 = self._get_channel_stack(image, 0)
        ch1 = self._get_channel_stack(image, 1)
        if ch0 is None or ch1 is None:
            return suggestions
        frame0 = ch0[t_idx, z_idx]
        frame1 = ch1[t_idx, z_idx]
        high0 = float(np.nanquantile(frame0, 0.85))
        low0 = float(np.nanquantile(frame0, 0.35))
        high1 = float(np.nanquantile(frame1, 0.85))
        low1 = float(np.nanquantile(frame1, 0.35))
        rule = None
        cfg = getattr(self, "_suggestion_rule_config", None)
        if cfg is not None:
            channels = getattr(cfg, "channels", {})
            if "A" in channels:
                ch = channels["A"]
                high0 = float(ch.peak_min if ch.peak_min is not None else high0)
                low0 = float(ch.background_max)
            if "B" in channels:
                ch = channels["B"]
                high1 = float(ch.peak_min if ch.peak_min is not None else high1)
                low1 = float(ch.background_max)
            semantic_rules = getattr(cfg, "semantic_rules", {})
            rule = semantic_rules.get(strategy_key)
        filtered: list[PointSuggestion] = []
        for suggestion in suggestions:
            y = int(round(float(suggestion.y)))
            x = int(round(float(suggestion.x)))
            if y < 0 or x < 0 or y >= frame0.shape[0] or x >= frame0.shape[1]:
                continue
            v0 = float(frame0[y, x])
            v1 = float(frame1[y, x])
            keep = True
            if strategy_key == "channel_a_only":
                keep = v0 >= v1
            elif strategy_key == "channel_b_only":
                keep = v1 >= v0
            elif strategy_key == "channel_a_peak_b_low":
                keep = (v0 >= high0) and (v1 <= low1)
            elif strategy_key == "channel_b_peak_a_low":
                keep = (v1 >= high1) and (v0 <= low0)
            if keep and rule is not None:
                if rule.channel_a_peak_gt is not None and v0 <= float(rule.channel_a_peak_gt):
                    keep = False
                if rule.channel_b_peak_gt is not None and v1 <= float(rule.channel_b_peak_gt):
                    keep = False
                if rule.channel_a_lt is not None and v0 >= float(rule.channel_a_lt):
                    keep = False
                if rule.channel_b_lt is not None and v1 >= float(rule.channel_b_lt):
                    keep = False
                if rule.roi_id is not None and str(getattr(suggestion, "roi_id", "")) != str(
                    rule.roi_id
                ):
                    keep = False
            if keep:
                filtered.append(suggestion)
        return filtered

    def _rank_and_calibrate_suggestions(self, suggestions: list[PointSuggestion]) -> list[PointSuggestion]:
        """Apply lightweight ranker and calibrated p_accept if available."""
        if not suggestions:
            return suggestions
        annotation_space = str(getattr(self.controller.session_state, "annotation_space", "stack"))
        try:
            ranked = self.controller.score_suggestions_for_context(
                list(suggestions),
                annotation_space=annotation_space,
            )
        except Exception:
            ranked = list(suggestions)
        ranked.sort(
            key=lambda s: (
                -float(getattr(s, "score", 0.0)),
                int(getattr(s, "t", 0)),
                int(getattr(s, "z", 0)),
                float(getattr(s, "y", 0.0)),
                float(getattr(s, "x", 0.0)),
                str(getattr(s, "suggestion_id", "")),
            )
        )

        # Apply experimental sidecar predictions only when explicitly enabled.
        if self._interactive_learning_enabled() and self._interactive_learning_model.is_trained:
            predictions = self._interactive_learning_model.predict(ranked)
            for suggestion, prediction in zip(ranked, predictions):
                suggestion.meta["ml_prediction"] = prediction["accepted"]
                suggestion.meta["ml_confidence"] = prediction["confidence"]
                suggestion.meta["ml_uncertainty"] = prediction["uncertainty"]
                suggestion.meta["ml_method"] = prediction["method"]
        else:
            for suggestion in ranked:
                for key in ("ml_prediction", "ml_confidence", "ml_uncertainty", "ml_method"):
                    suggestion.meta.pop(key, None)

        return ranked

    def _enrich_suggestions_for_training(
        self, suggestions: list[PointSuggestion], image_data: np.ndarray
    ) -> None:
        """Attach microscopy context features and self-confirmation flags."""
        anns = list(self.annotations.get(self.primary_image.id, []))
        h, w = image_data.shape[:2]
        for suggestion in suggestions:
            y = float(suggestion.y)
            x = float(suggestion.x)
            min_border = min(x, y, float(w - 1) - x, float(h - 1) - y)
            nearest_truth = float("inf")
            nearest_any = float("inf")
            for kp in anns:
                if int(kp.t) not in (int(suggestion.t), -1):
                    continue
                if int(kp.z) not in (int(suggestion.z), -1):
                    continue
                dx = float(kp.x) - x
                dy = float(kp.y) - y
                dist = float((dx * dx + dy * dy) ** 0.5)
                nearest_any = min(nearest_any, dist)
                status = str(getattr(kp, "status", "active") or "active").strip().lower()
                source = str(getattr(kp, "source", "manual") or "manual").strip().lower()
                if status in {"rejected", "conflict"} or source in {"suggestion", "proposed"}:
                    continue
                nearest_truth = min(nearest_truth, dist)
            if not np.isfinite(nearest_truth):
                nearest_truth = float(max(h, w))
            if not np.isfinite(nearest_any):
                nearest_any = float(max(h, w))
            suggestion.meta["distance_to_nearest_accepted"] = float(nearest_truth)
            suggestion.meta["distance_to_nearest_truth_strict"] = float(nearest_truth)
            suggestion.meta["distance_to_any_annotation"] = float(nearest_any)
            suggestion.meta["border_proximity"] = float(max(0.0, min_border))
            suggestion.meta["derived_from_accepted_area"] = bool(
                nearest_truth <= float(getattr(suggestion, "psf_radius", 6.0))
            )

    def _note_annotation_edit(self, image_id: Optional[int] = None) -> None:
        """Record latest annotation-edit timestamp for staleness guardrails."""
        target_id = int(self.primary_image.id if image_id is None else image_id)
        by_image = getattr(self, "_annotation_edit_ts_by_image", None)
        if by_image is None:
            by_image = {}
            self._annotation_edit_ts_by_image = by_image
        by_image[target_id] = float(time.time())

    def _suggest_points_current_slice(self) -> None:
        """Generate model suggestions for the current slice."""
        assist_generation.suggest_points_current_slice(self)

    def _suggest_points_current_image(self) -> None:
        """Generate suggestions for all T/Z slices in the active image."""
        assist_generation.suggest_points_current_image(self)

    def _accept_visible_suggestions(self) -> None:
        """Accept visible suggestions as one reviewed batch command."""
        assist_generation.accept_visible_suggestions(self)

    def _accept_high_confidence_suggestions(self) -> None:
        """Accept all visible green suggestions (calibrated p_accept >= 0.75)."""
        assist_generation.accept_high_confidence_suggestions(self)

    def _preview_batch_accept_dialog(
        self,
        *,
        candidates: List[PointSuggestion],
        title: str,
        description: str,
        stale_override_required: bool = False,
    ) -> Optional[List[str]]:
        """Show checkbox preview dialog and return selected suggestion IDs.

        Returns None when user cancels.
        """
        return assist_generation.preview_batch_accept_dialog(
            self,
            candidates=candidates,
            title=title,
            description=description,
            stale_override_required=stale_override_required,
        )

    def _reject_visible_suggestions(self) -> None:
        """Reject all visible suggestions via undoable commands."""
        assist_generation.reject_visible_suggestions(self)

    def _accept_suggestions_in_roi(self) -> None:
        """Accept visible suggestions that are currently inside ROI."""
        assist_generation.accept_suggestions_in_roi(self)

    def _clear_suggestions_current_image(self) -> None:
        """Clear all pending suggestions for active image."""
        assist_generation.clear_suggestions_current_image(self)

    def _batch_correct_suggestions_dialog(self) -> None:
        """Apply a constant (dx, dy) correction to top-N uncertain suggestions."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions to batch-correct.",
                timeout_ms=2500,
                source="standard.batch_correct",
            )
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Batch Correct Suggestions")
        layout = QtWidgets.QFormLayout(dialog)
        n_spin = QtWidgets.QSpinBox(dialog)
        n_spin.setRange(1, len(ranked))
        n_spin.setValue(min(25, len(ranked)))
        dx_spin = QtWidgets.QDoubleSpinBox(dialog)
        dx_spin.setRange(-500.0, 500.0)
        dx_spin.setDecimals(2)
        dx_spin.setValue(0.0)
        dy_spin = QtWidgets.QDoubleSpinBox(dialog)
        dy_spin.setRange(-500.0, 500.0)
        dy_spin.setDecimals(2)
        dy_spin.setValue(0.0)
        layout.addRow("Select top-N uncertain:", n_spin)
        layout.addRow("Offset dx (pixels):", dx_spin)
        layout.addRow("Offset dy (pixels):", dy_spin)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        layout.addRow(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        if dialog.exec() != int(QtWidgets.QDialog.DialogCode.Accepted):
            return
        self._apply_batch_suggestion_offset(
            count=int(n_spin.value()),
            dx=float(dx_spin.value()),
            dy=float(dy_spin.value()),
        )

    def _apply_batch_suggestion_offset(self, *, count: int, dx: float, dy: float) -> None:
        """Apply (dx, dy) to first `count` uncertain suggestions and log correction signal."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions to batch-correct.",
                timeout_ms=2500,
                source="standard.batch_correct",
            )
            return
        rows = list(ranked[: max(0, int(count))])
        if not rows:
            self._status_info(
                "No suggestions selected for batch correction.",
                timeout_ms=2500,
                source="standard.batch_correct",
            )
            return
        moved = 0
        h = int(self.primary_image.array.shape[2]) if getattr(self.primary_image, "array", None) is not None else None
        w = int(self.primary_image.array.shape[3]) if getattr(self.primary_image, "array", None) is not None else None
        for suggestion in rows:
            old_x = float(suggestion.x)
            old_y = float(suggestion.y)
            new_x = old_x + float(dx)
            new_y = old_y + float(dy)
            if w is not None:
                new_x = float(max(0.0, min(float(w - 1), new_x)))
            if h is not None:
                new_y = float(max(0.0, min(float(h - 1), new_y)))
            suggestion.x = new_x
            suggestion.y = new_y
            suggestion.meta["batch_corrected"] = True
            suggestion.meta["batch_dx"] = float(dx)
            suggestion.meta["batch_dy"] = float(dy)
            suggestion.meta["batch_shift_distance"] = float((dx * dx + dy * dy) ** 0.5)
            if hasattr(self.controller, "observe_suggestion_correction"):
                self.controller.observe_suggestion_correction(suggestion, dx=dx, dy=dy)
            self.controller.update_suggestion_metrics(
                correction_distance=float((new_x - old_x) ** 2 + (new_y - old_y) ** 2) ** 0.5
            )
            moved += 1
        self.controller.append_audit_event(
            "suggestions_batch_corrected",
            image_id=self.primary_image.id,
            count=int(moved),
            dx=float(dx),
            dy=float(dy),
        )
        self._request_ui_refresh("standard-actions")
        self._refresh_assist_warmup_panel()
        self._status_success(
            f"Batch-corrected {moved} suggestion(s) with dx={dx:.2f}, dy={dy:.2f}.",
            timeout_ms=3000,
            source="standard.batch_correct",
        )

    def _apply_review_queue_offset(self, count: int, dx: float, dy: float) -> None:
        """Apply inline review-queue XY offset controls without opening a modal."""
        self._apply_batch_suggestion_offset(count=int(count), dx=float(dx), dy=float(dy))

    def _propagate_suggestions_remaining_dialog(self) -> None:
        """Generate suggestions in remaining T/Z slices as a background task."""
        image = self.primary_image
        arr = getattr(image, "array", None)
        if arr is None or getattr(arr, "ndim", 0) < 4:
            self._status_warning(
                "No stack loaded for propagation.",
                timeout_ms=2500,
                source="standard.propagate",
            )
            return
        modes = (
            "remaining_t_current_z",
            "remaining_z_current_t",
            "remaining_tz",
        )
        labels = {
            "remaining_t_current_z": "Remaining T at current Z",
            "remaining_z_current_t": "Remaining Z at current T",
            "remaining_tz": "Remaining T/Z (grid)",
        }
        mode, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Propagate Suggestions",
            "Scope:",
            [labels[m] for m in modes],
            0,
            False,
        )
        if not ok:
            return
        mode_key = next((k for k, v in labels.items() if v == str(mode)), "remaining_t_current_z")
        t0 = int(self.t_slider.value())
        z0 = int(self.z_slider.value())
        t_size = int(arr.shape[0])
        z_size = int(arr.shape[1])
        targets: list[tuple[int, int]] = []
        if mode_key == "remaining_t_current_z":
            targets = [(t, z0) for t in range(t0, t_size)]
        elif mode_key == "remaining_z_current_t":
            targets = [(t0, z) for z in range(z0, z_size)]
        else:
            for t in range(t0, t_size):
                for z in range(z_size):
                    if t == t0 and z < z0:
                        continue
                    targets.append((t, z))
        if not targets:
            self._status_info(
                "No remaining slices to propagate.",
                timeout_ms=2500,
                source="standard.propagate",
            )
            return

        image_id = int(image.id)
        image_name = str(image.name)
        label = str(self.current_label)
        strategy = str(getattr(self, "_suggestion_strategy", "current_view"))
        roi_shape = str(self.roi_shape)
        roi_rect = tuple(self.roi_rect)

        def _job(progress, cancel_token):
            out: list[PointSuggestion] = []
            total = max(1, len(targets))
            for idx, (t_idx, z_idx) in enumerate(targets):
                if cancel_token.is_cancelled():
                    return None
                frame = np.asarray(arr[t_idx, z_idx, :, :], dtype=np.float32)
                generated = self._suggestion_model.predict(
                    frame,
                    image_id=image_id,
                    image_name=image_name,
                    t=int(t_idx),
                    z=int(z_idx),
                    label=label,
                    strategy=strategy,
                    roi_shape=roi_shape,
                    roi_rect=roi_rect,
                )
                out.extend(generated)
                progress(int((idx + 1) / total * 100), f"{idx + 1}/{total} slices")
            return out

        def _on_result(result):
            if result is None:
                self._status_info(
                    "Suggestion propagation cancelled.",
                    timeout_ms=2500,
                    source="standard.propagate",
                )
                return
            generated = list(result)
            for suggestion in generated:
                frame = np.asarray(arr[int(suggestion.t), int(suggestion.z), :, :], dtype=np.float32)
                self._enrich_suggestions_for_training([suggestion], frame)
            generated = self._rank_and_calibrate_suggestions(generated)
            generated_at = float(time.time())
            for suggestion in generated:
                suggestion.meta["generated_at_ts"] = generated_at
            self.controller.append_generated_suggestions(image_id, generated, sort_pending=True)
            self.controller.update_suggestion_metrics(generated=len(generated))
            self.controller.append_audit_event(
                "suggestions_propagated_remaining",
                image_id=image_id,
                count=len(generated),
                mode=str(mode_key),
                strategy=strategy,
            )
            self._remember_generation_context(generated)
            if generated:
                first = generated[0]
                self.t_slider.setValue(max(self.t_slider.minimum(), min(int(first.t), self.t_slider.maximum())))
                self.z_slider.setValue(max(self.z_slider.minimum(), min(int(first.z), self.z_slider.maximum())))
            self._request_ui_refresh("standard-actions")
            self._refresh_assist_warmup_panel()
            self._status_success(
                f"Propagated {len(generated)} suggestions across remaining slices.",
                timeout_ms=3500,
                source="standard.propagate",
            )

        self._submit_analysis_job(
            _job,
            name="Propagate suggestions",
            on_result=_on_result,
        )

    def _toggle_suggestions_overlay(self, checked: bool) -> None:
        """Toggle suggestion overlay rendering."""
        self._show_suggestion_overlay = bool(checked)
        self._request_ui_refresh("standard-actions")

    def _visible_suggestions_uncertain_first(self) -> list[PointSuggestion]:
        """Visible suggestions ranked by uncertainty (lowest score first)."""
        return sorted(
            self._visible_suggestions(),
            key=lambda s: float(
                dict(getattr(s, "meta", {}) or {}).get(
                    "p_accept", getattr(s, "score", getattr(s, "confidence", 0.0))
                )
            ),
        )

    def _review_throughput_snapshot(self) -> tuple[str, float]:
        """Return compact throughput text and avg sec/decision for current session."""
        return assist_review.review_throughput_snapshot(self)

    def _calibration_sparkline_text(self) -> str:
        """Return tiny reliability sparkline from p_accept bins."""
        return assist_review.calibration_sparkline_text(self)

    def _review_queue_progress_counts(self) -> tuple[int, int]:
        """Return (processed, total) counts for current image and T/Z context."""
        return assist_review.review_queue_progress_counts(self)

    def _refresh_review_queue_panel(self) -> None:
        """Refresh right-dock assisted review queue details and progress."""
        assist_review.refresh_review_queue_panel(self)

    def _on_review_queue_row_selected(self, row: int) -> None:
        """Handle row selection from suggested-points table."""
        assist_review.on_review_queue_row_selected(self, row)

    def _annotation_exists_for_suggestion(self, image_id: int, suggestion_id: str) -> bool:
        """Return True if an annotation linked to suggestion_id already exists."""
        sid = str(suggestion_id)
        rows = list(getattr(self.controller.session_state, "annotations", {}).get(int(image_id), []))
        for ann in rows:
            meta = dict(getattr(ann, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                return True
        return False

    def _remove_annotation_for_suggestion(self, image_id: int, suggestion_id: str) -> int:
        """Remove annotations linked to suggestion_id and return count removed."""
        return int(self.controller.remove_annotations_for_suggestion(int(image_id), str(suggestion_id)))

    def _append_annotation_from_suggestion(self, suggestion: PointSuggestion) -> None:
        """Create a committed annotation from suggestion if it does not already exist."""
        self.controller.append_annotation_from_suggestion(suggestion)

    def _set_selected_suggestion_decision(self, suggestion_id: str, status: str) -> None:
        """Set selected suggestion decision any time: accepted/rejected/proposed."""
        assist_review.set_selected_suggestion_decision(self, suggestion_id, status)

    def _confirm_suggestion_redecision(self, target_status: str) -> bool:
        """Confirm destructive re-decision from accepted to non-accepted state."""
        return assist_review.confirm_suggestion_redecision(self, target_status)

    def _refresh_suggestion_explain_panel(self, suggestion: PointSuggestion | None) -> None:
        """Refresh 'Why was this suggested?' panel for the current suggestion."""
        panel = getattr(self, "suggestion_explain_panel", None)
        if panel is None:
            return
        if suggestion is None:
            panel.coords_lbl.setText("(x=-, y=-, t=-, z=-)")
            panel.class_lbl.setText("class: n/a")
            panel.score_lbl.setText("generator score: n/a")
            panel.calib_lbl.setText("Acceptance likelihood (p_accept): n/a")
            panel.uncertainty_lbl.setText("uncertainty: n/a")
            panel.nn_lbl.setText("nearest accepted distance: n/a")
            panel.label_match_lbl.setText("label match: n/a")
            panel.context_lbl.setText("confidence mode: heuristic")
            panel.stale_lbl.setText("staleness: n/a")
            panel.modality_lbl.setText("modality evidence: n/a")
            panel.control_lbl.setText("control contradiction: n/a")
            panel.components_txt.setPlainText("No suggestion selected.")
            panel.patch_lbl.setText("No suggestion selected.")
            panel.patch_lbl.setPixmap(QtGui.QPixmap())
            if hasattr(panel, "assist_state_lbl"):
                state = self._canonical_assist_state([])
                panel.header_lbl.setText(
                    f"Why Was This Suggested? | Assist: {assist_state_label(state)}"
                )
                self._style_assist_state_label(panel.assist_state_lbl, state, prefix="Assist: ")
            return
        meta = dict(getattr(suggestion, "meta", {}) or {})
        if hasattr(panel, "assist_state_lbl"):
            state = self._canonical_assist_state([suggestion])
            panel.header_lbl.setText(
                f"Why Was This Suggested? | Assist: {assist_state_label(state)}"
            )
            self._style_assist_state_label(panel.assist_state_lbl, state, prefix="Assist: ")
        panel.coords_lbl.setText(
            f"(x={int(round(float(suggestion.x)))}, y={int(round(float(suggestion.y)))}, "
            f"t={int(suggestion.t)}, z={int(suggestion.z)})"
        )
        panel.class_lbl.setText(
            f"class: {str(meta.get('candidate_class', 'new')).replace('_', ' ')} | status: {str(getattr(suggestion, 'status', 'proposed'))}"
        )
        panel.score_lbl.setText(f"generator score: {float(getattr(suggestion, 'score', 0.0)):.3f}")
        p_accept = meta.get("p_accept")
        uncertainty_score = getattr(suggestion, "uncertainty_score", meta.get("uncertainty_score"))
        uncertainty_reason = str(getattr(suggestion, "uncertainty_reason", meta.get("uncertainty_reason", "")) or "")
        if p_accept is None:
            panel.calib_lbl.setText("Acceptance likelihood (p_accept): n/a (heuristic-only)")
            panel.context_lbl.setText("confidence mode: heuristic")
        else:
            panel.calib_lbl.setText(f"Acceptance likelihood (p_accept): {float(p_accept):.3f}")
            panel.context_lbl.setText("confidence mode: calibrated")
        if uncertainty_score is None:
            panel.uncertainty_lbl.setText("uncertainty: n/a")
        else:
            detail = f" ({uncertainty_reason.replace(',', ', ')})" if uncertainty_reason else ""
            panel.uncertainty_lbl.setText(f"uncertainty: {float(uncertainty_score):.3f}{detail}")
        panel.calib_lbl.setToolTip(
            "Acceptance likelihood (p_accept) predicts your acceptance behavior, "
            "not ground-truth correctness."
        )
        nn = meta.get("distance_to_nearest_accepted")
        panel.nn_lbl.setText(
            "nearest accepted distance: n/a"
            if nn is None
            else f"nearest accepted distance: {float(nn):.2f}px"
        )
        nearest_same = meta.get("nearest_same_label_px")
        nearest_other = meta.get("nearest_other_label_px")
        if nearest_same is not None and (nearest_other is None or float(nearest_same) <= float(nearest_other)):
            panel.label_match_lbl.setText("label match: nearest truth has same label")
        elif nearest_other is not None:
            panel.label_match_lbl.setText("label match: nearest truth has different label")
        else:
            panel.label_match_lbl.setText("label match: n/a")
        ts = meta.get("generated_at_ts")
        if ts is None:
            panel.stale_lbl.setText("staleness: unknown")
        else:
            age_s = max(0.0, float(time.time()) - float(ts))
            panel.stale_lbl.setText(f"staleness: {age_s:.1f}s")
        support_modalities = list(getattr(suggestion, "supporting_modalities", []) or meta.get("supporting_modalities", []) or [])
        if support_modalities:
            panel.modality_lbl.setText(
                "modality evidence: "
                f"{', '.join(str(v) for v in support_modalities)} | "
                f"consistency={float(getattr(suggestion, 'cross_modality_consistency_score', meta.get('cross_modality_consistency_score', 1.0)) or 0.0):.2f}"
            )
        else:
            panel.modality_lbl.setText("modality evidence: single-modality / unavailable")
        contradiction = getattr(suggestion, "control_contradiction_score", meta.get("control_contradiction_score"))
        panel.control_lbl.setText(
            "control contradiction: n/a"
            if contradiction is None
            else f"control contradiction: {float(contradiction):.2f}"
        )
        comp = dict(getattr(suggestion, "score_components", {}) or {})
        if comp or meta:
            lines = [f"{k}: {float(v):.4f}" for k, v in sorted(comp.items()) if isinstance(v, (int, float))]
            for key in ("local_density", "distance_to_recent_reject", "distance_to_nearest_accepted", "uncertainty_score", "control_contradiction_score", "cross_modality_consistency_score"):
                if key in meta:
                    lines.append(f"{key}: {float(meta[key]):.4f}")
            density_context = dict(getattr(suggestion, "density_context", {}) or meta.get("density_context", {}) or {})
            for key, value in sorted(density_context.items()):
                if isinstance(value, (int, float)):
                    lines.append(f"density.{key}: {float(value):.4f}")
            panel.components_txt.setPlainText("\n".join(lines) if lines else str(comp))
        else:
            panel.components_txt.setPlainText("No score components available.")

        frame = self._slice_data(
            self.primary_image,
            t_override=int(suggestion.t),
            z_override=int(suggestion.z),
        )
        if frame is None:
            panel.patch_lbl.setText("Patch unavailable.")
            panel.patch_lbl.setPixmap(QtGui.QPixmap())
            return
        half = 16
        y = int(round(float(suggestion.y)))
        x = int(round(float(suggestion.x)))
        y0 = max(0, y - half)
        x0 = max(0, x - half)
        y1 = min(frame.shape[0], y + half)
        x1 = min(frame.shape[1], x + half)
        patch = np.asarray(frame[y0:y1, x0:x1], dtype=np.float32)
        if patch.size == 0:
            panel.patch_lbl.setText("Patch unavailable.")
            panel.patch_lbl.setPixmap(QtGui.QPixmap())
            return
        pmin = float(np.nanmin(patch))
        pmax = float(np.nanmax(patch))
        denom = (pmax - pmin) if pmax > pmin else 1.0
        norm = ((patch - pmin) / denom * 255.0).clip(0, 255).astype(np.uint8)
        rgb = np.stack([norm, norm, norm], axis=-1)
        h, w = rgb.shape[:2]
        image = QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(image.copy()).scaled(
            180,
            180,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.FastTransformation,
        )
        panel.patch_lbl.setPixmap(pixmap)
        panel.patch_lbl.setText("")

    def _refresh_assist_warmup_panel(self) -> None:
        """Refresh assist warmup counters and queue state in the settings panel."""
        if not hasattr(self, "assist_warmup_status_lbl"):
            self._refresh_review_queue_panel()
            return
        if not hasattr(self, "primary_image") or self.primary_image is None:
            self._refresh_review_queue_panel()
            return
        annotation_space = str(getattr(self.controller.session_state, "annotation_space", "stack"))
        ranked = self._visible_suggestions_uncertain_first()
        ref = ranked[0] if ranked else None
        if ref is None:
            all_rows = list(self.suggestions.get(self.primary_image.id, []))
            proposed = [s for s in all_rows if str(getattr(s, "status", "proposed")) == "proposed"]
            if proposed:
                ref = sorted(
                    proposed,
                    key=lambda s: float(dict(getattr(s, "meta", {}) or {}).get("p_accept", s.score)),
                )[0]
        if ref is not None:
            context_key = self.controller._context_key(
                suggestion=ref,
                annotation_space=annotation_space,
            )
            breakdown = self.controller.assist_need_breakdown(
                annotation_space=annotation_space,
                context_key=context_key,
            )
            state = self._canonical_assist_state([ref])
            self._style_assist_state_label(
                self.assist_warmup_status_lbl,
                state,
                prefix="Assist: ",
            )
            self.assist_warmup_context_lbl.setText(
                f"Context labels: {breakdown['context_total']} (need +{breakdown['need_context']})"
            )
        else:
            rows = list(getattr(self.controller.session_state, "suggestion_training_samples", []))
            pos = sum(1 for row in rows if int(row.get("y", 0)) == 1)
            neg = max(0, len(rows) - pos)
            breakdown = {
                "total": int(len(rows)),
                "pos": int(pos),
                "neg": int(neg),
                "need_total": max(
                    0, int(self.controller.session_state.assist_min_total_labels) - int(len(rows))
                ),
                "need_pos": max(
                    0, int(self.controller.session_state.assist_min_positive_labels) - int(pos)
                ),
                "need_neg": max(
                    0, int(self.controller.session_state.assist_min_negative_labels) - int(neg)
                ),
                "context_total": 0,
                "need_context": int(self.controller.session_state.assist_min_labels_per_context),
            }
            self._style_assist_state_label(
                self.assist_warmup_status_lbl,
                self._canonical_assist_state([]),
                prefix="Assist: ",
            )
            self.assist_warmup_context_lbl.setText(
                f"Context labels: 0 (need +{breakdown['need_context']})"
            )
        self.assist_warmup_counts_lbl.setText(
            f"Labels total/+/-: {breakdown['total']}/{breakdown['pos']}/{breakdown['neg']}"
        )
        self.assist_warmup_need_lbl.setText(
            "Need "
            f"+{breakdown['need_total']} total, "
            f"+{breakdown['need_pos']} positive, "
            f"+{breakdown['need_neg']} negative"
        )
        self.assist_warmup_queue_lbl.setText(f"Visible uncertain queue: {len(ranked)}")
        if hasattr(self, "assist_warmup_next_btn"):
            self.assist_warmup_next_btn.setEnabled(bool(ranked))
        self._refresh_review_queue_panel()

    def _focus_suggestion(self, suggestion: PointSuggestion) -> None:
        """Jump view to a suggestion and auto-pan only when it is off-screen."""
        if hasattr(self, "t_slider"):
            self.t_slider.setValue(
                max(self.t_slider.minimum(), min(int(suggestion.t), self.t_slider.maximum()))
            )
        if hasattr(self, "z_slider"):
            self.z_slider.setValue(
                max(self.z_slider.minimum(), min(int(suggestion.z), self.z_slider.maximum()))
            )
        frame_ax = (
            self.renderer.axes.get("frame") if getattr(self, "renderer", None) is not None else None
        )
        if frame_ax is not None:
            x = float(suggestion.x)
            y = float(suggestion.y)
            x0, x1 = frame_ax.get_xlim()
            y0, y1 = frame_ax.get_ylim()
            bounds_ok = np.isfinite(np.asarray([x0, x1, y0, y1], dtype=float)).all()
            if bounds_ok:
                x_min, x_max = (x0, x1) if x0 <= x1 else (x1, x0)
                y_min, y_max = (y0, y1) if y0 <= y1 else (y1, y0)
                in_view = (x_min <= x <= x_max) and (y_min <= y <= y_max)
                if not in_view:
                    span_x = abs(x1 - x0)
                    span_y = abs(y1 - y0)
                    fallback_half = float(getattr(self, "_suggestion_focus_zoom_px", 160.0)) / 2.0
                    half_x = span_x / 2.0 if span_x > 0 else fallback_half
                    half_y = span_y / 2.0 if span_y > 0 else fallback_half
                    frame_ax.set_xlim(x - half_x, x + half_x)
                    if y0 <= y1:
                        frame_ax.set_ylim(y - half_y, y + half_y)
                    else:
                        frame_ax.set_ylim(y + half_y, y - half_y)
            else:
                zoom_px = float(getattr(self, "_suggestion_focus_zoom_px", 160.0))
                half = zoom_px / 2.0
                frame_ax.set_xlim(x - half, x + half)
                frame_ax.set_ylim(y + half, y - half)
        self._request_ui_refresh("standard-actions")

    def _focus_current_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        self._focus_suggestion(current)
        self._status_info(
            f"Suggestion {self._suggestion_cursor + 1}/{len(ranked)} score={float(current.score):.3f}",
            timeout_ms=2500,
            source="standard.suggestion_focus",
        )
        self._refresh_review_queue_panel()

    def _next_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = (int(getattr(self, "_suggestion_cursor", 0)) + 1) % len(ranked)
        self._focus_current_uncertain_suggestion()

    def _prev_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = (int(getattr(self, "_suggestion_cursor", 0)) - 1) % len(ranked)
        self._focus_current_uncertain_suggestion()

    def _accept_current_uncertain_suggestion(self) -> None:
        if not self._ensure_annotation_write_context_confirmed("Accept current suggestion"):
            return
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        if not self._ensure_suggestion_accept_allowed(
            current,
            action_label="Accept current suggestion",
            source="standard.suggestion_focus",
        ):
            return

        if self._interactive_learning_enabled():
            self._interactive_learning_model.add_example(current, accepted=True)

        cmd = AcceptSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self._note_annotation_edit(self.primary_image.id)
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
            self._schedule_qc_validation(self.primary_image.id)
            if bool(getattr(self, "_timed_session_active", False)):
                self._timed_session_accepts = int(getattr(self, "_timed_session_accepts", 0)) + 1
                self._timed_session_points = int(getattr(self, "_timed_session_points", 0)) + 1
            self._refresh_assist_warmup_panel()
        self._focus_current_uncertain_suggestion()

    def _accept_and_next_uncertain_suggestion(self) -> None:
        """Mirror keyboard cadence A then N for mixed-input review workflows."""
        if not self._ensure_annotation_write_context_confirmed("Accept current suggestion"):
            return
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._accept_current_uncertain_suggestion()
        self._next_uncertain_suggestion()

    def _reject_current_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]

        if self._interactive_learning_enabled():
            self._interactive_learning_model.add_example(current, accepted=False)

        cmd = RejectSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            self._request_ui_refresh("standard-actions")
            if bool(getattr(self, "_timed_session_active", False)):
                self._timed_session_rejects = int(getattr(self, "_timed_session_rejects", 0)) + 1
            self._refresh_assist_warmup_panel()
        self._focus_current_uncertain_suggestion()

    def _show_current_suggestion_patch(self) -> None:
        """Show a small snap-view patch around the current uncertain suggestion."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._status_info(
                "No visible suggestions above threshold.",
                timeout_ms=2500,
                source="standard.suggestion_focus",
            )
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        suggestion = ranked[self._suggestion_cursor]
        if hasattr(self, "_set_right_dock_mode"):
            self._set_right_dock_mode("inspect")
        frame = self._slice_data(
            self.primary_image,
            t_override=int(suggestion.t),
            z_override=int(suggestion.z),
        )
        if frame is None:
            return
        half = 24
        y = int(round(float(suggestion.y)))
        x = int(round(float(suggestion.x)))
        y0 = max(0, y - half)
        x0 = max(0, x - half)
        y1 = min(frame.shape[0], y + half)
        x1 = min(frame.shape[1], x + half)
        patch = np.asarray(frame[y0:y1, x0:x1], dtype=np.float32)
        if patch.size == 0:
            return
        pmin = float(np.nanmin(patch))
        pmax = float(np.nanmax(patch))
        denom = (pmax - pmin) if pmax > pmin else 1.0
        norm = ((patch - pmin) / denom * 255.0).clip(0, 255).astype(np.uint8)
        rgb = np.stack([norm, norm, norm], axis=-1)
        h, w = rgb.shape[:2]
        image = QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(image.copy()).scaled(
            240,
            240,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.FastTransformation,
        )
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Suggestion Snap View")
        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel(dlg)
        label.setPixmap(pixmap)
        layout.addWidget(label)
        meta = QtWidgets.QLabel(
            f"score={float(suggestion.score):.3f} | id={suggestion.suggestion_id[:8]}",
            dlg,
        )
        layout.addWidget(meta)
        dlg.exec()

    def _show_all_predictions_dialog(self) -> None:
        """Show a comprehensive dialog displaying all predictions/suggestions."""
        image_id = self.primary_image.id if self.primary_image else 0
        all_suggestions = self.suggestions.get(image_id, [])
        
        if not all_suggestions:
            QtWidgets.QMessageBox.information(
                self,
                "No Predictions",
                "No predictions/suggestions available. Please generate suggestions first using 'Suggest Points' from the Assist menu.",
            )
            return
        
        # Create dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"All Predictions ({len(all_suggestions)} total)")
        dlg.resize(900, 600)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Info label
        info_label = QtWidgets.QLabel(
            f"Showing {len(all_suggestions)} predictions for current image. "
            f"Threshold: {self._suggestion_score_threshold:.2f}"
        )
        layout.addWidget(info_label)
        
        # Create table
        table = QtWidgets.QTableWidget(dlg)
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            ["ID", "Score", "X", "Y", "T", "Z", "Label", "ML Pred", "ML Conf", "Method"]
        )
        table.setRowCount(len(all_suggestions))
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Populate table
        for row_idx, suggestion in enumerate(all_suggestions):
            # ID (shortened)
            id_item = QtWidgets.QTableWidgetItem(str(suggestion.suggestion_id)[:12])
            id_item.setToolTip(str(suggestion.suggestion_id))
            table.setItem(row_idx, 0, id_item)
            
            # Score
            score_item = QtWidgets.QTableWidgetItem(f"{float(suggestion.score):.4f}")
            score = float(suggestion.score)
            # Color code by score
            if score >= 0.8:
                score_item.setBackground(QtGui.QColor(67, 160, 71, 100))  # Green
            elif score >= 0.5:
                score_item.setBackground(QtGui.QColor(253, 216, 53, 100))  # Yellow
            else:
                score_item.setBackground(QtGui.QColor(244, 67, 54, 100))  # Red
            table.setItem(row_idx, 1, score_item)
            
            # X, Y, T, Z
            table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(f"{float(suggestion.x):.2f}"))
            table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"{float(suggestion.y):.2f}"))
            table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(str(suggestion.t)))
            table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(str(suggestion.z)))
            
            # Label
            table.setItem(row_idx, 6, QtWidgets.QTableWidgetItem(str(suggestion.label)))
            
            # ML Prediction
            meta = dict(getattr(suggestion, "meta", {}) or {})
            ml_pred = meta.get("ml_prediction", None)
            ml_pred_text = "Accept" if ml_pred is True else "Reject" if ml_pred is False else "N/A"
            ml_pred_item = QtWidgets.QTableWidgetItem(ml_pred_text)
            if ml_pred is True:
                ml_pred_item.setBackground(QtGui.QColor(67, 160, 71, 100))  # Green
            elif ml_pred is False:
                ml_pred_item.setBackground(QtGui.QColor(244, 67, 54, 100))  # Red
            table.setItem(row_idx, 7, ml_pred_item)
            
            # ML Confidence
            ml_conf = meta.get("ml_confidence", None)
            ml_conf_text = f"{float(ml_conf):.3f}" if ml_conf is not None else "N/A"
            ml_conf_item = QtWidgets.QTableWidgetItem(ml_conf_text)
            if ml_conf is not None:
                conf_val = float(ml_conf)
                if conf_val >= 0.75:
                    ml_conf_item.setBackground(QtGui.QColor(67, 160, 71, 80))  # Green
                elif conf_val >= 0.5:
                    ml_conf_item.setBackground(QtGui.QColor(253, 216, 53, 80))  # Yellow
                else:
                    ml_conf_item.setBackground(QtGui.QColor(244, 67, 54, 80))  # Red
            table.setItem(row_idx, 8, ml_conf_item)
            
            # Method
            ml_method = meta.get("ml_method", "rule_based")
            method_text = "ML Trained" if ml_method == "ml_trained" else "Rule-based"
            table.setItem(row_idx, 9, QtWidgets.QTableWidgetItem(method_text))
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # Statistics label
        high_score = sum(1 for s in all_suggestions if float(s.score) >= 0.8)
        medium_score = sum(1 for s in all_suggestions if 0.5 <= float(s.score) < 0.8)
        low_score = sum(1 for s in all_suggestions if float(s.score) < 0.5)
        
        ml_trained = sum(1 for s in all_suggestions if s.meta.get("ml_method") == "ml_trained")
        ml_accept = sum(1 for s in all_suggestions if s.meta.get("ml_prediction") is True)
        ml_reject = sum(1 for s in all_suggestions if s.meta.get("ml_prediction") is False)
        
        stats_label = QtWidgets.QLabel(
            f"Statistics: High score (≥0.8): {high_score} | "
            f"Medium score (0.5-0.8): {medium_score} | "
            f"Low score (<0.5): {low_score}<br>"
            f"ML Status: ML-trained: {ml_trained} | ML Accept: {ml_accept} | ML Reject: {ml_reject}"
        )
        layout.addWidget(stats_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QPushButton("Export to CSV")
        close_btn = QtWidgets.QPushButton("Close")
        jump_btn = QtWidgets.QPushButton("Jump to Selected")
        
        button_layout.addWidget(export_btn)
        button_layout.addWidget(jump_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        # Connect buttons
        close_btn.clicked.connect(dlg.accept)
        
        def jump_to_selected():
            selected = table.selectedItems()
            if selected:
                row = table.currentRow()
                if 0 <= row < len(all_suggestions):
                    suggestion = all_suggestions[row]
                    self.t_slider.setValue(int(suggestion.t))
                    self.z_slider.setValue(int(suggestion.z))
                    self._request_ui_refresh("standard-actions")
                    dlg.accept()
        
        def export_to_csv():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg, "Export Predictions to CSV", "", "CSV Files (*.csv)"
            )
            if path:
                import csv
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Score", "X", "Y", "T", "Z", "Label", "Image"])
                    for s in all_suggestions:
                        writer.writerow([
                            s.suggestion_id,
                            float(s.score),
                            float(s.x),
                            float(s.y),
                            int(s.t),
                            int(s.z),
                            str(s.label),
                            str(s.image_name),
                        ])
                QtWidgets.QMessageBox.information(dlg, "Export Complete", f"Exported {len(all_suggestions)} predictions to:\n{path}")
        
        jump_btn.clicked.connect(jump_to_selected)
        export_btn.clicked.connect(export_to_csv)
        
        dlg.exec()

    def _on_suggestion_auto_retrain_changed(self, checked: bool) -> None:
        """Enable/disable periodic ranker retraining from labels."""
        assist_training.on_suggestion_auto_retrain_changed(self, checked)

    def _on_suggestion_min_labels_changed(self, value: int) -> None:
        """Set minimum labeled samples required before auto-retrain."""
        assist_training.on_suggestion_min_labels_changed(self, value)

    def _train_suggestion_ranker_now(self) -> None:
        """Force immediate ranker training from current labeled history."""
        assist_training.train_suggestion_ranker_now(self)

    def _show_calibration_visualizer(self) -> None:
        """Plot reliability-style p_accept calibration bins from reviewed suggestions."""
        assist_training.show_calibration_visualizer(self)

    def _show_interactive_learning_stats(self) -> None:
        """Show statistics and status of the interactive learning model (Weka-inspired)."""
        if not self._interactive_learning_enabled():
            QtWidgets.QMessageBox.information(
                self,
                "Interactive Learning",
                "Interactive learning is disabled. Enable the experimental sidecar in Assist settings first.",
            )
            return
        
        model = self._interactive_learning_model
        stats = model.get_statistics()
        
        # Create dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Interactive Learning Model Statistics")
        dlg.resize(600, 400)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Model info
        info_text = f"""<b>Interactive Learning Model (Weka-inspired)</b><br><br>
        <b>Status:</b> {"✅ Trained" if model.is_trained else "⏳ Not trained yet"}<br>
        <b>Model Type:</b> {model.model_type}<br>
        <b>Training Examples:</b> {stats['n_examples']}<br>
        <b>Accepts:</b> {stats['n_accepts']} | <b>Rejects:</b> {stats['n_rejects']}<br>
        <b>Model Version:</b> {stats['version']}<br>
        <b>Update Frequency:</b> Every {model.update_frequency} examples<br>
        <b>Min Examples to Train:</b> {model.min_examples_to_train}<br><br>
        """
        
        if model.is_trained:
            info_text += f"<b>Training Accuracy:</b> {stats.get('training_accuracy', 0.0):.2%}<br>"
        
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Feature importance (if trained)
        if model.is_trained:
            importance = model.get_feature_importance()
            if importance:
                layout.addWidget(QtWidgets.QLabel("<b>Top 10 Important Features:</b>"))
                
                importance_table = QtWidgets.QTableWidget()
                importance_table.setColumnCount(2)
                importance_table.setHorizontalHeaderLabels(["Feature", "Importance"])
                importance_table.setRowCount(min(10, len(importance)))
                
                sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
                for i, (feature, imp) in enumerate(sorted_importance[:10]):
                    importance_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(feature)))
                    importance_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{float(imp):.4f}"))
                
                importance_table.resizeColumnsToContents()
                layout.addWidget(importance_table)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        if not model.is_trained and stats['n_examples'] >= model.min_examples_to_train:
            train_btn = QtWidgets.QPushButton("🎓 Train Now")
            def train_now():
                model.train()
                self._status_success(
                    f"Interactive learning model trained with {stats['n_examples']} examples.",
                    timeout_ms=3500,
                    source="standard.interactive_learning",
                )
                dlg.accept()
                self._show_interactive_learning_stats()  # Reopen with updated stats
            train_btn.clicked.connect(train_now)
            button_layout.addWidget(train_btn)
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        dlg.exec()

    def _save_interactive_learning_model(self) -> None:
        """Save the interactive learning model to a file."""
        if not self._interactive_learning_enabled():
            return
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Interactive Learning Model",
            "",
            "Model Files (*.pkl);;All Files (*)",
        )
        
        if not path:
            return
        
        try:
            self._interactive_learning_model.save(path)
            self._status_success(
                f"Interactive learning model saved to {path}.",
                timeout_ms=3500,
                source="standard.interactive_learning",
            )
            QtWidgets.QMessageBox.information(
                self,
                "Model Saved",
                f"Interactive learning model saved successfully to:\n{path}",
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Save Failed",
                f"Failed to save model:\n{str(e)}",
            )

    def _load_interactive_learning_model(self) -> None:
        """Load an interactive learning model from a file."""
        if not self._interactive_learning_enabled():
            return
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Interactive Learning Model",
            "",
            "Model Files (*.pkl);;All Files (*)",
        )
        
        if not path:
            return
        
        try:
            loaded_model = InteractiveLearningModel.load(path)
            self._interactive_learning_model = loaded_model
            stats = loaded_model.get_statistics()
            self._status_success(
                f"Interactive learning model loaded: {stats['n_examples']} examples, "
                f"{'trained' if loaded_model.is_trained else 'not trained'}.",
                timeout_ms=3500,
                source="standard.interactive_learning",
            )
            QtWidgets.QMessageBox.information(
                self,
                "Model Loaded",
                f"Interactive learning model loaded successfully from:\n{path}\n\n"
                f"Training examples: {stats['n_examples']}\n"
                f"Status: {'Trained' if loaded_model.is_trained else 'Not trained'}",
            )
            # Refresh predictions with new model
            if self.primary_image is not None:
                self._request_ui_refresh("standard-actions")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Load Failed",
                f"Failed to load model:\n{str(e)}",
            )

    def _reset_interactive_learning_model(self) -> None:
        """Reset the interactive learning model (clear all training examples)."""
        if not self.controller.feature_enabled("interactive_learning_experimental", False):
            return

        if not hasattr(self, "_interactive_learning_model"):
            self._interactive_learning_model = InteractiveLearningModel()
            self._status_info(
                "Interactive learning model initialized.",
                timeout_ms=3000,
                source="standard.interactive_learning",
            )
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Reset Interactive Learning Model",
            "This will clear all training examples and reset the model.\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Create a new model with same config
            old_model = self._interactive_learning_model
            self._interactive_learning_model = InteractiveLearningModel(
                model_type=old_model.model_type,
                update_frequency=old_model.update_frequency,
                min_examples_to_train=old_model.min_examples_to_train,
                confidence_threshold=old_model.confidence_threshold,
            )
            self._status_info(
                "Interactive learning model reset.",
                timeout_ms=3000,
                source="standard.interactive_learning",
            )
            QtWidgets.QMessageBox.information(
                self,
                "Model Reset",
                "Interactive learning model has been reset.\n"
                "All training examples have been cleared.",
            )

    def _on_annotation_space_changed(self, value: str) -> None:
        """Switch annotation space between stack and projection contexts."""
        old_space = str(getattr(self.controller.session_state, "annotation_space", "stack")).strip().lower()
        space = str(value or "stack").strip().lower()
        if space not in ("stack", "projection"):
            space = "stack"
        self.controller.set_annotation_space_value(space)
        if old_space != space:
            self._mark_annotation_context_changed(
                f"annotation space changed ({old_space} -> {space})"
            )
        self._status_info(
            f"Annotation space: {space}.",
            timeout_ms=2500,
            source="standard.annotation_space",
        )
        self._refresh_assist_warmup_panel()
        self._update_status()

    def _on_assist_minima_changed(self, _value: int) -> None:
        """Update assist-level minimum label gates."""
        self.controller.set_assist_minima(
            min_total=int(self.assist_min_total_spin.value()),
            min_positive=int(self.assist_min_positive_spin.value()),
            min_negative=int(self.assist_min_negative_spin.value()),
            min_per_context=int(self.assist_min_context_spin.value()),
        )
        self._settings.setValue("assistMinTotalLabels", int(self.assist_min_total_spin.value()))
        self._settings.setValue(
            "assistMinPositiveLabels", int(self.assist_min_positive_spin.value())
        )
        self._settings.setValue(
            "assistMinNegativeLabels", int(self.assist_min_negative_spin.value())
        )
        self._settings.setValue(
            "assistMinLabelsPerContext", int(self.assist_min_context_spin.value())
        )
        self._status_info(
            "Assist minima updated.",
            timeout_ms=2500,
            source="standard.assist_minima",
        )
        self._refresh_assist_warmup_panel()
        self._update_status()

    def _on_qc_auto_show_changed(self, checked: bool) -> None:
        """Enable/disable automatically showing QC panel when issues are found."""
        self._settings.setValue("qcAutoShowOnIssues", bool(checked))
        self._status_info(
            "QC panel auto-show enabled."
            if bool(checked)
            else "QC panel auto-show disabled.",
            timeout_ms=2500,
            source="standard.qc_auto_show",
        )

    def _on_generation_space_changed(self, value: str) -> None:
        """Switch assist generation evidence between stack and projection space."""
        old_space = str(getattr(self.controller.session_state, "generation_space", "stack")).strip().lower()
        space = str(value or "stack").strip().lower()
        if space not in ("stack", "projection"):
            space = "stack"
        self.controller.set_generation_space_value(space)
        self._settings.setValue("assistGenerationSpace", space)
        if old_space != space:
            self._mark_annotation_context_changed(
                f"assist generation space changed ({old_space} -> {space})"
            )
        self._status_info(
            f"Assist generation space: {space}.",
            timeout_ms=2500,
            source="standard.generation_space",
        )
        self._refresh_assist_warmup_panel()
        self._update_status()

    def _on_disable_bulk_accept_when_stale_changed(self, checked: bool) -> None:
        """Persist stale accept guard policy for review/batch actions."""
        self._disable_bulk_accept_when_stale = bool(checked)
        self.controller.set_disable_bulk_accept_when_stale_value(bool(checked))
        self._settings.setValue("disableBulkAcceptWhenStale", bool(checked))
        self._status_info(
            "Stale accept guard enabled."
            if bool(checked)
            else "Stale accept guard disabled.",
            timeout_ms=2500,
            source="standard.stale_guard",
        )

    def _on_interactive_learning_experimental_changed(self, checked: bool) -> None:
        """Enable/disable the experimental interactive-learning sidecar."""
        enabled = bool(checked)
        self.controller.set_feature_flag("interactive_learning_experimental", enabled)
        self._settings.setValue("assistInteractiveLearningExperimental", enabled)
        if enabled and not hasattr(self, "_interactive_learning_model"):
            self._reset_interactive_learning_model()
        elif not enabled and hasattr(self, "_interactive_learning_model"):
            delattr(self, "_interactive_learning_model")
        self._status_info(
            "Experimental interactive learning enabled."
            if enabled
            else "Experimental interactive learning disabled.",
            timeout_ms=2500,
            source="standard.interactive_learning",
        )
        self._request_ui_refresh("standard-actions")

    def _interactive_learning_enabled(self) -> bool:
        """Return whether the experimental interactive-learning sidecar is active."""
        return bool(
            self.controller.feature_enabled("interactive_learning_experimental", False)
            and hasattr(self, "_interactive_learning_model")
        )

    def _ensure_suggestion_accept_allowed(
        self,
        suggestion: PointSuggestion | None,
        *,
        action_label: str,
        source: str,
    ) -> bool:
        """Enforce stale-suggestion accept protection for all single-item accept paths."""
        if suggestion is None:
            return False
        if not bool(getattr(self, "_disable_bulk_accept_when_stale", True)):
            return True
        freshness = self._suggestion_freshness_state(
            self.primary_image.id,
            suggestions=[suggestion],
        )
        if not freshness.get("is_stale", False):
            return True
        self._status_warning(
            f"{action_label} blocked: suggestion is stale. Regenerate or use the batch preview override.",
            timeout_ms=5000,
            source=source,
        )
        return False

    def _start_assist_warmup(self) -> None:
        """Guide early balanced accept/reject triage to bootstrap learned assist."""
        self._refresh_assist_warmup_panel()
        self._focus_current_uncertain_suggestion()
        visible = self._visible_suggestions_uncertain_first()
        if not visible:
            self._status_info(
                "Warmup: generate suggestions first.",
                timeout_ms=2500,
                source="standard.warmup",
            )
            return
        annotation_space = str(getattr(self.controller.session_state, "annotation_space", "stack"))
        context_key = self.controller._context_key(
            suggestion=visible[0],
            annotation_space=annotation_space,
        )
        b = self.controller.assist_need_breakdown(
            annotation_space=annotation_space,
            context_key=context_key,
        )
        self._status_info(
            "Warmup mode: use N/P to move, A accept, R reject. "
            f"Need +{b['need_pos']} positives, +{b['need_neg']} negatives, +{b['need_context']} context labels.",
            timeout_ms=5000,
            source="standard.warmup",
        )

    def _start_timed_annotation_session(self, assisted: bool) -> None:
        """Start timed benchmark session for throughput metrics."""
        self._timed_session_active = True
        self._timed_session_assisted = bool(assisted)
        self._timed_session_started_at = time.time()
        self._timed_session_accepts = 0
        self._timed_session_rejects = 0
        self._timed_session_points = 0
        self._timed_session_correction_time = 0.0
        mode = "with assist" if assisted else "without assist"
        self._status_info(
            f"Timed annotation session started ({mode}).",
            timeout_ms=3000,
            source="standard.timed_session",
        )

    def _stop_timed_annotation_session(self) -> None:
        """Stop timed benchmark session and report metrics."""
        if not bool(getattr(self, "_timed_session_active", False)):
            self._status_info(
                "No active timed session.",
                timeout_ms=2500,
                source="standard.timed_session",
            )
            return
        elapsed = max(1e-6, time.time() - float(getattr(self, "_timed_session_started_at", time.time())))
        points = int(getattr(self, "_timed_session_points", 0))
        accepts = int(getattr(self, "_timed_session_accepts", 0))
        rejects = int(getattr(self, "_timed_session_rejects", 0))
        ppm = 60.0 * float(points) / elapsed
        correction = float(getattr(self, "_timed_session_correction_time", 0.0))
        correction_avg = correction / max(1, accepts + rejects)
        msg = (
            f"Duration: {elapsed:.1f}s\n"
            f"Points/min: {ppm:.2f}\n"
            f"Acceptance rate: {(accepts / max(1, accepts + rejects)):.3f}\n"
            f"Avg correction time: {correction_avg:.2f}s\n"
        )
        QtWidgets.QMessageBox.information(self, "Timed Annotation Session", msg)
        self.controller.append_audit_event(
            "timed_annotation_session_completed",
            assisted=bool(getattr(self, "_timed_session_assisted", True)),
            duration_s=elapsed,
            points=points,
            points_per_min=ppm,
            acceptance_rate=(accepts / max(1, accepts + rejects)),
            correction_time_avg_s=correction_avg,
        )
        self._timed_session_active = False

    def _selected_table_keypoints(self) -> list:
        """Return currently selected keypoints from annotation table."""
        if getattr(self, "annot_table", None) is None or self.annot_table.selectionModel() is None:
            return []
        rows = sorted({idx.row() for idx in self.annot_table.selectionModel().selectedRows()})
        selected = []
        for row in rows:
            kp = self._keypoint_for_table_row(row) if hasattr(self, "_keypoint_for_table_row") else None
            if kp is not None:
                selected.append(kp)
        return selected

    def _set_selected_review_state(self, state: str) -> None:
        """Set review state on selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._status_info(
                "Select one or more annotations first.",
                timeout_ms=2500,
                source="standard.annotation_selection",
            )
            return
        updated = 0
        now_ts = time.time()
        for kp in selected:
            new_meta = dict(kp.meta)
            new_meta["review_state"] = state
            new_meta["reviewer"] = self.controller.session_state.current_user
            new_meta["reviewed_at"] = now_ts
            replacement = type(kp)(
                image_id=kp.image_id,
                image_name=kp.image_name,
                t=kp.t,
                z=kp.z,
                y=kp.y,
                x=kp.x,
                label=kp.label,
                annotation_id=kp.annotation_id,
                image_key=kp.image_key,
                source=kp.source,
                meta=new_meta,
                modality_idx=kp.modality_idx,
            )
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                updated += 1
        if updated:
            self.controller.append_audit_event(
                "review_state_updated", state=state, count=updated
            )
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Updated review state for {updated} annotation(s).",
            timeout_ms=3000,
            source="standard.review_state",
        )

    def _assign_selected_annotations_dialog(self) -> None:
        """Set assignee for selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._status_info(
                "Select one or more annotations first.",
                timeout_ms=2500,
                source="standard.annotation_selection",
            )
            return
        assignee, ok = QtWidgets.QInputDialog.getText(
            self,
            "Assign Selected Annotations",
            "Assignee:",
            text=self.controller.session_state.current_user,
        )
        if not ok:
            return
        assignee = assignee.strip()
        updated = 0
        for kp in selected:
            new_meta = dict(kp.meta)
            new_meta["assignee"] = assignee
            replacement = type(kp)(
                image_id=kp.image_id,
                image_name=kp.image_name,
                t=kp.t,
                z=kp.z,
                y=kp.y,
                x=kp.x,
                label=kp.label,
                annotation_id=kp.annotation_id,
                image_key=kp.image_key,
                source=kp.source,
                meta=new_meta,
                modality_idx=kp.modality_idx,
            )
            if self.controller.update_annotation(kp.image_id, kp, replacement):
                updated += 1
        if updated:
            self.controller.append_audit_event(
                "assignee_updated", assignee=assignee, count=updated
            )
            self._refresh_table()
            self._request_ui_refresh("standard-actions")
        self._status_success(
            f"Assigned {updated} annotation(s) to '{assignee}'.",
            timeout_ms=3000,
            source="standard.assignee",
        )

    def _set_current_user_dialog(self) -> None:
        """Set current local user identity for review/audit actions."""
        current = self.controller.session_state.current_user
        user, ok = QtWidgets.QInputDialog.getText(self, "Set Current User", "User:", text=current)
        if not ok:
            return
        user = user.strip() or "local_user"
        self.controller.set_current_user_value(user)
        self.controller.append_audit_event("current_user_changed", user=user)
        self._status_info(
            f"Current user set to '{user}'.",
            timeout_ms=2500,
            source="standard.current_user",
        )

    def _set_review_queue_filter(self, mode: str) -> None:
        """Switch annotation table queue filter mode."""
        self._review_queue_filter = str(mode)
        action_map = {
            "all": getattr(self, "queue_all_act", None),
            "my_queue": getattr(self, "queue_my_act", None),
            "needs_review": getattr(self, "queue_needs_review_act", None),
            "blocked_qc": getattr(self, "queue_blocked_qc_act", None),
        }
        for key, action in action_map.items():
            if action is None:
                continue
            action.blockSignals(True)
            action.setChecked(key == self._review_queue_filter)
            action.blockSignals(False)
        self._refresh_table()
        self._refresh_review_queue_panel()
        self._request_ui_refresh("standard-actions")
        self._status_info(
            f"Review queue: {self._review_queue_filter}.",
            timeout_ms=2500,
            source="standard.review_queue",
        )

    def _show_profile_dialog(self) -> None:
        """Open a dialog showing line profiles (vertical, horizontal, diagonals) raw vs corrected."""
        if self.primary_image.array is None:
            return
        data = self._apply_crop(self._slice_data(self.primary_image))
        if data.ndim > 2:
            data = np.mean(data, axis=-1)
        h, w = data.shape[:2]
        cy, cx = h // 2, w // 2
        vertical = data[:, cx]
        horizontal = data[cy, :]
        diag1 = np.diag(data)
        diag2 = np.diag(np.fliplr(data))

        def _correct(arr: np.ndarray) -> np.ndarray:
            if self.illum_corr_chk.isChecked():
                arr = arr - arr.min()
            if arr.max() > 0:
                arr = arr / arr.max()
            return arr

        fig, axes = plt.subplots(2, 2, figsize=(10, 6))
        axes = axes.ravel()
        for ax, arr, title in [
            (axes[0], vertical, "Vertical"),
            (axes[1], horizontal, "Horizontal"),
            (axes[2], diag1, "Diag TL-BR"),
            (axes[3], diag2, "Diag TR-BL"),
        ]:
            ax.plot(arr, label="raw")
            ax.plot(_correct(arr), label="corrected")
            ax.set_title(title)
            ax.legend()
            ax.set_xlabel("Pixel")
            ax.set_ylabel("Intensity")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Line profiles")
        layout = QtWidgets.QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.resize(900, 600)
        dlg.show()
        dlg.exec()

    def _show_bleach_dialog(self) -> None:
        """Open a dialog showing ROI mean over T with exponential fit."""
        if self.primary_image.array is None:
            return
        self.recorder.record("bleach_fit", {"image": self.primary_image.name})
        arr = self.primary_image.array
        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        crop_rect = self.crop_rect
        img_path = pathlib.Path(self.primary_image.path)
        job_gen = self._job_generation

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Computing…", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Bleaching analysis")
        layout = QtWidgets.QVBoxLayout(dlg)
        status_label = QtWidgets.QLabel("Computing ROI means…")
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        status_row = QtWidgets.QHBoxLayout()
        status_row.addWidget(status_label)
        status_row.addWidget(cancel_btn)
        layout.addLayout(status_row)
        layout.addWidget(progress_bar)

        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        def _job(progress, cancel_token):
            def _apply_crop_local(frame: np.ndarray) -> np.ndarray:
                x, y, w, h = crop_rect
                if w <= 0 or h <= 0:
                    return frame
                x0 = int(max(0, x))
                y0 = int(max(0, y))
                x1 = int(min(frame.shape[1], x + w))
                y1 = int(min(frame.shape[0], y + h))
                return frame[y0:y1, x0:x1]

            def _roi_mask_local(shape: Tuple[int, ...]) -> np.ndarray:
                if len(shape) < 2:
                    raise ValueError(f"Invalid frame shape for ROI mask: {shape}")
                h, w = int(shape[0]), int(shape[1])
                yy = np.arange(h)[:, None]
                xx = np.arange(w)[None, :]
                rx, ry, rw, rh = roi_rect
                if roi_shape == "circle":
                    cx, cy = rx + rw / 2, ry + rh / 2
                    r = min(rw, rh) / 2
                    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
                return (rx <= xx) & (xx <= rx + rw) & (ry <= yy) & (yy <= ry + rh)

            means = []
            total = max(1, arr.shape[0])
            for t in range(arr.shape[0]):
                if cancel_token.is_cancelled():
                    return None
                frame = arr[t, 0, :, :]
                frame_cropped = _apply_crop_local(frame)
                roi_mask = _roi_mask_local(frame_cropped.shape)
                vals = frame_cropped[roi_mask]
                means.append(float(vals.mean()) if vals.size else float("nan"))
                pct = int((t + 1) / total * 80)
                progress(pct, f"Computing means… {t+1}/{total}")
            if cancel_token.is_cancelled():
                return None
            progress(90, "Fitting…")
            try:
                xs, fit, eq = fit_bleach_curve(means)
            except Exception:
                xs = np.arange(len(means))
                fit = None
                eq = "fit failed"
            progress(100, "Done")
            return (means, xs, fit, eq, img_path, job_gen)

        def _on_progress(value: int, msg: str) -> None:
            if not dlg.isVisible():
                return
            progress_bar.setValue(value)
            if msg:
                status_label.setText(msg)

        def _on_result(result) -> None:
            if not dlg.isVisible():
                return
            if result is None:
                return
            means, xs, fit, eq, path, gen = result
            if gen != self._job_generation:
                return
            if pathlib.Path(self.primary_image.path) != path:
                return
            ax.clear()
            ax.plot(xs, means, "o-", label="ROI mean")
            if fit is not None:
                ax.plot(xs, fit, "--", label=eq)
            ax.set_xlabel("Frame")
            ax.set_ylabel("Mean intensity")
            ax.set_title("ROI mean vs frame")
            ax.legend()
            canvas.draw_idle()
            status_label.setText("Done.")

        def _on_error(err: str) -> None:
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Failed. See Logs.")
            self._append_log(f"[JOB] Bleaching analysis error\n{err}")

        token = self._submit_analysis_job(
            _job,
            name="Bleaching analysis",
            on_progress=_on_progress,
            on_result=_on_result,
            on_error=_on_error,
        )

        def _cancel() -> None:
            token.cancel()
            status_label.setText("Cancelled.")

        cancel_btn.clicked.connect(_cancel)
        dlg.finished.connect(lambda _result: token.cancel())
        dlg.resize(800, 520)
        dlg.show()
        dlg.exec()

    def _show_table_dialog(self) -> None:
        """Open a dialog with a table of file names and ROI mean; allow CSV export."""
        # Prefer last opened folder; otherwise use currently loaded images.
        candidates: List[pathlib.Path] = []
        if self._last_folder and self._last_folder.exists():
            candidates = sorted(
                [
                    p
                    for p in self._last_folder.iterdir()
                    if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")
                ]
            )
        if not candidates:
            candidates = [img.path for img in self.images]
        if not candidates:
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("ROI mean table")
        layout = QtWidgets.QVBoxLayout(dlg)
        status_label = QtWidgets.QLabel("Computing ROI means…")
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        status_row = QtWidgets.QHBoxLayout()
        status_row.addWidget(status_label)
        status_row.addWidget(cancel_btn)
        layout.addLayout(status_row)
        layout.addWidget(progress_bar)

        table = QtWidgets.QTableWidget(len(candidates), 2)
        table.setHorizontalHeaderLabels(["File", "ROI mean"])
        for i, p in enumerate(candidates):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(p.name))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem("…"))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        export_btn = QtWidgets.QPushButton("Export CSV")
        layout.addWidget(export_btn)

        rows: List[dict] = [{"file": p.name, "roi_mean": float("nan")} for p in candidates]

        def _export() -> None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export ROI means",
                str(pathlib.Path.cwd() / "roi_means.csv"),
                "CSV Files (*.csv)",
            )
            if path:
                pd.DataFrame(rows).to_csv(path, index=False)

        export_btn.clicked.connect(_export)
        export_btn.setEnabled(False)

        roi_rect = self.roi_rect
        roi_shape = self.roi_shape
        crop_rect = self.crop_rect
        job_gen = self._job_generation

        def _job(progress, cancel_token):
            total = max(1, len(candidates))
            for idx, path in enumerate(candidates):
                if cancel_token.is_cancelled():
                    return None
                roi_mean = compute_roi_mean_for_path(str(path), roi_rect, roi_shape, crop_rect)
                pct = int((idx + 1) / total * 100)
                progress(pct, f"row:{idx}:{roi_mean}")
            return "done"

        def _on_progress(value: int, msg: str) -> None:
            if not dlg.isVisible():
                return
            progress_bar.setValue(value)
            if msg.startswith("row:"):
                try:
                    _, idx_s, mean_s = msg.split(":", 2)
                    idx = int(idx_s)
                    mean_val = float(mean_s)
                except ValueError:
                    return
                if 0 <= idx < len(rows):
                    rows[idx]["roi_mean"] = mean_val
                    table.setItem(idx, 1, QtWidgets.QTableWidgetItem(f"{mean_val:.3f}"))
            status_label.setText("Computing ROI means…")

        def _on_result(_result) -> None:
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Done.")
            export_btn.setEnabled(True)

        def _on_error(err: str) -> None:
            if not dlg.isVisible():
                return
            if job_gen != self._job_generation:
                return
            status_label.setText("Failed. See Logs.")
            self._append_log(f"[JOB] ROI mean table error\n{err}")

        token = self._submit_analysis_job(
            _job,
            name="ROI mean table",
            on_progress=_on_progress,
            on_result=_on_result,
            on_error=_on_error,
        )

        def _cancel() -> None:
            token.cancel()
            status_label.setText("Cancelled.")

        cancel_btn.clicked.connect(_cancel)
        dlg.finished.connect(lambda _result: token.cancel())
        dlg.resize(500, 300)
        dlg.show()
        dlg.exec()

    def _compute_roi_mean_for_path(self, path: pathlib.Path) -> float:
        """Compute ROI mean for the given TIFF path with minimal memory use."""
        try:
            return compute_roi_mean_for_path(
                str(path), self.roi_rect, self.roi_shape, self.crop_rect
            )
        except Exception:
            return float("nan")

    def _clear_cache(self) -> None:
        """Clear all lazy image data (arrays + projections) and refresh the view."""
        self.stop_playback_t()
        cleared = 0
        self.proj_cache.clear()
        for img in self.images:
            if img.array is not None or img.mean_proj is not None or img.std_proj is not None:
                cleared += 1
            self._evict_image_cache(img)
        gc.collect()
        debug_log(f"Cleared cached data for {cleared} images")
        self._status_success(
            f"Cleared cached image data for {cleared} images.",
            timeout_ms=3000,
            source="standard.clear_cache",
        )
        # Will lazily reload the active images after purge.
        self._request_ui_refresh("standard-actions")

    def _show_smlm_panel(self) -> None:
        """Show the SMLM parameter panel."""
        if self.dock_smlm is not None:
            self.set_panel_visible("smlm", True, source="advanced_panel")
            self.dock_smlm.raise_()
            if getattr(self, "smlm_panel", None) is not None:
                self.smlm_panel.tabs.setCurrentIndex(0)

    def _show_deepstorm_panel(self) -> None:
        """Show the Deep-STORM parameter panel."""
        if getattr(self, "dock_smlm", None) is not None:
            self.set_panel_visible("smlm", True, source="advanced_panel")
            self.dock_smlm.raise_()
        if getattr(self, "smlm_panel", None) is not None:
            self.smlm_panel.tabs.setCurrentIndex(1)

    def _show_threshold_panel(self) -> None:
        """Show the Threshold panel."""
        if getattr(self, "dock_threshold", None) is not None:
            self.set_panel_visible("threshold", True, source="advanced_panel")
            self.dock_threshold.raise_()

    def _show_analyze_particles_panel(self) -> None:
        """Show the Analyze Particles panel."""
        if getattr(self, "dock_particles", None) is not None:
            self.set_panel_visible("particles", True, source="advanced_panel")
            self.dock_particles.raise_()
