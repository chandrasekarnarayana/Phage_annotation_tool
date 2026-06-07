"""Extracted method group 9 for DisplayControlsMixin."""

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



class DisplayControlsModalityMixin:
    """Method group 9 extracted from DisplayControlsMixin."""

    def _on_view_sync_changed(
        self,
        modality_idx: int,
        zoom: float,
        pan_x: float,
        pan_y: float,
        t_idx: int = 0,
        z_idx: int = 0,
    ) -> None:
        """Apply linked zoom/pan updates and publish them through the signal hub.

        The view-sync manager emits T/Z indices alongside zoom/pan updates. They are
        accepted here for signal compatibility even though this handler currently
        only applies viewport changes.
        """
        panel_key = getattr(self, "_panel_sync_reverse", {}).get(modality_idx)
        if panel_key is None:
            return
        ax = None
        if getattr(self, "renderer", None) is not None:
            ax = self.renderer.axes.get(panel_key)
        if ax is None:
            return
        shape = getattr(self, "_last_display_shape", None)
        if shape is None:
            return
        if len(shape) < 2:
            return
        h, w = int(shape[0]), int(shape[1])
        span_x = max(1.0, w / max(0.1, zoom))
        span_y = max(1.0, h / max(0.1, zoom))
        x0 = max(0.0, min(pan_x, max(0.0, w - span_x)))
        y0 = max(0.0, min(pan_y, max(0.0, h - span_y)))
        self._suppress_limits = True
        try:
            ax.set_xlim(x0, x0 + span_x)
            ax.set_ylim(y0 + span_y, y0)
        finally:
            self._suppress_limits = False
        if getattr(self, "link_zoom", False):
            self._last_zoom_linked = ((x0, x0 + span_x), (y0 + span_y, y0))
        self._controller_view_refresh_hint = "view_sync"
        from phage_annotator.ui_qt.controls import display as display_module

        display_module.emit_view_changed(
            self.controller,
            change_type="view_sync",
            viewport={
                "panel_key": str(panel_key),
                "modality_idx": int(modality_idx),
                "zoom": float(zoom),
                "pan_x": float(x0),
                "pan_y": float(y0),
                "xlim": (float(x0), float(x0 + span_x)),
                "ylim": (float(y0 + span_y), float(y0)),
            },
        )
    def _on_modality_context_menu(self, pos: QtCore.QPoint) -> None:
        """Show context menu for modality renaming."""
        combo = self.sender()
        if combo is None:
            return
        
        menu = QtWidgets.QMenu(combo)
        rename_action = menu.addAction("Rename modality...")
        
        action = menu.exec_(combo.mapToGlobal(pos))
        
        if action == rename_action:
            self._show_rename_dialog(combo)
    def _show_rename_dialog(self, combo: QtWidgets.QComboBox) -> None:
        """Show rename dialog for the selected modality in combo."""
        from phage_annotator.ui_qt.dialogs.rename_modality_dialog import RenameModalityDialog
        
        current_idx = combo.currentIndex()
        current_name = combo.currentText()
        
        # Get all other modality names (for duplicate validation)
        existing_names = {combo.itemText(i) for i in range(combo.count())}
        existing_names.discard(current_name)
        
        dialog = RenameModalityDialog(current_name, existing_names, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_name = dialog.get_new_name()
            
            # Update the combo display
            combo.setItemText(current_idx, new_name)
            
            # Update the modality's display_name in the modality manager
            manager = getattr(self.controller.session_state, "modality_manager", None)
            if manager is not None:
                image_id = self.images[current_idx].id if current_idx < len(self.images) else None
                if image_id is not None:
                    for modality in manager.get_all_modalities():
                        if modality.image_id == image_id:
                            modality.display_name = new_name
                            break
            
            # Refresh UI to show updated names everywhere
            self._refresh_modality_display()
    def _refresh_modality_display(self) -> None:
        """Refresh all UI elements that display modality names."""
        visible = list(getattr(self, "_panel_sync_index", {}).keys())
        self._update_sync_list(visible)

        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
        
        # Refresh image to update any modality-related displays
        self._request_ui_refresh("display-controls")
    def _contrast_sync_scope(self) -> str:
        """Return contrast sync target mode."""
        if self._sync_follow_active_enabled():
            return "active_group"
        return "manual_group"
    def _contrast_target_panels(self) -> List[str]:
        """Resolve panels affected by contrast edits from selected sync group."""
        panel_keys = list(getattr(self, "_panel_sync_index", {}).keys())
        selected = [
            key
            for key in self._selected_sync_panels(default_to_all=True)
            if self._sync_mode_enabled_for_panel(str(key), "contrast")
        ]
        return selected if selected else panel_keys[:1]
    def _on_sync_scope_changed(self, _text: str) -> None:
        """Update sync hint text for current target mode."""
        hint = getattr(self, "sync_scope_hint_lbl", None)
        scope = self._contrast_sync_scope()
        selected_key = str(getattr(getattr(self, "sync_key_combo", None), "currentData", lambda: "")() or "")
        if hint is not None:
            if scope == "active_group":
                hint.setText("Sync target follows active canvas view group.")
            else:
                hint.setText(
                    f"Sync target uses Group {selected_key}."
                    if selected_key.isdigit()
                    else "Select a manual Sync Group."
                )
        self._update_sync_keys_hint()
    def _select_all_sync_views(self) -> None:
        """Compatibility no-op: legacy linked-view list was removed."""
        return
    def _clear_sync_view_selection(self) -> None:
        """Compatibility no-op: legacy linked-view list was removed."""
        return
