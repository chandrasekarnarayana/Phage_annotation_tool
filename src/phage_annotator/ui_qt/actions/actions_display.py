"""Display, view, and modality layer actions."""

from __future__ import annotations

import json
import logging

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.rendering.lut_manager import lut_names

logger = logging.getLogger(__name__)


class ActionsMixinDisplay:
    """Mixin for view/display toggles, modality layers, and help dialogs."""

    def _toggle_left_pane(self) -> None:
        """Toggle left pane for the current workflow."""
        if self.dock_sidebar is None:
            return
        self._set_panel_visibility("sidebar")

    def _toggle_settings_pane(self) -> None:
        """Toggle settings pane for the current workflow."""
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
        """Handle the on link zoom menu helper flow."""
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
        """Show about for the current workflow."""
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
        from phage_annotator.ui_qt.assist_state import assist_state_label
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

    # ── Modality / evidence layer management ──────────────────────────────

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
