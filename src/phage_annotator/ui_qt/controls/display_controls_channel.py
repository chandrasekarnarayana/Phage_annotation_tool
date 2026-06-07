"""Channel/panel selection, FOV navigation, and sync-role helpers."""

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


class DisplayControlsChannel:
    """Helpers for panel/channel selection, FOV navigation, and sync roles."""

    def _hist_region_widget(self):
        """Handle the hist region widget helper flow."""
        return getattr(self, "contrast_hist_region_combo", None) or getattr(self, "hist_region_combo", None)

    def _hist_scope_widget(self):
        """Handle the hist scope widget helper flow."""
        return getattr(self, "contrast_hist_scope_combo", None) or getattr(self, "hist_scope_combo", None)

    def _sync_role_for_panel(self, panel_key: str):
        """Return the lazy-table role key associated with a canvas panel."""
        key = str(panel_key or "").strip().lower()
        if not key:
            return None
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        modality = panel_map.get(key)
        if modality is not None:
            idx = int(getattr(modality, "idx", -1))
            if idx >= 0:
                return idx
        if key == "frame":
            return 0
        if key == "support":
            return 1
        if key in {"mean", "std"}:
            return f"builtin:{key}"
        if key.startswith("modality_"):
            try:
                return int(key.split("_", 1)[1])
            except Exception:
                return None
        return None

    def _sync_mode_enabled_for_panel(self, panel_key: str, mode_key: str) -> bool:
        """Return whether a panel participates in a given sync mode."""
        key = str(panel_key or "").strip()
        mode = str(mode_key or "").strip().lower()
        if not key or mode not in {"contrast", "zoom", "playback"}:
            return False
        role = self._sync_role_for_panel(key)
        if role is None:
            return True
        modes = self._lazy_sync_modes_state() if hasattr(self, "_lazy_sync_modes_state") else {}
        flags = dict(modes.get(role, {}) or {})
        return bool(flags.get(mode, True))

    def _sync_follow_active_enabled(self) -> bool:
        """Return whether sync target should follow active canvas view group."""
        combo = getattr(self, "sync_target_mode_combo", None)
        if combo is not None:
            return str(combo.currentData() or "manual").strip().lower() == "active"
        follow = getattr(self, "sync_follow_active_chk", None)
        return bool(follow is not None and follow.isChecked())

    def _sync_key_active_group(self) -> str:
        """Return the sync group key derived from current active view/target."""
        default_target = (
            self._default_panel_key() if hasattr(self, "_default_panel_key") else "modality_0"
        )
        active_key = str(getattr(self, "annotate_target", default_target)).strip().lower() or default_target
        return str(self._sync_key_for_panel(active_key) or "").strip()

    def _set_sync_key_combo_data(self, group_key: str) -> None:
        """Set sync-key combo selection without emitting change signals."""
        combo = getattr(self, "sync_key_combo", None)
        if combo is None:
            return
        group = str(group_key or "").strip()
        if not group:
            return
        idx = combo.findData(group)
        if idx < 0:
            return
        combo.blockSignals(True)
        try:
            combo.setCurrentIndex(idx)
        finally:
            combo.blockSignals(False)

    def _propagate_sync_to_modalities(
        self, source_image_id: int, panel: str, min_val: float, max_val: float
    ) -> None:
        """Propagate brightness/contrast changes to synced modalities."""
        try:
            mapping = self.controller.display_mapping
            sync_targets = mapping.propagate_sync_updates(source_image_id, panel)
            allowed_panels = set(self._contrast_target_panels())
            for target_image_id, target_panel in sync_targets:
                if allowed_panels and str(target_panel) not in allowed_panels:
                    continue
                target_image = None
                for img in self.images:
                    if img.id == target_image_id:
                        target_image = img
                        break
                if target_image is None or target_image.array is None:
                    continue
                target_mapping = self._get_display_mapping(
                    target_image_id, target_panel, target_image.array
                )
                target_mapping.set_window(min_val, max_val)
                self._sync_modality_display_settings(target_panel, target_mapping)
        except Exception as e:
            import sys
            print(f"Error propagating sync to modalities: {e}", file=sys.stderr)

    def _sync_base_modality_sources(self) -> None:
        """Keep modality-manager base sources aligned with UI primary/support selection."""
        manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is None or not self.images:
            return
        try:
            primary_mod = manager.get_modality(0)
            if primary_mod is not None:
                primary_mod.image_id = int(self.primary_image.id)
            support_mod = manager.get_modality(1)
            if support_mod is not None:
                support_mod.image_id = int(self.support_image.id)
        except Exception:
            return

    def _set_fov(self, idx: int) -> None:
        """Set fov for the current workflow."""
        if idx < 0 or idx >= len(self.images):
            return
        self.stop_playback_t()
        self._smlm_overlay = None
        self._smlm_overlay_extent = None
        self._smlm_results = []
        self._smlm_image_id = None
        self._deepstorm_overlay = None
        self._deepstorm_overlay_extent = None
        self._deepstorm_results = []
        self._deepstorm_image_id = None
        self._sr_overlay = None
        self._sr_overlay_extent = None
        self._particles_results = []
        self._particles_overlays = []
        self._particles_selected = None
        self._binary_view_mask = None
        self._binary_view_enabled = False
        self.current_image_idx = idx
        status_combo = getattr(self, "status_modality_combo", None)
        if status_combo is not None:
            status_combo.blockSignals(True)
            status_combo.setCurrentIndex(idx)
            status_combo.blockSignals(False)
        if self.threshold_panel is not None:
            cfg = self.controller.session_state.threshold_configs_by_image.get(idx)
            if cfg:
                self._apply_threshold_settings(cfg)
        self._sync_base_modality_sources()
        self.axis_mode_combo.setCurrentText(self.primary_image.interpret_3d_as)
        self._refresh_roi_manager()
        self._refresh_metadata_dock(self.primary_image.id)
        self._maybe_autoload_annotations(self.primary_image.id)
        if hasattr(self, "_sync_channel_panel_for_active_image"):
            self._sync_channel_panel_for_active_image()
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
        self._request_ui_refresh("display-controls", metadata=True)
        if hasattr(self, "_on_qc_image_changed"):
            self._on_qc_image_changed()

    def _set_primary_combo(
        self,
        idx: int,
        *,
        refresh_lazy_table: bool = True,
        schedule_prefetch: bool = True,
    ) -> None:
        """Set primary combo for the current workflow."""
        if 0 <= idx < len(self.images):
            self._set_fov(idx)
            if not refresh_lazy_table:
                self._lazy_apply_table_refresh = False
            self._refresh_prepare_setup_summary()
            if schedule_prefetch:
                self._schedule_adjacent_fov_prefetch()

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
        existing_names = {combo.itemText(i) for i in range(combo.count())}
        existing_names.discard(current_name)
        dialog = RenameModalityDialog(current_name, existing_names, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_name = dialog.get_new_name()
            combo.setItemText(current_idx, new_name)
            manager = getattr(self.controller.session_state, "modality_manager", None)
            if manager is not None:
                image_id = self.images[current_idx].id if current_idx < len(self.images) else None
                if image_id is not None:
                    for modality in manager.get_all_modalities():
                        if modality.image_id == image_id:
                            modality.display_name = new_name
                            break
            self._refresh_modality_display()

    def _refresh_modality_display(self) -> None:
        """Refresh all UI elements that display modality names."""
        visible = list(getattr(self, "_panel_sync_index", {}).keys())
        self._update_sync_list(visible)
        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        if hasattr(self, "_refresh_lazy_modality_table"):
            self._refresh_lazy_modality_table()
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
