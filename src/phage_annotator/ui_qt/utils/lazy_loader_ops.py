"""Extracted method group 10 for UiExtrasMixin."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.services.action_logger import get_action_logger

from phage_annotator.ui_qt.models.lazy_loader import (
    LAZY_LOADER_FILE_FILTER,
    LAZY_LOADER_OPEN_FILES_TITLE,
    LAZY_LOADER_OPEN_FOLDER_TITLE,
    LAZY_TABLE_COLUMN_GROUP,
    LAZY_TABLE_COLUMN_NAME,
    LAZY_TABLE_COLUMN_ANNOTATION_FILE,
    LAZY_TABLE_COLUMN_ANNOTATION_MODE,
    LAZY_TABLE_COLUMN_POINTS,
    LAZY_TABLE_COLUMN_PROJECTION,
    LAZY_TABLE_COLUMN_SHOW,
    LAZY_TABLE_COLUMN_SOURCE,
    LAZY_TABLE_COLUMN_SYNC_CONTRAST,
    LAZY_TABLE_COLUMN_SYNC_TIME,
    LAZY_TABLE_COLUMN_SYNC_VIEW,
    LAZY_TABLE_COLUMN_TABLE,
    LazyTableRowSpec,
    normalize_lazy_sync_groups,
    iter_tiff_paths,
)
from phage_annotator.ui_qt.utils.ui_extra_annotations import (
    UiAnnotationViewsMixin,
    _LogicalVisibilityLabel,
)
from phage_annotator.ui_qt.utils.ui_extra_refresh import UiRefreshMixin
from phage_annotator.ui_qt.utils.ui_extra_tooltips import UiTooltipMixin
from phage_annotator.ui_qt.utils.iconography import right_sidebar_icon, tool_icon, workflow_sidebar_icon
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.utils.sidebar_manager import SidebarLayoutConfig, SidebarManager
from phage_annotator.tools import Tool, ToolCallbacks, ToolRouter

PRIMARY_RIGHT_SIDEBAR_PANELS = (
    "annotations",
    "review_queue",
    "advanced_settings",
    "advanced_analysis",
    "qc_issues",
)
SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS = (
    "status_details",
)
ALL_RIGHT_SIDEBAR_PANELS = PRIMARY_RIGHT_SIDEBAR_PANELS + SUPPLEMENTAL_RIGHT_SIDEBAR_PANELS



class LazyLoaderOpsMixin:
    """Method group 10 extracted from UiExtrasMixin."""

    def _remove_selected_lazy_modality_view(self) -> None:
        """Remove the selected modality/view row from the lazy table."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        row = int(table.currentRow())
        role_key = self._role_key_for_lazy_row(row)
        if role_key is None:
            self._status_warning("Select a modality/view row to remove.", source="ui_extra.lazy_loader")
            return

        removed_name = ""
        if isinstance(role_key, str) and role_key.startswith("builtin:"):
            panel_key = str(role_key).split(":", 1)[1]
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            cfg = dict(builtin.get(panel_key, {}) or {})
            removed_name = str(cfg.get("name", panel_key.title()))
            if panel_key not in builtin:
                return
            builtin.pop(panel_key, None)
            self._lazy_builtin_views = builtin
            self._panel_visibility.pop(panel_key, None)
            self._annotation_panel_visibility.pop(panel_key, None)
        else:
            try:
                modality_idx = int(role_key)
            except Exception:
                self._status_warning("Could not resolve the selected modality/view.", source="ui_extra.lazy_loader")
                return
            from phage_annotator.session.migration import ensure_modality_system

            manager = ensure_modality_system(self.controller.session_state)
            modalities = list(manager.get_all_modalities() or [])
            modality = next((m for m in modalities if int(getattr(m, "idx", -1)) == modality_idx), None)
            if modality is None:
                return
            if len(modalities) <= 1:
                self._status_warning(
                    "At least one modality/view must remain available.",
                    source="ui_extra.lazy_loader",
                )
                return
            removed_name = str(getattr(modality, "display_name", f"Modality {modality_idx + 1}"))
            if not manager.remove_modality(modality_idx):
                return
            panel_key = self._panel_key_for_modality_idx(modality_idx)
            self._panel_visibility.pop(panel_key, None)
            self._annotation_panel_visibility.pop(panel_key, None)

        self._ensure_lazy_sync_group_keys()
        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        self._request_lazy_canvas_refresh("lazy-remove-view", refresh_table=True)
        self._status_success(
            f"Removed modality/view: {removed_name or 'selected row'}",
            source="ui_extra.lazy_loader",
        )
    def _clear_lazy_loader_sources(self) -> None:
        """Reset the lazy-loader source list back to the current primary image only."""
        if not getattr(self, "images", None):
            return
        self.stop_playback_t()
        self._cancel_all_jobs()
        self._bump_job_generation()
        keep_idx = int(getattr(self, "current_image_idx", 0))
        self.controller.retain_single_image(keep_idx)
        self.current_image_idx = 0
        self.support_image_idx = 0
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None or not getattr(self, "images", None):
            return
        keep_img = self.images[0]
        keep_img.id = 0
        keep_path = Path(str(getattr(keep_img, "path", "")))
        if not keep_path:
            return
        path_to_ids = {str(keep_path): [int(getattr(keep_img, "id", 0))]}
        self._lazy_loader_path_to_ids = path_to_ids
        manifest.clear()
        manifest.add_paths([keep_path], path_to_ids)
        self.roi_manager.rois_by_image = {0: self.roi_manager.list_rois(keep_idx)}
        self.roi_manager.set_active(self.roi_manager.active_roi_id)
        self._refresh_roi_manager()
        self._refresh_lazy_loader_tree()
        self._request_lazy_canvas_refresh("lazy-loader-clear", refresh_table=True)
        self._status_info("Cleared previous loader sources.", source="ui_extra.lazy_loader")
    def _open_annotation_table_for_panel(self, panel_key: str) -> None:
        """Open the annotation table focused on one lazy-loader panel context."""
        key = str(panel_key or "").strip()
        if not key:
            return
        try:
            self.annotate_target = key
        except Exception:
            pass
        self.open_panel("annotations", reason="lazy_loader:annotation_table")
        if getattr(self, "annotation_table_mode_combo", None) is not None:
            idx = self.annotation_table_mode_combo.findData("truth")
            if idx >= 0:
                self.annotation_table_mode_combo.setCurrentIndex(idx)
        if hasattr(self, "_refresh_table"):
            self._refresh_table()
    def _on_lazy_modality_item_changed(self, item) -> None:
        """Handle lazy-table inline rename and propagate to canvas titles."""
        if item is None or getattr(self, "controller", None) is None:
            return
        col = int(item.column())
        if col not in (LAZY_TABLE_COLUMN_NAME, LAZY_TABLE_COLUMN_GROUP):
            return
        from phage_annotator.session.migration import ensure_modality_system

        role_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        role_text = str(role_data)
        if role_text.startswith("builtin:"):
            panel_key = role_text.split(":", 1)[1]
            if col == LAZY_TABLE_COLUMN_GROUP:
                new_key = self._set_lazy_sync_group_for_role(
                    f"builtin:{panel_key}",
                    item.text(),
                )
                item.setText(new_key)
                self._status_info("Sync group updated.", source="ui_extra.lazy_loader")
                return
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            cfg = dict(builtin.get(panel_key, {}) or {})
            cfg["name"] = str(item.text()).strip() or cfg.get("name", panel_key.title())
            builtin[panel_key] = cfg
            self._lazy_builtin_views = builtin
            self._request_lazy_canvas_refresh("lazy-builtin-rename", refresh_table=False)
            return

        modality_idx = int(role_data)
        if col == LAZY_TABLE_COLUMN_GROUP:
            new_key = self._set_lazy_sync_group_for_role(
                int(modality_idx),
                item.text(),
            )
            item.setText(new_key)
            self._status_info("Sync group updated.", source="ui_extra.lazy_loader")
            return
        new_name = str(item.text()).strip()
        if not new_name:
            return
        manager = ensure_modality_system(self.controller.session_state)
        try:
            manager.rename_modality(modality_idx, new_name)
        except Exception as exc:
            self._status_error(f"Rename rejected: {exc}", source="ui_extra.lazy_loader")
            return
        self._request_lazy_canvas_refresh("lazy-modality-rename", refresh_table=False)
    def _apply_lazy_group_sync_selection(self, group_key: str) -> None:
        """Set manual sync target to a shared lazy-table group key."""
        group = str(group_key or "").strip()
        combo = getattr(self, "sync_key_combo", None)
        if not group or combo is None:
            return
        idx = combo.findData(group)
        if idx < 0:
            return
        mode_combo = getattr(self, "sync_target_mode_combo", None)
        if mode_combo is not None:
            mode_combo.blockSignals(True)
            mode_combo.setCurrentIndex(max(0, mode_combo.findData("manual")))
            mode_combo.blockSignals(False)
        if getattr(self, "sync_follow_active_chk", None) is not None:
            self.sync_follow_active_chk.setChecked(False)
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
    def _on_lazy_auto_update_toggled(self, checked: bool) -> None:
        """Handle auto-update checkbox toggle and persist preference."""
        if hasattr(self, "_settings"):
            self._settings.setValue("lazyModalityAutoUpdate", bool(checked))
        if bool(checked):
            self._request_lazy_canvas_refresh("lazy-auto-update", refresh_table=True)
    def _apply_lazy_pending_updates(self) -> None:
        """Apply lazy modality table changes to canvas (triggered by Update Canvas button or auto-update)."""
        self._lazy_apply_table_refresh = True
        self._flush_lazy_canvas_refresh()
    def _on_lazy_modality_source_changed(self, modality_idx: int, image_id: int) -> None:
        """Handle the on lazy modality source changed helper flow."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        modality = manager.get_modality(int(modality_idx))
        if modality is None:
            return
        modality.image_id = int(image_id)
        panel_key = self._panel_key_for_modality_idx(int(modality_idx))
        self.controller.clear_annotation_binding_for_panel(
            panel_key,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._auto_bind_detected_annotation_for_panel(panel_key, int(image_id))
        self._queue_lazy_panel_auto_contrast(panel_key)
        self._request_lazy_canvas_refresh("lazy-source-change", refresh_table=False)
        self._flush_lazy_canvas_refresh()
