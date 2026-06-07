"""Extracted method group 3 for ActionsMixin."""

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



class ActionsModalityLayersMixin:
    """Method group 3 extracted from ActionsMixin."""

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
