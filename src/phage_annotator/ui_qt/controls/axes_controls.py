"""Extracted method group 7 for DisplayControlsMixin."""

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



class AxesControlsMixin:
    """Method group 7 extracted from DisplayControlsMixin."""

    def _focus_axis_mode_control(self) -> None:
        """Handle the focus axis mode control helper flow."""
        if getattr(self, "advanced_group", None) is not None:
            self.advanced_group.setChecked(True)
            self.axis_mode_combo.setFocus()
            self.axis_mode_combo.showPopup()
    def _update_axes_info(self) -> None:
        """Refresh the Axes info panel and tooltip (OME vs heuristic)."""
        img = self.primary_image
        if img.array is not None:
            t, z, y, x = img.array.shape
        else:
            shape = img.shape
            if len(shape) == 2:
                t, z, y, x = 1, 1, shape[0], shape[1]
            elif len(shape) == 3:
                if img.has_time and not img.has_z:
                    t, z, y, x = shape[0], 1, shape[1], shape[2]
                elif img.has_z and not img.has_time:
                    t, z, y, x = 1, shape[0], shape[1], shape[2]
                else:
                    # RGB/multi-channel 2D image.
                    t, z, y, x = 1, 1, shape[0], shape[1]
            else:
                t, z, y, x = shape[0], shape[1], shape[2], shape[3]

        interp = img.interpret_3d_as
        self.axes_info_label.setText(
            f"T: {t}  Z: {z}  Y: {y}  X: {x}  | Interpretation: {interp}"
        )
        if img.ome_axes:
            tooltip = f"OME metadata axes: {img.ome_axes}"
        elif img.axis_auto_used and img.axis_auto_mode:
            tooltip = f"Auto heuristic used: {img.axis_auto_mode}"
        else:
            tooltip = "No OME metadata; manual interpretation"
        self.axes_info_label.setToolTip(tooltip)
    def _update_axis_warning(self) -> None:
        """Show a non-intrusive warning when auto heuristics are used."""
        img = self.primary_image
        if img.interpret_3d_as == "auto" and img.axis_auto_used and img.axis_auto_mode:
            mode = img.axis_auto_mode.upper()
            self.axis_warning.setText(
                f'<a href="axes">3D axis interpreted as {mode} (auto). Click to change.</a>'
            )
            self.axis_warning.setVisible(True)
        else:
            self.axis_warning.setVisible(False)
    def _on_limits_changed(self, ax) -> None:
        """Handle the on limits changed helper flow."""
        if getattr(self, "renderer", None) is not None:
            if ax not in set(self.renderer.axes.values()):
                return
        else:
            return
        if self._suppress_limits:
            return
        if self.link_zoom:
            self._last_zoom_linked = (ax.get_xlim(), ax.get_ylim())
            self._update_status()
        self._sync_view_from_axis(ax)
        self._update_sync_keys_hint()
    def _sync_view_from_axis(self, ax) -> None:
        """Synchronize view from axis for the current workflow."""
        if getattr(self, "view_sync", None) is None:
            return
        if not self.link_zoom:
            return
        panel_key = self._panel_key_for_axis(ax)
        if panel_key is None:
            return
        shape = getattr(self, "_last_display_shape", None)
        if shape is None:
            return
        if len(shape) < 2:
            return
        w = int(shape[1])
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        span_x = max(1e-6, abs(xlim[1] - xlim[0]))
        zoom_level = max(0.1, min(20.0, w / span_x))
        pan_x = float(xlim[0])
        pan_y = float(ylim[1])  # top of view
        idx = getattr(self, "_panel_sync_index", {}).get(panel_key)
        if idx is not None:
            self.view_sync.set_view(idx, zoom_level, pan_x, pan_y)
    def _panel_key_for_axis(self, ax) -> Optional[str]:
        """Handle the panel key for axis helper flow."""
        if getattr(self, "renderer", None) is not None:
            for key, panel_ax in self.renderer.axes.items():
                if panel_ax == ax:
                    return key
        return None
    def _update_sync_list(self, visible: List[str]) -> None:
        """Update sync list for the current workflow."""
        if hasattr(self, "_ensure_lazy_sync_group_keys"):
            try:
                self._ensure_lazy_sync_group_keys()
            except Exception:
                pass
        self._sync_selected_panels = set(visible)
        self._update_sync_key_selector()
        self._update_sync_keys_hint()
    def _update_sync_key_selector(self) -> None:
        """Refresh sync-key selector from current lazy-loading group keys."""
        combo = getattr(self, "sync_key_combo", None)
        if combo is None:
            return
        current = combo.currentData()
        keys = []
        for panel_key in getattr(self, "_panel_sync_index", {}).keys():
            sync_key = self._sync_key_for_panel(str(panel_key))
            if str(sync_key).strip().isdigit():
                keys.append(str(sync_key).strip())
        ordered = sorted(set(keys), key=lambda v: int(v))
        combo.blockSignals(True)
        try:
            combo.clear()
            for key in ordered:
                combo.addItem(f"Group {key}", key)
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            combo.blockSignals(False)
    def _on_sync_key_changed(self, _index: int) -> None:
        """Apply sync updates when manual sync-key selection changes."""
        combo = getattr(self, "sync_key_combo", None)
        if combo is None:
            return
        key = str(combo.currentData() or "").strip()
        if key.isdigit() and hasattr(self, "_apply_lazy_group_sync_selection"):
            self._on_sync_mode_changed()
            self._status_info(
                f"Sync target group: {key}",
                timeout_ms=2500,
                source="display.sync_group",
            )
    def _sync_key_for_panel(self, panel_key: str) -> str:
        """Return sync key for a panel from lazy modality/view group mapping."""
        groups = self._lazy_sync_groups_state() if hasattr(self, "_lazy_sync_groups_state") else {}
        role = self._sync_role_for_panel(panel_key)
        return str(groups.get(role, "")).strip() if role is not None else ""
    def _update_sync_keys_hint(self) -> None:
        """Show available sync keys and effective target source."""
        hint = getattr(self, "sync_keys_hint_lbl", None)
        live = getattr(self, "sync_target_live_lbl", None)
        contract = getattr(self, "sync_contract_live_lbl", None)
        panels = getattr(self, "sync_panels_live_lbl", None)
        view = getattr(self, "sync_view_live_lbl", None)
        if hint is None:
            return
        keys = []
        for panel_key in getattr(self, "_panel_sync_index", {}).keys():
            sync_key = self._sync_key_for_panel(str(panel_key))
            if str(sync_key).strip().isdigit():
                keys.append(str(sync_key).strip())
        if keys:
            ordered = sorted(set(keys), key=lambda v: int(v))
            selected_key = str(
                getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or ""
            ).strip()
            mode = "active view group" if self._sync_follow_active_enabled() else f"group {selected_key or '-'}"
            hint.setText(f"Groups available: {', '.join(ordered)} | Target: {mode}")
            if live is not None:
                if "active view group" in mode:
                    default_target = (
                        self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
                    )
                    active_key = str(getattr(self, "annotate_target", default_target)).strip().lower() or default_target
                    active_group = self._sync_key_for_panel(active_key) or "-"
                    live.setText(f"Sync target: Active group ({active_group})")
                else:
                    live.setText(f"Sync target: Manual group ({selected_key or '-'})")
            if contract is not None:
                contract.setText(self._sync_contract_summary())
            if panels is not None:
                panels.setText(self._sync_panel_summary())
            if view is not None:
                view.setText(self._sync_view_summary())
        else:
            hint.setText("Groups available: none")
            if live is not None:
                live.setText("Sync target: -")
            if contract is not None:
                contract.setText("Sync contract: -")
            if panels is not None:
                panels.setText("Sync panels: -")
            if view is not None:
                view.setText("Sync view: -")
        prepare_target = getattr(self, "prepare_sync_target_lbl", None)
        if prepare_target is not None and live is not None:
            prepare_target.setText(live.text())
        prepare_contract = getattr(self, "prepare_sync_contract_lbl", None)
        if prepare_contract is not None and contract is not None:
            prepare_contract.setText(contract.text())
        prepare_panels = getattr(self, "prepare_sync_panels_lbl", None)
        if prepare_panels is not None and panels is not None:
            prepare_panels.setText(panels.text())
        self._refresh_prepare_setup_summary()
    def _sync_contract_summary(self) -> str:
        """Return a concise summary of the current effective sync contract."""
        selected = list(self._selected_sync_panels(default_to_all=True))
        if not selected:
            return "Sync contract: -"
        mode_labels: list[str] = []
        if any(self._sync_mode_enabled_for_panel(str(key), "contrast") for key in selected):
            mode_labels.append("Contrast")
        if any(self._sync_mode_enabled_for_panel(str(key), "zoom") for key in selected):
            mode_labels.append("Zoom/Pan")
        if any(self._sync_mode_enabled_for_panel(str(key), "playback") for key in selected):
            mode_labels.append("Playback")
        group = (
            self._sync_key_active_group()
            if self._sync_follow_active_enabled()
            else str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "").strip()
        ) or "-"
        return (
            f"Sync contract: Group {group} | {', '.join(mode_labels)}"
            if mode_labels
            else f"Sync contract: Group {group} | None"
        )
