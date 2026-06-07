"""Extracted method group 13 for ActionsMixin."""

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



class ActionsAssistConfigMixin:
    """Method group 13 extracted from ActionsMixin."""

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
