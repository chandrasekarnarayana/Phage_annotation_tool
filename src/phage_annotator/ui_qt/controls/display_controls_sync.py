"""Extracted method group 8 for DisplayControlsMixin."""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_auto_window
from phage_annotator.session.signal_hub import emit_display_changed, emit_view_changed
from phage_annotator.session.modality import ProjectionType
from phage_annotator.session.multi_playback import PlaybackMode
from phage_annotator.ui_qt.controls.display_contrast import DisplayContrastMixin
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger



class DisplayControlsSyncMixin:
    """Method group 8 extracted from DisplayControlsMixin."""

    def _sync_panel_summary(self) -> str:
        """Return the currently targeted panel set for the active/manual sync group."""
        selected = list(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return "Sync panels: -"
        labels = []
        for key in selected:
            modality = dict(getattr(self, "_panel_modality_map", {}) or {}).get(str(key))
            if modality is not None:
                labels.append(str(getattr(modality, "display_name", key)))
            else:
                labels.append(str(key))
        preview = ", ".join(labels[:3])
        if len(labels) > 3:
            preview += f" +{len(labels) - 3}"
        return f"Sync panels: {preview}"
    def _sync_view_summary(self) -> str:
        """Return a compact viewport readout for the current sync target."""
        selected = list(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return "Sync view: -"
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        active_key = str(getattr(self, "annotate_target", default_target)).strip().lower() or default_target
        panel_key = active_key if active_key in selected else str(selected[0])
        ax = None
        if getattr(self, "renderer", None) is not None:
            ax = self.renderer.axes.get(panel_key)
        if ax is None:
            return f"Sync view: {panel_key}"
        try:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            shape = getattr(self, "_last_display_shape", None)
            if shape is None or len(shape) < 2:
                return f"Sync view: {panel_key}"
            width = max(1e-6, abs(float(xlim[1]) - float(xlim[0])))
            zoom = max(0.1, min(20.0, float(shape[1]) / width))
            pan_x = float(min(xlim))
            pan_y = float(min(ylim))
            return f"Sync view: {panel_key} | Zoom {zoom:.2f}x | Pan {pan_x:.0f}, {pan_y:.0f}"
        except Exception:
            return f"Sync view: {panel_key}"
    def _refresh_prepare_setup_summary(self) -> None:
        """Refresh the Prepare-page mirrors for reference, sync, and ROI setup."""
        reference_lbl = getattr(self, "prepare_reference_summary_lbl", None)
        if reference_lbl is not None:
            primary_name = "-"
            support_name = "-"
            images = list(getattr(self, "images", []) or [])
            primary_idx = int(getattr(self, "current_image_idx", 0))
            support_idx = int(getattr(self, "support_image_idx", 0))
            if 0 <= primary_idx < len(images):
                primary_name = str(getattr(images[primary_idx], "name", "-")).strip() or "-"
            if 0 <= support_idx < len(images):
                support_name = str(getattr(images[support_idx], "name", "-")).strip() or "-"
            relation = "same view" if primary_name == support_name else "compare pair"
            reference_lbl.setText(
                f"Reference views: Primary {primary_name} | Reference {support_name} ({relation})"
            )
        roi_lbl = getattr(self, "prepare_roi_summary_lbl", None)
        if roi_lbl is not None:
            rect = tuple(getattr(self, "roi_rect", (0.0, 0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0, 0.0))
            if len(rect) >= 4 and float(rect[2]) > 0 and float(rect[3]) > 0:
                roi_lbl.setText(
                    f"ROI: x={float(rect[0]):.0f}, y={float(rect[1]):.0f}, w={float(rect[2]):.0f}, h={float(rect[3]):.0f}"
                )
            else:
                roi_lbl.setText("ROI: Full field")
    def _selected_sync_panels(self, default_to_all: bool = False) -> List[str]:
        """Handle the selected sync panels helper flow."""
        panel_keys = list(getattr(self, "_panel_sync_index", {}).keys())
        if not panel_keys:
            return []
        follow_active = self._sync_follow_active_enabled()
        if follow_active:
            group = self._sync_key_active_group()
            self._set_sync_key_combo_data(group)
        else:
            group = str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "")
        group = str(group).strip()
        if not group:
            return panel_keys if default_to_all else []
        selected = [k for k in panel_keys if self._sync_key_for_panel(str(k)) == group]
        if not selected and default_to_all:
            return panel_keys
        return selected
    def _on_sync_selection_changed(self) -> None:
        """Handle the on sync selection changed helper flow."""
        self._on_sync_mode_changed()
    def _update_sync_indicators(self) -> None:
        """Refresh sync target tooltips for current mode."""
        combo = getattr(self, "sync_key_combo", None)
        mode_combo = getattr(self, "sync_target_mode_combo", None)
        follow = getattr(self, "sync_follow_active_chk", None)
        if combo is not None:
            combo.setToolTip("Manual sync target group.")
        if mode_combo is not None:
            mode_combo.setToolTip("Choose manual group or active canvas group target.")
        if follow is not None:
            follow.setToolTip(
                "Use active canvas view group."
                if follow.isChecked()
                else "Use manually selected group."
            )
    def _on_sync_mode_changed(self) -> None:
        """Handle the on sync mode changed helper flow."""
        combo = getattr(self, "sync_key_combo", None)
        follow_active = self._sync_follow_active_enabled()
        follow = getattr(self, "sync_follow_active_chk", None)
        if follow is not None:
            follow.blockSignals(True)
            follow.setChecked(follow_active)
            follow.blockSignals(False)
        if follow_active:
            self._set_sync_key_combo_data(self._sync_key_active_group())
        if hasattr(self, "_apply_roi_for_sync_group"):
            try:
                target_group = (
                    self._sync_key_active_group()
                    if follow_active
                    else str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "")
                )
                self._apply_roi_for_sync_group(str(target_group).strip())
            except Exception:
                pass
        if combo is not None:
            combo.setEnabled(True)
        self._apply_sync_selection()
        self._update_sync_indicators()
        self._on_sync_scope_changed("")
        self._sync_contrast_from_frame()
    def _apply_sync_selection(self) -> None:
        """Apply sync selection for the current workflow."""
        self._apply_view_sync_selection()
        self._apply_playback_sync_selection()
    def _apply_view_sync_selection(self) -> None:
        """Apply view sync selection for the current workflow."""
        if getattr(self, "view_sync", None) is None:
            return
        if not self.link_zoom:
            self.view_sync.clear()
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        selected = {
            key
            for key in self._selected_sync_panels(default_to_all=True)
            if self._sync_mode_enabled_for_panel(str(key), "zoom")
        }
        if not selected:
            self.view_sync.clear()
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        group = {
            idx
            for key, idx in getattr(self, "_panel_sync_index", {}).items()
            if key in selected
        }
        if not group:
            self.view_sync.clear()
            self.view_sync.enable_zoom_sync(False)
            self.view_sync.enable_pan_sync(False)
            return
        self.view_sync.clear()
        for idx in getattr(self, "_panel_sync_reverse", {}).keys():
            self.view_sync.register_modality(idx)
        self.view_sync.create_link_group(group)
        self.view_sync.enable_zoom_sync(True)
        self.view_sync.enable_pan_sync(True)
    def _apply_playback_sync_selection(self) -> None:
        """Apply playback sync selection for the current workflow."""
        if getattr(self, "modality_playback", None) is None:
            return
        targets = self._selected_playback_modalities()
        selected_panels = self._selected_sync_panels(default_to_all=True)
        if selected_panels and not targets:
            self.modality_playback.set_sync_group(set())
            return
        self.modality_playback.set_sync_group(targets if targets else None)
    def _selected_playback_modalities(self) -> set[int]:
        """Handle the selected playback modalities helper flow."""
        selected = {
            key
            for key in self._selected_sync_panels(default_to_all=True)
            if self._sync_mode_enabled_for_panel(str(key), "playback")
        }
        targets: set[int] = set()
        panel_map = getattr(self, "_panel_modality_map", {})
        manager = getattr(getattr(self, "controller", None), "session_state", None)
        manager = getattr(manager, "modality_manager", None)
        for key in selected:
            key_text = str(key)
            if key_text.startswith("modality_") and manager is not None:
                try:
                    mod_idx = int(key_text.split("_", 1)[1])
                    base_mod = manager.get_modality(mod_idx)
                    if base_mod is not None and base_mod.projection_type == ProjectionType.RAW:
                        targets.add(int(base_mod.idx))
                    continue
                except Exception:
                    pass
            modality = panel_map.get(key)
            if modality is None:
                continue
            if modality.idx < 0:
                continue
            if modality.projection_type != ProjectionType.RAW:
                continue
            targets.add(modality.idx)
        return targets
    def _sync_view_manager_panels(self, visible: List[str]) -> None:
        """Synchronize view manager panels for the current workflow."""
        if getattr(self, "view_sync", None) is None:
            return
        self.view_sync.clear()
        self._panel_sync_index = {}
        self._panel_sync_reverse = {}
        for idx, key in enumerate(visible):
            self._panel_sync_index[key] = idx
            self._panel_sync_reverse[idx] = key
            self.view_sync.register_modality(idx)
        self._update_sync_list(visible)
        self._update_sync_indicators()
        self._apply_view_sync_selection()
        self._apply_playback_sync_selection()
