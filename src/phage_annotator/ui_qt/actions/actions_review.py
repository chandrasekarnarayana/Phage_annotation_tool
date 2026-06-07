"""Extracted method group 8 for ActionsMixin."""

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



class ActionsReviewMixin:
    """Method group 8 extracted from ActionsMixin."""

    def _toggle_suggestions_overlay(self, checked: bool) -> None:
        """Toggle suggestion overlay rendering."""
        visible = bool(checked)
        self._show_suggestion_overlay = visible
        if getattr(self, "review_queue_panel", None) is not None and hasattr(
            self.review_queue_panel, "show_suggestions_chk"
        ):
            self.review_queue_panel.show_suggestions_chk.blockSignals(True)
            self.review_queue_panel.show_suggestions_chk.setChecked(visible)
            self.review_queue_panel.show_suggestions_chk.blockSignals(False)
        action = getattr(self, "toggle_suggestions_overlay_act", None)
        if action is not None and bool(action.isChecked()) != visible:
            action.blockSignals(True)
            action.setChecked(visible)
            action.blockSignals(False)
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
