"""Extracted method group 9 for UiExtrasMixin."""

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



class LazyLoaderStateMixin:
    """Method group 9 extracted from UiExtrasMixin."""

    def _queue_lazy_panel_auto_contrast(self, panel_key: str) -> None:
        """Remember one panel to auto-contrast after the next lazy refresh."""
        key = str(panel_key or "").strip().lower()
        if key:
            self._lazy_pending_auto_contrast_panel = key
    def _flush_lazy_canvas_refresh(self) -> None:
        """Apply queued table/tree changes to the canvas asynchronously."""
        if bool(getattr(self, "_lazy_apply_table_refresh", False)):
            # Rebuild browser + controls first, then render once from the latest state.
            self._refresh_lazy_modality_table()
            self._refresh_lazy_loader_tree()
        self._reconcile_lazy_loader_sources()
        self._refresh_annotation_view_controls()
        self._request_render_refresh("lazy-panel-flush")
        self._request_ui_refresh("lazy-panel-flush", table=True, status=True)
        pending_panel = str(getattr(self, "_lazy_pending_auto_contrast_panel", "") or "").strip().lower()
        self._lazy_pending_auto_contrast_panel = ""
        if pending_panel and hasattr(self, "_auto_contrast_panel"):
            try:
                self._auto_contrast_panel(pending_panel)
            except Exception:
                pass
        self._lazy_apply_table_refresh = False
        btn = getattr(self, "lazy_apply_btn", None)
        if btn is not None:
            btn.setEnabled(True)
    def _sync_mode_toolbutton(self, table, role_key, mode_key: str):
        """Create compact lazy-table sync mode toggle button (C/Z/P)."""
        mk = str(mode_key).strip().lower()
        label = {"contrast": "C", "zoom": "Z", "playback": "P"}.get(mk, "?")
        tooltip = {
            "contrast": "Sync contrast for this row's Sync Group",
            "zoom": "Sync zoom/pan for this row's Sync Group",
            "playback": "Sync playback for this row's Sync Group",
        }.get(mk, "Sync mode")
        btn = QtWidgets.QToolButton(table)
        btn.setText(label)
        btn.setCheckable(True)
        btn.setAutoRaise(False)
        btn.setFixedWidth(24)
        btn.setEnabled(True)  # Explicitly enable the button
        btn.setToolTip(tooltip)
        btn.setProperty("syncMode", mk)
        btn.setProperty("roleKey", role_key)
        btn.setChecked(bool(self._sync_modes_for_role(role_key).get(mk, True)))
        btn.toggled.connect(
            lambda checked, rk=role_key, mode=mk: self._set_sync_mode_for_role(
                rk, mode, bool(checked)
            )
        )
        return btn
    def _role_key_for_lazy_row(self, row: int):
        """Return role key (int or builtin:*) for a lazy-table row."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return None
        item = table.item(row, LAZY_TABLE_COLUMN_NAME)
        if item is None:
            return None
        role_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(role_data, str):
            role_text = str(role_data)
            if role_text.startswith("builtin:"):
                return role_text
            if role_text.startswith("modality_"):
                try:
                    return int(role_text.split("_", 1)[1])
                except Exception:
                    return None
            return role_text
        try:
            return int(role_data)
        except Exception:
            return None
    def _sync_mode_widgets_for_roles(self, role_keys: set, mode_key: str) -> None:
        """Apply mode-check state to all visible lazy-table rows for given role keys."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        mk = str(mode_key).strip().lower()
        if mk not in {"contrast", "zoom", "playback"}:
            return
        col = {
            "contrast": LAZY_TABLE_COLUMN_SYNC_CONTRAST,
            "zoom": LAZY_TABLE_COLUMN_SYNC_VIEW,
            "playback": LAZY_TABLE_COLUMN_SYNC_TIME,
        }[mk]
        role_set = set(role_keys or set())
        for row in range(table.rowCount()):
            rk = self._role_key_for_lazy_row(row)
            if rk not in role_set:
                continue
            widget = table.cellWidget(row, col)
            if widget is None:
                continue
            target_checked = bool(self._sync_modes_for_role(rk).get(mk, True))
            checkbox = self._lazy_checkbox_from_cell(widget) if hasattr(self, "_lazy_checkbox_from_cell") else None
            target = checkbox if checkbox is not None else widget
            target.blockSignals(True)
            try:
                if hasattr(target, "setChecked"):
                    target.setChecked(target_checked)
            finally:
                target.blockSignals(False)
    def _ensure_lazy_sync_group_keys(self) -> None:
        """Ensure every lazy modality/view row has a numeric sync key (default to 1)."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        row_specs = self._lazy_table_row_specs(manager)
        normalized_groups = normalize_lazy_sync_groups(
            row_specs,
            self._lazy_sync_groups_state(),
        )
        for role_key, group_key in normalized_groups.items():
            self._set_lazy_sync_group_for_role(role_key, group_key)
        self._ensure_lazy_sync_modes()
    def _add_lazy_modality_view(self, projection_key: str) -> None:
        """Add a new modality/view row and reflect it immediately on canvas."""
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system
        from phage_annotator.session.modality import ProjectionType

        proj_key = str(projection_key).strip().lower()
        active_image_id = int(getattr(getattr(self, "primary_image", None), "id", getattr(self, "current_image_idx", 0)))
        logger = get_action_logger()
        
        if proj_key in {"mean", "std"}:
            builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
            cfg = dict(builtin.get(proj_key, {}) or {})
            cfg["projection"] = proj_key
            cfg["name"] = str(cfg.get("name", "")).strip() or (
                "Mean Projection" if proj_key == "mean" else "Std Projection"
            )
            # Always bind newly added/edited built-in view to the active source.
            cfg["image_id"] = int(active_image_id)
            builtin[proj_key] = cfg
            self._lazy_builtin_views = builtin
            self._panel_visibility[proj_key] = True
            self._auto_bind_detected_annotation_for_panel(str(proj_key), active_image_id)
            self._ensure_lazy_sync_group_keys()
            self._request_lazy_canvas_refresh("lazy-add-builtin", refresh_table=True)
            logger.log_action(
                "add_builtin_projection",
                panel="lazy_loader",
                details={"projection": proj_key, "image_id": active_image_id}
            )
            return

        manager = ensure_modality_system(self.controller.session_state)
        proj = {
            "raw": ProjectionType.RAW,
            "mean": ProjectionType.MEAN,
            "std": ProjectionType.STD,
            "min": ProjectionType.MIN,
            "max": ProjectionType.MAX,
        }.get(proj_key, ProjectionType.RAW)
        try:
            modality = manager.add_modality(
                image_id=active_image_id,
                projection_type=proj,
            )
        except Exception as exc:
            self._status_error(f"Could not add modality/view: {exc}", source="ui_extra.lazy_loader")
            logger.log_action(
                "add_modality",
                panel="lazy_loader",
                details={"projection": proj_key, "image_id": active_image_id},
                error=str(exc)
            )
            return
        panel_key = self._panel_key_for_modality_idx(int(modality.idx))
        self._panel_visibility[str(panel_key)] = True
        self._auto_bind_detected_annotation_for_panel(str(panel_key), active_image_id)
        self._ensure_lazy_sync_group_keys()
        if hasattr(self, "_update_analysis_panel_modalities"):
            self._update_analysis_panel_modalities()
        self._queue_lazy_panel_auto_contrast(str(panel_key))
        self._request_lazy_canvas_refresh("lazy-add-view", refresh_table=True)
        logger.log_action(
            "add_modality",
            panel="lazy_loader",
            details={"modality_idx": modality.idx, "projection": proj_key, "image_id": active_image_id}
        )
