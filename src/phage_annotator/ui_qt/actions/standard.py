"""Menu and dialog actions for the GUI."""

from __future__ import annotations

import gc
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
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import PointSuggestion
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
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


class ActionsMixin(
    NavigationActionsMixin,
    ExportActionsMixin,
    DockActionsMixin,
    QCActionsMixin,
):
    """Mixin for File/View/Analyze actions and dialogs."""

    def _current_annotation_write_context(self) -> tuple[str, str]:
        """Return normalized write context key (annotation_space, annotate_target)."""
        space = str(getattr(self.controller.session_state, "annotation_space", "stack")).strip().lower()
        if space not in ("stack", "projection"):
            space = "stack"
        target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        if target not in ("frame", "mean", "support"):
            target = "frame"
        return (space, target)

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
            self._set_status("Write cancelled: context confirmation required.")
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
                    self.fov_list.addItem(meta.name)
                    self.primary_combo.addItem(meta.name)
                    self.support_combo.addItem(meta.name)
                    self.roi_manager.rois_by_image[meta.id] = []
                # Build annotation index (lightweight) and update availability
                try:
                    self.controller.build_annotation_index(files[0].parent)
                except Exception:
                    pass
                self._refresh_annotation_availability()
                self._refresh_roi_manager()
                self._refresh_metadata_dock(self.primary_image.id)
                self._refresh_image()
                self._maybe_autoload_annotations(self.primary_image.id)

            self.jobs.submit(
                _worker,
                name="Open folder",
                on_result=_on_result,
                timeout_sec=300.0,
                retries=2,
                retry_delay_sec=1.0,
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
        )
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._refresh_image()

    def _load_annotations_multi(self) -> None:
        cal = self._get_calibration_state(self.primary_image.id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self.controller.load_annotations(self, self.primary_image.id, pixel_size_nm=pixel_size_nm)
        meta = self.controller.latest_annotation_meta(self.primary_image.id)
        if meta:
            self._handle_annotation_metadata(self.primary_image.id, meta)
        self._mark_dirty()
        self._refresh_image()

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
            self.controller.annotations_changed.emit()
            self._refresh_image()

        self.jobs.submit(
            _worker,
            name="Load all annotations",
            on_result=_on_result,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
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
        self.settings_advanced_container.setVisible(
            not self.settings_advanced_container.isVisible()
        )

    def _on_link_zoom_menu(self) -> None:
        self.link_zoom = self.link_zoom_act.isChecked()
        if not self.link_zoom:
            # reset last linked to avoid forcing 0-1 ranges
            self._last_zoom_linked = None
        if getattr(self, "sync_zoom_chk", None) is not None:
            self.sync_zoom_chk.blockSignals(True)
            self.sync_zoom_chk.setChecked(self.link_zoom)
            self.sync_zoom_chk.blockSignals(False)
        if getattr(self, "view_sync", None) is not None:
            self._apply_view_sync_selection()
        self._refresh_image()

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
                "- Use right-dock tabs: Annotation Table, Review Queue, Why This Suggestion?\n"
                "- Use Layouts button near playback for quick presets."
            ),
        )

    def _visible_suggestions(self) -> list[PointSuggestion]:
        """Return suggestions visible on active image and T/Z slice."""
        image_id = self.primary_image.id
        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        min_score = float(getattr(self, "_suggestion_score_threshold", 0.0))
        return [
            s
            for s in self.suggestions.get(image_id, [])
            if int(s.t) in (t_idx, -1) and int(s.z) in (z_idx, -1)
            and float(getattr(s, "score", getattr(s, "confidence", 0.0))) >= min_score
        ]

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
        return out

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
                scale_sigma=seed.scale_sigma,
                psf_radius=seed.psf_radius,
                roi_id=seed.roi_id,
                score_components=dict(seed.score_components),
                status=seed.status,
                meta=dict(seed.meta),
            )
            combined.meta["features"] = bundle
            combined.meta["consensus_votes"] = int(votes)
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
        roi_id = "active_roi" if self.roi_shape != "none" else None

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
            )
            for row in rows:
                row.source_modality = modality_id
                row.meta.setdefault("features", {})
                row.meta["features"][modality_id] = dict(row.score_components)
            return rows

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
            filtered = []
            for suggestion in seeds:
                features = dict(suggestion.meta.get("features", {}))
                keep = True
                for modality_id, threshold in dict(rule.positive_modalities).items():
                    peak = float(dict(features.get(modality_id, {})).get("peak", -np.inf))
                    if peak < float(threshold):
                        keep = False
                        break
                if keep:
                    for modality_id, threshold in dict(rule.negative_modalities).items():
                        peak = float(dict(features.get(modality_id, {})).get("peak", np.inf))
                        if peak > float(threshold):
                            keep = False
                            break
                if keep:
                    filtered.append(suggestion)
            return filtered

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
        self._set_status(f"Loaded suggestion rule config: {pathlib.Path(path).name}")

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
        ranked.sort(key=lambda s: float(getattr(s, "score", 0.0)), reverse=True)
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
            nearest = float("inf")
            for kp in anns:
                if int(kp.t) not in (int(suggestion.t), -1):
                    continue
                if int(kp.z) not in (int(suggestion.z), -1):
                    continue
                dx = float(kp.x) - x
                dy = float(kp.y) - y
                dist = float((dx * dx + dy * dy) ** 0.5)
                if dist < nearest:
                    nearest = dist
            if not np.isfinite(nearest):
                nearest = float(max(h, w))
            suggestion.meta["distance_to_nearest_accepted"] = float(nearest)
            suggestion.meta["border_proximity"] = float(max(0.0, min_border))
            suggestion.meta["derived_from_accepted_area"] = bool(
                nearest <= float(getattr(suggestion, "psf_radius", 6.0))
            )

    def _select_suggestion_strategy_dialog(self) -> None:
        """Choose proposal strategy used by Suggest actions."""
        strategies = self._candidate_suggestion_strategies()
        current = str(getattr(self, "_suggestion_strategy", "raw"))
        idx = strategies.index(current) if current in strategies else 0
        selected, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Suggest Points Using",
            "Strategy:",
            strategies,
            idx,
            False,
        )
        if not ok:
            return
        self._suggestion_strategy = str(selected)
        self.controller.session_state.suggestion_strategy = self._suggestion_strategy
        self._set_status(f"Suggestion strategy: {self._suggestion_strategy}.")
        self._refresh_assist_warmup_panel()

    def _set_suggestion_score_threshold_dialog(self) -> None:
        """Set display threshold for proposal score."""
        current = float(getattr(self, "_suggestion_score_threshold", 0.0))
        value, ok = QtWidgets.QInputDialog.getDouble(
            self,
            "Show Suggestions With Score >= X",
            "Score threshold (0-1):",
            current,
            0.0,
            1.0,
            2,
        )
        if not ok:
            return
        self._suggestion_score_threshold = float(value)
        self.controller.session_state.suggestion_score_threshold = self._suggestion_score_threshold
        self._refresh_image()
        self._set_status(
            f"Show suggestions with confidence (calibrated p_accept) >= {self._suggestion_score_threshold:.2f}; generator score is heuristic."
        )
        self._refresh_assist_warmup_panel()

    def _suggest_points_current_slice(self) -> None:
        """Generate model suggestions for the current slice."""
        image_data = self._slice_data(self.primary_image)
        if image_data is None:
            return
        image_id = self.primary_image.id
        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        generated = self._gating_strategy_candidates(
            image=self.primary_image,
            t_idx=t_idx,
            z_idx=z_idx,
            strategy=str(getattr(self, "_suggestion_strategy", "current_view")),
            label=str(self.current_label),
        )
        generated = self._rank_and_calibrate_suggestions(generated)
        self._enrich_suggestions_for_training(generated, image_data)
        generated_at = float(time.time())
        for suggestion in generated:
            suggestion.meta["generated_at_ts"] = generated_at
        self.suggestions.setdefault(image_id, []).extend(generated)
        self.controller.session_state.suggestion_history.setdefault(image_id, []).extend(
            list(generated)
        )
        self.suggestions[image_id].sort(key=lambda s: float(s.score), reverse=True)
        self.controller.update_suggestion_metrics(generated=len(generated))
        self.controller.append_audit_event(
            "suggestions_generated",
            image_id=image_id,
            model=getattr(getattr(self, "_suggestion_model", None), "model_name", "unknown"),
            count=len(generated),
            strategy=str(getattr(self, "_suggestion_strategy", "current_view")),
        )
        ctx_key = self.controller._context_key(
            suggestion=(generated[0] if generated else PointSuggestion(image_id, self.primary_image.name, t_idx, z_idx, 0, 0, 0.0)),
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        _, assist_txt = self.controller.assist_status(
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
            context_key=ctx_key,
        )
        self._suggestion_cursor = 0
        self._refresh_image()
        self._set_status(f"Generated {len(generated)} ranked suggestion(s). {assist_txt}")
        self._refresh_assist_warmup_panel()

    def _suggest_points_current_image(self) -> None:
        """Generate suggestions for all T/Z slices in the active image."""
        image = self.primary_image
        if image.array is None:
            return
        image_id = image.id
        total = 0
        t_size = int(image.array.shape[0])
        z_size = int(image.array.shape[1])
        for t_idx in range(t_size):
            for z_idx in range(z_size):
                slice_data = self._slice_data(image, t_override=t_idx, z_override=z_idx)
                generated = self._gating_strategy_candidates(
                    image=image,
                    t_idx=t_idx,
                    z_idx=z_idx,
                    strategy=str(getattr(self, "_suggestion_strategy", "current_view")),
                    label=str(self.current_label),
                )
                generated = self._rank_and_calibrate_suggestions(generated)
                self._enrich_suggestions_for_training(generated, slice_data)
                generated_at = float(time.time())
                for suggestion in generated:
                    suggestion.meta["generated_at_ts"] = generated_at
                total += len(generated)
                self.suggestions.setdefault(image_id, []).extend(generated)
                self.controller.session_state.suggestion_history.setdefault(image_id, []).extend(
                    list(generated)
                )
        self.suggestions.setdefault(image_id, []).sort(key=lambda s: float(s.score), reverse=True)
        self.controller.update_suggestion_metrics(generated=total)
        self.controller.append_audit_event(
            "suggestions_generated",
            image_id=image_id,
            model=getattr(getattr(self, "_suggestion_model", None), "model_name", "unknown"),
            count=total,
            scope="all_slices",
            strategy=str(getattr(self, "_suggestion_strategy", "current_view")),
        )
        self._suggestion_cursor = 0
        self._refresh_image()
        self._set_status(f"Generated {total} ranked suggestion(s) for full image.")
        self._refresh_assist_warmup_panel()

    def _accept_visible_suggestions(self) -> None:
        """Accept all visible suggestions via undoable commands."""
        if not self._ensure_annotation_write_context_confirmed("Accept suggestions"):
            return
        visible = self._visible_suggestions()
        accepted = 0
        for suggestion in list(visible):
            cmd = AcceptSuggestionCommand(
                self.controller, self.primary_image.id, suggestion.suggestion_id
            )
            if self.controller.execute_view_command(cmd):
                accepted += 1
                self.controller.update_suggestion_metrics(correction_distance=0.0)
                if bool(getattr(self, "_timed_session_active", False)):
                    self._timed_session_accepts = int(getattr(self, "_timed_session_accepts", 0)) + 1
                    self._timed_session_points = int(getattr(self, "_timed_session_points", 0)) + 1
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if accepted:
            self._refresh_table()
            self._refresh_image()
            self._schedule_qc_validation(self.primary_image.id)
        self._set_status(f"Accepted {accepted} suggestion(s).")
        self._refresh_assist_warmup_panel()

    def _accept_high_confidence_suggestions(self) -> None:
        """Accept all visible green suggestions (calibrated p_accept >= 0.75)."""
        if not self._ensure_annotation_write_context_confirmed("Accept high-confidence suggestions"):
            return
        visible = self._visible_suggestions()
        candidates = [
            s
            for s in visible
            if bool(dict(getattr(s, "meta", {}) or {}).get("confidence_available", False))
            and float(dict(getattr(s, "meta", {}) or {}).get("p_accept", 0.0)) >= 0.75
        ]
        accepted = 0
        for suggestion in list(candidates):
            cmd = AcceptSuggestionCommand(
                self.controller, self.primary_image.id, suggestion.suggestion_id
            )
            if self.controller.execute_view_command(cmd):
                accepted += 1
                self.controller.update_suggestion_metrics(correction_distance=0.0)
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if accepted:
            self._refresh_table()
            self._refresh_image()
            self._schedule_qc_validation(self.primary_image.id)
        self._set_status(f"Accepted {accepted} high-confidence suggestion(s).")
        self._refresh_assist_warmup_panel()

    def _reject_visible_suggestions(self) -> None:
        """Reject all visible suggestions via undoable commands."""
        visible = self._visible_suggestions()
        reason_key = "unspecified"
        rejected = 0
        for suggestion in list(visible):
            cmd = RejectSuggestionCommand(
                self.controller, self.primary_image.id, suggestion.suggestion_id
            )
            if self.controller.execute_view_command(cmd):
                rejected += 1
                self.controller.update_suggestion_metrics(**{f"reject_reason::{reason_key}": 1})
                if bool(getattr(self, "_timed_session_active", False)):
                    self._timed_session_rejects = int(getattr(self, "_timed_session_rejects", 0)) + 1
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if rejected:
            self._refresh_image()
            self.controller.append_audit_event(
                "suggestions_rejected",
                image_id=self.primary_image.id,
                count=rejected,
                reason=reason_key,
            )
        self._set_status(f"Rejected {rejected} suggestion(s).")
        self._refresh_assist_warmup_panel()

    def _accept_suggestions_in_roi(self) -> None:
        """Accept visible suggestions that are currently inside ROI."""
        visible = self._visible_suggestions()
        candidates = [s for s in visible if self._point_in_roi(float(s.x), float(s.y))]
        accepted = 0
        for suggestion in list(candidates):
            cmd = AcceptSuggestionCommand(
                self.controller, self.primary_image.id, suggestion.suggestion_id
            )
            if self.controller.execute_view_command(cmd):
                accepted += 1
                self.controller.update_suggestion_metrics(correction_distance=0.0)
                if bool(getattr(self, "_timed_session_active", False)):
                    self._timed_session_accepts = int(getattr(self, "_timed_session_accepts", 0)) + 1
                    self._timed_session_points = int(getattr(self, "_timed_session_points", 0)) + 1
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        if accepted:
            self._refresh_table()
            self._refresh_image()
            self._schedule_qc_validation(self.primary_image.id)
            self.controller.append_audit_event(
                "suggestions_accepted_in_roi",
                image_id=self.primary_image.id,
                count=accepted,
            )
        self._set_status(f"Accepted {accepted} suggestion(s) in ROI.")
        self._refresh_assist_warmup_panel()

    def _clear_suggestions_current_image(self) -> None:
        """Clear all pending suggestions for active image."""
        cmd = ClearSuggestionsCommand(self.controller, self.primary_image.id)
        if not self.controller.execute_view_command(cmd):
            self._set_status("No suggestions to clear.")
            return
        self.undo_act.setEnabled(self.controller.can_undo())
        self.redo_act.setEnabled(self.controller.can_redo())
        self._refresh_image()
        self._set_status("Cleared suggestions.")
        self._refresh_assist_warmup_panel()

    def _batch_correct_suggestions_dialog(self) -> None:
        """Apply a constant (dx, dy) correction to top-N uncertain suggestions."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions to batch-correct.")
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
            self._set_status("No visible suggestions to batch-correct.")
            return
        rows = list(ranked[: max(0, int(count))])
        if not rows:
            self._set_status("No suggestions selected for batch correction.")
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
        self._refresh_image()
        self._refresh_assist_warmup_panel()
        self._set_status(
            f"Batch-corrected {moved} suggestion(s) with dx={dx:.2f}, dy={dy:.2f}."
        )

    def _apply_review_queue_offset(self, count: int, dx: float, dy: float) -> None:
        """Apply inline review-queue XY offset controls without opening a modal."""
        self._apply_batch_suggestion_offset(count=int(count), dx=float(dx), dy=float(dy))

    def _propagate_suggestions_remaining_dialog(self) -> None:
        """Generate suggestions in remaining T/Z slices as a background task."""
        image = self.primary_image
        arr = getattr(image, "array", None)
        if arr is None or getattr(arr, "ndim", 0) < 4:
            self._set_status("No stack loaded for propagation.")
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
            self._set_status("No remaining slices to propagate.")
            return

        image_id = int(image.id)
        image_name = str(image.name)
        label = str(self.current_label)
        strategy = str(getattr(self, "_suggestion_strategy", "current_view"))

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
                )
                out.extend(generated)
                progress(int((idx + 1) / total * 100), f"{idx + 1}/{total} slices")
            return out

        def _on_result(result):
            if result is None:
                self._set_status("Suggestion propagation cancelled.")
                return
            generated = list(result)
            for suggestion in generated:
                frame = np.asarray(arr[int(suggestion.t), int(suggestion.z), :, :], dtype=np.float32)
                self._enrich_suggestions_for_training([suggestion], frame)
            generated = self._rank_and_calibrate_suggestions(generated)
            generated_at = float(time.time())
            for suggestion in generated:
                suggestion.meta["generated_at_ts"] = generated_at
            self.suggestions.setdefault(image_id, []).extend(generated)
            self.controller.session_state.suggestion_history.setdefault(image_id, []).extend(
                list(generated)
            )
            self.suggestions[image_id].sort(key=lambda s: float(s.score), reverse=True)
            self.controller.update_suggestion_metrics(generated=len(generated))
            self.controller.append_audit_event(
                "suggestions_propagated_remaining",
                image_id=image_id,
                count=len(generated),
                mode=str(mode_key),
                strategy=strategy,
            )
            if generated:
                first = generated[0]
                self.t_slider.setValue(max(self.t_slider.minimum(), min(int(first.t), self.t_slider.maximum())))
                self.z_slider.setValue(max(self.z_slider.minimum(), min(int(first.z), self.z_slider.maximum())))
            self._refresh_image()
            self._refresh_assist_warmup_panel()
            self._set_status(f"Propagated {len(generated)} suggestions across remaining slices.")

        self._submit_analysis_job(
            _job,
            name="Propagate suggestions",
            on_result=_on_result,
        )

    def _toggle_suggestions_overlay(self, checked: bool) -> None:
        """Toggle suggestion overlay rendering."""
        self._show_suggestion_overlay = bool(checked)
        self._refresh_image()

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

    def _review_queue_progress_counts(self) -> tuple[int, int]:
        """Return (processed, total) counts for current image and T/Z context."""
        image_id = self.primary_image.id
        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        pending = self._visible_suggestions_uncertain_first()
        history = list(
            getattr(self.controller.session_state, "suggestion_history", {}).get(image_id, [])
        )
        processed = 0
        for row in history:
            if int(getattr(row, "t", -2)) not in (t_idx, -1):
                continue
            if int(getattr(row, "z", -2)) not in (z_idx, -1):
                continue
            status = str(getattr(row, "status", ""))
            if status in ("accepted", "rejected"):
                processed += 1
        total = int(processed + len(pending))
        return processed, total

    def _refresh_review_queue_panel(self) -> None:
        """Refresh right-dock assisted review queue details and progress."""
        panel = getattr(self, "review_queue_panel", None)
        if panel is None:
            self._refresh_suggestion_explain_panel(None)
            return
        t_idx = int(self.t_slider.value())
        z_idx = int(self.z_slider.value())
        ranked = self._visible_suggestions_uncertain_first()
        panel.header_lbl.setText(f"Review Queue - T={t_idx + 1} Z={z_idx + 1}")
        panel.remaining_lbl.setText(f"Uncertain remaining: {len(ranked)}")
        processed, total = self._review_queue_progress_counts()
        panel.progress_lbl.setText(f"Progress: {processed} / {total}")
        pct = int(round(100.0 * float(processed) / max(1, float(total)))) if total > 0 else 0
        panel.progress_bar.setValue(max(0, min(100, pct)))
        assist_state = self._canonical_assist_state(ranked)
        assist_label = assist_state_label(assist_state)
        need = self._assist_context_need_count(ranked)
        readiness_txt = (
            f" (Need {need} more labels in this context)"
            if assist_state.name == "HEURISTIC" and need > 0
            else ""
        )
        panel.header_lbl.setText(
            f"Review Queue - T={t_idx + 1} Z={z_idx + 1} | Assist: {assist_label}{readiness_txt}"
        )
        self._style_assist_state_label(
            panel.assist_lbl,
            assist_state,
            prefix="Assist state: ",
            suffix=readiness_txt,
        )

        if not ranked:
            panel.coords_lbl.setText("(x=-, y=-)")
            panel.score_lbl.setText("p_accept: n/a")
            panel.stale_lbl.setText("staleness: n/a")
            panel.details_lbl.setText("No uncertain suggestions on current frame/scope.")
            panel.accept_btn.setEnabled(False)
            panel.accept_next_btn.setEnabled(False)
            panel.reject_btn.setEnabled(False)
            panel.skip_btn.setEnabled(False)
            panel.next_uncertain_btn.setEnabled(False)
            panel.accept_green_btn.setEnabled(False)
            if hasattr(panel, "offset_count_spin"):
                panel.offset_count_spin.setRange(1, 1)
                panel.offset_count_spin.setValue(1)
            if hasattr(panel, "apply_offset_btn"):
                panel.apply_offset_btn.setEnabled(False)
            self._refresh_suggestion_explain_panel(None)
            self._refresh_right_dock_segment_headers()
            return

        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        p_accept = dict(getattr(current, "meta", {}) or {}).get("p_accept")
        generated_ts = dict(getattr(current, "meta", {}) or {}).get("generated_at_ts")
        panel.coords_lbl.setText(f"(x={int(round(float(current.x)))}, y={int(round(float(current.y)))})")
        if p_accept is None:
            panel.score_lbl.setText(f"p_accept: n/a | generator score: {float(current.score):.2f}")
            panel.details_lbl.setText("Heuristic-only proposal; review required.")
        else:
            p_val = float(p_accept)
            suffix = "(review)" if p_val < 0.5 else ""
            panel.score_lbl.setText(f"p_accept: {p_val:.2f} {suffix}".strip())
            panel.details_lbl.setText(f"Generator score: {float(current.score):.2f}")
        if generated_ts is None:
            panel.stale_lbl.setText("staleness: unknown")
        else:
            age_s = max(0.0, float(time.time()) - float(generated_ts))
            panel.stale_lbl.setText(f"staleness: {age_s:.1f}s")
        panel.accept_btn.setEnabled(True)
        panel.accept_next_btn.setEnabled(True)
        panel.reject_btn.setEnabled(True)
        panel.skip_btn.setEnabled(True)
        panel.next_uncertain_btn.setEnabled(True)
        if hasattr(panel, "offset_count_spin"):
            max_count = max(1, len(ranked))
            panel.offset_count_spin.setRange(1, max_count)
            if int(panel.offset_count_spin.value()) > max_count:
                panel.offset_count_spin.setValue(max_count)
        if hasattr(panel, "apply_offset_btn"):
            panel.apply_offset_btn.setEnabled(True)
        green_count = sum(
            1
            for s in ranked
            if bool(dict(getattr(s, "meta", {}) or {}).get("confidence_available", False))
            and float(dict(getattr(s, "meta", {}) or {}).get("p_accept", 0.0)) >= 0.75
        )
        panel.accept_green_btn.setEnabled(green_count > 0)
        panel.accept_green_btn.setText(
            f"Accept All Green ({green_count})" if green_count > 0 else "Accept All Green"
        )
        self._refresh_suggestion_explain_panel(current)
        self._refresh_right_dock_segment_headers()

    def _refresh_suggestion_explain_panel(self, suggestion: PointSuggestion | None) -> None:
        """Refresh 'Why was this suggested?' panel for the current suggestion."""
        panel = getattr(self, "suggestion_explain_panel", None)
        if panel is None:
            return
        if suggestion is None:
            panel.coords_lbl.setText("(x=-, y=-, t=-, z=-)")
            panel.score_lbl.setText("generator score: n/a")
            panel.calib_lbl.setText("calibrated p_accept: n/a")
            panel.nn_lbl.setText("nearest accepted distance: n/a")
            panel.stale_lbl.setText("staleness: n/a")
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
        panel.score_lbl.setText(f"generator score: {float(getattr(suggestion, 'score', 0.0)):.3f}")
        p_accept = meta.get("p_accept")
        if p_accept is None:
            panel.calib_lbl.setText("calibrated p_accept: n/a (heuristic-only)")
        else:
            panel.calib_lbl.setText(f"calibrated p_accept: {float(p_accept):.3f}")
        nn = meta.get("distance_to_nearest_accepted")
        panel.nn_lbl.setText(
            "nearest accepted distance: n/a"
            if nn is None
            else f"nearest accepted distance: {float(nn):.2f}px"
        )
        ts = meta.get("generated_at_ts")
        if ts is None:
            panel.stale_lbl.setText("staleness: unknown")
        else:
            age_s = max(0.0, float(time.time()) - float(ts))
            panel.stale_lbl.setText(f"staleness: {age_s:.1f}s")
        comp = dict(getattr(suggestion, "score_components", {}) or {})
        if comp:
            lines = [f"{k}: {float(v):.4f}" for k, v in sorted(comp.items()) if isinstance(v, (int, float))]
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
        self._refresh_image()

    def _focus_current_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions above threshold.")
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        self._focus_suggestion(current)
        self._set_status(
            f"Suggestion {self._suggestion_cursor + 1}/{len(ranked)} score={float(current.score):.3f}"
        )
        self._refresh_review_queue_panel()

    def _next_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions above threshold.")
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = (int(getattr(self, "_suggestion_cursor", 0)) + 1) % len(ranked)
        self._focus_current_uncertain_suggestion()

    def _prev_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions above threshold.")
            self._refresh_review_queue_panel()
            return
        self._suggestion_cursor = (int(getattr(self, "_suggestion_cursor", 0)) - 1) % len(ranked)
        self._focus_current_uncertain_suggestion()

    def _accept_current_uncertain_suggestion(self) -> None:
        if not self._ensure_annotation_write_context_confirmed("Accept current suggestion"):
            return
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions above threshold.")
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        cmd = AcceptSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            self._refresh_table()
            self._refresh_image()
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
            self._set_status("No visible suggestions above threshold.")
            return
        self._accept_current_uncertain_suggestion()
        self._next_uncertain_suggestion()

    def _reject_current_uncertain_suggestion(self) -> None:
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions above threshold.")
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        current = ranked[self._suggestion_cursor]
        cmd = RejectSuggestionCommand(self.controller, self.primary_image.id, current.suggestion_id)
        if self.controller.execute_view_command(cmd):
            self.undo_act.setEnabled(self.controller.can_undo())
            self.redo_act.setEnabled(self.controller.can_redo())
            self._refresh_image()
            if bool(getattr(self, "_timed_session_active", False)):
                self._timed_session_rejects = int(getattr(self, "_timed_session_rejects", 0)) + 1
            self._refresh_assist_warmup_panel()
        self._focus_current_uncertain_suggestion()

    def _show_current_suggestion_patch(self) -> None:
        """Show a small snap-view patch around the current uncertain suggestion."""
        ranked = self._visible_suggestions_uncertain_first()
        if not ranked:
            self._set_status("No visible suggestions above threshold.")
            return
        self._suggestion_cursor = int(
            max(0, min(int(getattr(self, "_suggestion_cursor", 0)), len(ranked) - 1))
        )
        suggestion = ranked[self._suggestion_cursor]
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

    def _on_suggestion_auto_retrain_changed(self, checked: bool) -> None:
        """Enable/disable periodic ranker retraining from labels."""
        self.controller.set_suggestion_retrain_config(enabled=bool(checked))
        self._settings.setValue("suggestionAutoRetrainEnabled", bool(checked))
        self._set_status(
            "Auto-retrain enabled." if bool(checked) else "Auto-retrain disabled."
        )
        self._update_status()

    def _on_suggestion_min_labels_changed(self, value: int) -> None:
        """Set minimum labeled samples required before auto-retrain."""
        min_labels = int(max(1, value))
        self.controller.set_suggestion_retrain_config(min_labels=min_labels)
        self._settings.setValue("suggestionAutoRetrainMinLabels", min_labels)
        self._set_status(f"Auto-retrain min labels set to {min_labels}.")
        self._update_status()

    def _train_suggestion_ranker_now(self) -> None:
        """Force immediate ranker training from current labeled history."""
        ok = self.controller.train_suggestion_ranker_now()
        if ok:
            self._set_status("Suggestion ranker trained.")
        else:
            self._set_status("Not enough labeled suggestions to train ranker.")
        self._refresh_assist_warmup_panel()
        self._update_status()

    def _on_annotation_space_changed(self, value: str) -> None:
        """Switch annotation space between stack and projection contexts."""
        old_space = str(getattr(self.controller.session_state, "annotation_space", "stack")).strip().lower()
        space = str(value or "stack").strip().lower()
        if space not in ("stack", "projection"):
            space = "stack"
        self.controller.session_state.annotation_space = space
        if old_space != space:
            self._mark_annotation_context_changed(
                f"annotation space changed ({old_space} -> {space})"
            )
        self._set_status(f"Annotation space: {space}.")
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
        self._set_status("Assist minima updated.")
        self._refresh_assist_warmup_panel()
        self._update_status()

    def _on_qc_auto_show_changed(self, checked: bool) -> None:
        """Enable/disable automatically showing QC panel when issues are found."""
        self._settings.setValue("qcAutoShowOnIssues", bool(checked))
        self._set_status(
            "QC panel auto-show enabled."
            if bool(checked)
            else "QC panel auto-show disabled."
        )

    def _start_assist_warmup(self) -> None:
        """Guide early balanced accept/reject triage to bootstrap learned assist."""
        self._refresh_assist_warmup_panel()
        self._focus_current_uncertain_suggestion()
        visible = self._visible_suggestions_uncertain_first()
        if not visible:
            self._set_status("Warmup: generate suggestions first.")
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
        self._set_status(
            "Warmup mode: use N/P to move, A accept, R reject. "
            f"Need +{b['need_pos']} positives, +{b['need_neg']} negatives, +{b['need_context']} context labels."
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
        self._set_status(f"Timed annotation session started ({mode}).")

    def _stop_timed_annotation_session(self) -> None:
        """Stop timed benchmark session and report metrics."""
        if not bool(getattr(self, "_timed_session_active", False)):
            self._set_status("No active timed session.")
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
            self._set_status("Select one or more annotations first.")
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
            self._refresh_image()
        self._set_status(f"Updated review state for {updated} annotation(s).")

    def _assign_selected_annotations_dialog(self) -> None:
        """Set assignee for selected annotations."""
        selected = self._selected_table_keypoints()
        if not selected:
            self._set_status("Select one or more annotations first.")
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
            self._refresh_image()
        self._set_status(f"Assigned {updated} annotation(s) to '{assignee}'.")

    def _set_current_user_dialog(self) -> None:
        """Set current local user identity for review/audit actions."""
        current = self.controller.session_state.current_user
        user, ok = QtWidgets.QInputDialog.getText(self, "Set Current User", "User:", text=current)
        if not ok:
            return
        user = user.strip() or "local_user"
        self.controller.session_state.current_user = user
        self.controller.append_audit_event("current_user_changed", user=user)
        self._set_status(f"Current user set to '{user}'.")

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
        self._refresh_image()
        self._set_status(f"Review queue: {self._review_queue_filter}.")

    def _show_profile_dialog(self) -> None:
        """Open a dialog showing line profiles (vertical, horizontal, diagonals) raw vs corrected."""
        if self.primary_image.array is None:
            return
        data = self._apply_crop(self._slice_data(self.primary_image))
        h, w = data.shape
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

            def _roi_mask_local(shape: Tuple[int, int]) -> np.ndarray:
                h, w = shape
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
        self._set_status(f"Cleared cached image data for {cleared} images.")
        # Will lazily reload the active images after purge.
        self._refresh_image()

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

    def _clear_fov_list(self) -> None:
        """Remove all FOVs except the current primary to reset the list."""
        if not self.images:
            return
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        keep_idx = self.current_image_idx
        keep_img = self.images[keep_idx]
        self.controller.retain_single_image(keep_idx)
        self.fov_list.clear()
        self.primary_combo.clear()
        self.support_combo.clear()
        keep_img.id = 0
        self.fov_list.addItem(keep_img.name)
        self.primary_combo.addItem(keep_img.name)
        self.support_combo.addItem(keep_img.name)
        self.current_image_idx = 0
        self.support_image_idx = 0
        self._set_status("Cleared FOV list; kept current image.")
        self.roi_manager.rois_by_image = {0: self.roi_manager.list_rois(keep_idx)}
        self.roi_manager.set_active(self.roi_manager.active_roi_id)
        self._refresh_roi_manager()
        self._refresh_image()

    def _recent_limit(self) -> int:
        return int(self._settings.value("keepRecentImages", 10, type=int))

    def _load_recent_images(self) -> List[str]:
        recent = self._settings.value("recentImages", [], type=list)
        recent_list = [str(p) for p in recent] if recent else []
        self.controller.set_recent_images(recent_list)
        return recent_list

    def _save_recent_images(self, recent: List[str]) -> None:
        self._settings.setValue("recentImages", recent)
        self.controller.set_recent_images(recent)

    def _add_recent_images(self, paths: List[pathlib.Path]) -> None:
        recent = self._load_recent_images()
        for p in paths:
            p_str = str(p)
            if p_str in recent:
                recent.remove(p_str)
            recent.insert(0, p_str)
        limit = self._recent_limit()
        recent = recent[:limit]
        self._save_recent_images(recent)
        self._populate_recent_menu()

    def _populate_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = self._load_recent_images()
        for path in recent:
            act = self.recent_menu.addAction(path)
            act.triggered.connect(lambda _checked, p=path: self._open_recent_image(p))
        if recent:
            self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.recent_clear_act)

    def _clear_recent_images(self) -> None:
        self._save_recent_images([])
        self._populate_recent_menu()

    def _open_recent_image(self, path: str) -> None:
        p = pathlib.Path(path)
        if not p.exists():
            QtWidgets.QMessageBox.warning(self, "File not found", f"{path} does not exist.")
            self._clear_recent_images()
            return
        self._open_files_from_paths([p])

    def _open_files_from_paths(self, paths: List[pathlib.Path]) -> None:
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        self._add_recent_images(paths)
        self._last_folder = paths[0].parent
        self.roi_manager.rois_by_image.clear()
        new_images = []
        for p in paths:
            meta = read_metadata(p)
            new_images.append(meta)
        self.controller.add_images(new_images)
        for meta in new_images:
            self.fov_list.addItem(meta.name)
            self.primary_combo.addItem(meta.name)
            self.support_combo.addItem(meta.name)
            self.roi_manager.rois_by_image[meta.id] = []
        self._refresh_annotation_availability()
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._refresh_image()
        
        # Phase ζ: Update modality selectors in analysis panels
        self._update_analysis_panel_modalities()

    def _refresh_annotation_availability(self) -> None:
        if self.fov_list is None:
            return
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView)
        for idx, img in enumerate(self.images):
            item = self.fov_list.item(idx)
            if item is None:
                continue
            if self.controller.annotations_available(img.id):
                item.setIcon(icon)
                item.setToolTip("Annotations available")
            else:
                item.setIcon(QtGui.QIcon())
                item.setToolTip("")

    def _maybe_autoload_annotations(self, image_id: int) -> None:
        if not self._settings.value("autoLoadAnnotations", True, type=bool):
            return
        if self.controller.annotations_are_loaded(image_id):
            return
        if not self.controller.annotation_entries_for_image(image_id):
            return
        cal = self._get_calibration_state(image_id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        self._start_annotation_load_job(image_id, replace=False, pixel_size_nm=pixel_size_nm)

    def _start_annotation_load_job(
        self, image_id: int, *, replace: bool, pixel_size_nm: Optional[float]
    ) -> None:
        existing = self._annotation_job_tokens.get(image_id)
        if existing is not None:
            existing.cancel()

        def _worker(progress, cancel):
            paths = [entry.path for entry in self.controller.annotation_entries_for_image(image_id)]
            points, imports = self.controller._parse_annotations_from_paths(
                paths,
                image_id=image_id,
                pixel_size_nm=pixel_size_nm,
                force_image_id=image_id,
            )
            return (points, imports)

        def _on_result(result):
            if result is None:
                return
            points, imports = result
            self.controller._record_annotation_imports(imports)
            if replace:
                self.controller.replace_annotations(image_id, points)
            else:
                self.controller.merge_annotations(image_id, points)
            meta = None
            for target_id, entry in imports:
                if target_id == image_id:
                    meta = entry.get("meta")
                    if isinstance(meta, dict) and meta:
                        break
            if meta:
                self._handle_annotation_metadata(image_id, meta)
            self._mark_dirty()
            self.controller.annotations_changed.emit()
            if image_id == self.primary_image.id:
                self._refresh_image()
            try:
                # Brief user feedback on completion
                self.statusBar().showMessage("Annotations loaded.", 3000)
            except Exception:
                pass

        def _on_error(err: str) -> None:
            try:
                self.statusBar().showMessage("Annotation load error (see Logs)", 4000)
            except Exception:
                pass
            self._append_log(f"[Annotations] Load error for image id={image_id}\n{err}")

        try:
            self.statusBar().showMessage("Loading annotations…", 2000)
        except Exception:
            pass
        handle = self.jobs.submit(
            _worker,
            name="Load annotations",
            on_result=_on_result,
            on_error=_on_error,
            timeout_sec=300.0,
            retries=2,
            retry_delay_sec=1.0,
        )
        self._annotation_job_tokens[image_id] = handle.cancel_token
        self._annotation_job_ids[image_id] = handle.job_id

    def _on_metadata_dock_visibility(self, visible: bool) -> None:
        if not visible:
            return
        self._load_full_metadata()

    def _refresh_metadata_dock(self, image_id: int) -> None:
        if getattr(self, "metadata_widget", None) is None:
            return
        summary = self.controller.get_metadata_summary(image_id)
        bundle = MetadataBundle(
            summary=summary,
            tiff_tags={},
            ome_xml=None,
            ome_parsed=None,
            micromanager=None,
            vendor_private={},
        )
        self.metadata_widget.set_bundle(bundle)
        if self.dock_metadata is not None and self.dock_metadata.isVisible():
            self._load_full_metadata()

    def _load_full_metadata(self) -> None:
        if getattr(self, "metadata_widget", None) is None:
            return
        image_id = self.primary_image.id
        bundle = self.controller.load_metadata_bundle(image_id)
        self.metadata_widget.set_bundle(bundle)

    def _handle_annotation_metadata(self, image_id: int, meta: dict) -> None:
        self._pending_annotation_meta = meta
        self._pending_annotation_meta_image_id = image_id
        self._show_annotation_meta_banner(image_id, meta)
        if self._settings.value("applyAnnotationMetaOnLoad", False, type=bool):
            self._apply_annotation_metadata(keep_banner=True)

    def _show_annotation_meta_banner(self, image_id: int, meta: dict) -> None:
        if not hasattr(self, "annotation_meta_widget") or self.annotation_meta_widget is None:
            return
        image_name = self.images[image_id].name if 0 <= image_id < len(self.images) else "image"
        self.annotation_meta_label.setText(f"Metadata detected for {image_name}.")
        self.annotation_meta_widget.setVisible(True)

    def _dismiss_annotation_meta_banner(self) -> None:
        if hasattr(self, "annotation_meta_widget") and self.annotation_meta_widget is not None:
            self.annotation_meta_widget.setVisible(False)
        self._pending_annotation_meta = None
        self._pending_annotation_meta_image_id = None

    def _apply_annotation_metadata(self, keep_banner: bool = False) -> None:
        meta = self._pending_annotation_meta
        image_id = self._pending_annotation_meta_image_id
        if not meta or image_id is None:
            return
        active_primary = self.primary_image.id
        roi = meta.get("roi")
        if isinstance(roi, dict) and image_id == active_primary:
            shape = roi.get("shape", "box")
            rect = roi.get("rect")
            if rect and len(rect) == 4:
                rect = tuple(float(v) for v in rect)
                self.controller.set_roi(rect, shape=str(shape))
                self.roi_rect = rect
                self.roi_shape = str(shape)
            elif shape == "circle":
                center = roi.get("center")
                radius = roi.get("radius")
                if center and radius is not None:
                    cx, cy = center
                    rect = (
                        float(cx - radius),
                        float(cy - radius),
                        float(radius * 2),
                        float(radius * 2),
                    )
                    self.controller.set_roi(rect, shape="circle")
                    self.roi_rect = rect
                    self.roi_shape = "circle"
        crop = meta.get("crop")
        if crop and len(crop) == 4 and image_id == active_primary:
            self.crop_rect = tuple(float(v) for v in crop)
            self.controller.set_crop(self.crop_rect)
            self._sync_crop_controls()
        if image_id == active_primary and roi is not None:
            self._sync_roi_controls()
        display = meta.get("display")
        if isinstance(display, dict):
            non_active_mapping = None
            win = display.get("win")
            if isinstance(win, dict) and "min" in win and "max" in win:
                if image_id == active_primary:
                    self.controller.set_display_mapping(
                        float(win["min"]), float(win["max"]), display.get("gamma")
                    )
                else:
                    non_active_mapping = self.controller.display_mapping.mapping_for(
                        image_id, "frame"
                    )
                    non_active_mapping.set_window(float(win["min"]), float(win["max"]))
            else:
                pct = display.get("pct")
                if (
                    isinstance(pct, dict)
                    and self.primary_image.array is not None
                    and image_id == active_primary
                ):
                    try:
                        low = float(pct.get("low", 2.0))
                        high = float(pct.get("high", 98.0))
                        data = self._slice_data(self.primary_image)
                        vmin = float(np.percentile(data, low))
                        vmax = float(np.percentile(data, high))
                        self.controller.set_display_mapping(vmin, vmax, display.get("gamma"))
                    except (TypeError, ValueError):
                        pass
            gamma = display.get("gamma")
            if gamma is not None:
                try:
                    if image_id == active_primary:
                        self.controller.set_gamma(float(gamma))
                    else:
                        if non_active_mapping is None:
                            non_active_mapping = self.controller.display_mapping.mapping_for(
                                image_id, "frame"
                            )
                        non_active_mapping.gamma = float(gamma)
                except (TypeError, ValueError):
                    pass
            mode = display.get("mode")
            if isinstance(mode, str):
                if image_id == active_primary:
                    mapping = self.controller.display_mapping.mapping_for(image_id, "frame")
                    mapping.mode = mode
                    self.controller.set_display_for_image(image_id, "frame", mapping)
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.mode = mode
            lut = display.get("lut")
            if isinstance(lut, str) and lut in lut_names():
                if image_id == active_primary:
                    self.controller.set_lut(lut_names().index(lut))
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.lut = lut_names().index(lut)
            elif isinstance(lut, int):
                if image_id == active_primary:
                    self.controller.set_lut(lut)
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.lut = lut
            invert = display.get("invert")
            if invert is not None:
                if image_id == active_primary:
                    self.controller.set_invert(bool(invert))
                else:
                    if non_active_mapping is None:
                        non_active_mapping = self.controller.display_mapping.mapping_for(
                            image_id, "frame"
                        )
                    non_active_mapping.invert = bool(invert)
            if non_active_mapping is not None and image_id != active_primary:
                self.controller.set_display_for_image(image_id, "frame", non_active_mapping)
        axis = meta.get("axis")
        if isinstance(axis, str):
            self.controller.set_axis_interpretation(image_id, axis)
            if image_id == active_primary and hasattr(self, "axis_mode_combo"):
                self.axis_mode_combo.setCurrentText(axis)
        if keep_banner:
            if hasattr(self, "annotation_meta_label"):
                self.annotation_meta_label.setText("Metadata applied.")
        else:
            self._dismiss_annotation_meta_banner()
        self._refresh_image()
