"""Extracted method group 7 for UiExtrasMixin."""

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



class ExtrasLazyModalityMixin:
    """Method group 7 extracted from UiExtrasMixin."""

    def _refresh_lazy_modality_table(self) -> None:
        """Populate lazy-loading modality/view table."""
        table = getattr(self, "lazy_modality_table", None)
        if table is None or getattr(self, "controller", None) is None:
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
        row_specs = self._lazy_table_row_specs(manager)
        table.blockSignals(True)
        table.setRowCount(0)
        for row_spec in row_specs:
            self._insert_lazy_table_row(table, row_spec)

        # Remove stale dynamic panel visibility keys no longer represented by modalities.
        valid_dynamic_keys = {
            self._panel_key_for_modality_idx(int(modality.idx))
            for modality in manager.get_all_modalities()
            if int(modality.idx) >= 2
        }
        for key in list(dict(getattr(self, "_panel_visibility", {}) or {}).keys()):
            k = str(key)
            if k.startswith("modality_") and k not in valid_dynamic_keys:
                self._panel_visibility.pop(k, None)

        table.blockSignals(False)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setColumnWidth(LAZY_TABLE_COLUMN_SHOW, 44)
        table.setColumnWidth(LAZY_TABLE_COLUMN_POINTS, 44)
        table.setColumnWidth(LAZY_TABLE_COLUMN_NAME, 220)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SOURCE, 220)
        table.setColumnWidth(LAZY_TABLE_COLUMN_PROJECTION, 130)
        table.setColumnWidth(LAZY_TABLE_COLUMN_TABLE, 76)
        table.setColumnWidth(LAZY_TABLE_COLUMN_ANNOTATION_MODE, 120)
        table.setColumnWidth(LAZY_TABLE_COLUMN_ANNOTATION_FILE, 120)
        table.setColumnWidth(LAZY_TABLE_COLUMN_GROUP, 84)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SYNC_CONTRAST, 86)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SYNC_VIEW, 88)
        table.setColumnWidth(LAZY_TABLE_COLUMN_SYNC_TIME, 84)
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        # Update sync key selector dropdown to show all available group keys
        if hasattr(self, "_update_sync_key_selector"):
            try:
                self._update_sync_key_selector()
            except Exception:
                pass
    def _panel_key_for_modality_idx(self, modality_idx: int) -> str:
        """Map modality index to panel key used by renderer/sync list."""
        idx = int(modality_idx)
        if idx == 0:
            return "frame"
        if idx == 1:
            return "support"
        return f"modality_{idx}"
    def _next_numeric_sync_key(self, groups: dict) -> str:
        """Return next available positive integer sync key as string."""
        used = set()
        for value in (groups or {}).values():
            text = str(value or "").strip()
            if text.isdigit():
                used.add(int(text))
        key = 1
        while key in used:
            key += 1
        return str(key)
    def _normalized_lazy_sync_group_key(self, group_key: object, groups: dict | None = None) -> str:
        """Return a valid numeric sync-group key."""
        text = str(group_key or "").strip()
        if text.isdigit():
            return text
        return self._next_numeric_sync_key(dict(groups or self._lazy_sync_groups_state() or {}))
    def _lazy_sync_groups_state(self) -> dict:
        """Return controller-owned lazy sync groups."""
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "get_lazy_sync_groups"):
            return dict(controller.get_lazy_sync_groups() or {})
        return {}
    def _lazy_sync_modes_state(self) -> dict:
        """Return controller-owned lazy sync modes."""
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "get_lazy_sync_modes"):
            return dict(controller.get_lazy_sync_modes() or {})
        return {}
    def _lazy_sync_group_for_role(self, role_key) -> str:
        """Return the current normalized sync group for one lazy-table role."""
        groups = self._lazy_sync_groups_state()
        return self._normalized_lazy_sync_group_key(groups.get(role_key, ""), groups)
    def _set_lazy_sync_group_for_role(self, role_key, group_key: object) -> str:
        """Set lazy sync-group membership through one centralized mutation path."""
        groups = self._lazy_sync_groups_state()
        normalized = self._normalized_lazy_sync_group_key(group_key, groups)
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "set_lazy_sync_group"):
            normalized = str(controller.set_lazy_sync_group(role_key, normalized))
            groups = self._lazy_sync_groups_state()
        else:
            return normalized
        self._ensure_lazy_sync_modes()
        self._apply_lazy_group_sync_selection(normalized)
        if hasattr(self, "_update_sync_key_selector"):
            try:
                self._update_sync_key_selector()
            except Exception:
                pass
        if hasattr(self, "_update_sync_keys_hint"):
            try:
                self._update_sync_keys_hint()
            except Exception:
                pass
        return normalized
    def _sync_modes_for_role(self, role_key) -> dict[str, bool]:
        """Return sync mode flags for a modality/view role key."""
        modes = self._lazy_sync_modes_state()
        current = dict(modes.get(role_key, {}) or {})
        normalized = {
            "contrast": bool(current.get("contrast", True)),
            "zoom": bool(current.get("zoom", True)),
            "playback": bool(current.get("playback", True)),
        }
        return normalized
    def _set_sync_mode_for_role(self, role_key, mode_key: str, enabled: bool) -> None:
        """Update one sync mode flag for a single row."""
        key = str(mode_key).strip().lower()
        if key not in {"contrast", "zoom", "playback"}:
            return
        modes = self._lazy_sync_modes_state()
        controller = getattr(self, "controller", None)
        row_modes = dict(modes.get(role_key, {}) or {})
        row_modes[key] = bool(enabled)
        normalized = {
            "contrast": bool(row_modes.get("contrast", True)),
            "zoom": bool(row_modes.get("zoom", True)),
            "playback": bool(row_modes.get("playback", True)),
        }
        if controller is not None and hasattr(controller, "set_lazy_sync_mode"):
            modes[role_key] = dict(controller.set_lazy_sync_mode(role_key, key, bool(enabled)) or {})
        else:
            modes[role_key] = normalized
        self._sync_mode_widgets_for_roles({role_key}, key)
        if hasattr(self, "_on_sync_mode_changed"):
            self._on_sync_mode_changed()
        self._request_ui_refresh("lazy-sync-group", status=True)
    def _ensure_lazy_sync_modes(self) -> None:
        """Ensure each lazy row has explicit sync mode flags."""
        modes = self._lazy_sync_modes_state()
        groups = self._lazy_sync_groups_state()
        if getattr(self, "controller", None) is not None:
            from phage_annotator.session.migration import ensure_modality_system

            manager = ensure_modality_system(self.controller.session_state)
            for modality in manager.get_all_modalities():
                role_key = int(modality.idx)
                current = dict(modes.get(role_key, {}) or {})
                modes[role_key] = {
                    "contrast": bool(current.get("contrast", True)),
                    "zoom": bool(current.get("zoom", True)),
                    "playback": bool(current.get("playback", True)),
                }
        for builtin_key in ("builtin:support", "builtin:mean", "builtin:std"):
            if builtin_key not in groups:
                continue
            current = dict(modes.get(builtin_key, {}) or {})
            modes[builtin_key] = {
                "contrast": bool(current.get("contrast", True)),
                "zoom": bool(current.get("zoom", True)),
                "playback": bool(current.get("playback", True)),
            }
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "set_lazy_sync_mode"):
            for role_key, state in modes.items():
                for mode_key, enabled in dict(state or {}).items():
                    controller.set_lazy_sync_mode(role_key, str(mode_key), bool(enabled))
    def _lazy_loader_focus_active(self) -> bool:
        """Return True when the lazy loader tree/table owns keyboard focus."""
        focused = QtWidgets.QApplication.focusWidget()
        for widget_name in ("lazy_loader_tree", "lazy_modality_table", "lazy_open_btn", "lazy_remove_btn"):
            widget = getattr(self, widget_name, None)
            if widget is None:
                continue
            if focused is widget or widget.isAncestorOf(focused):
                return True
        return False
    def _schedule_lazy_panel_sync(self, reason: str = "state-changed") -> None:
        """Schedule a lazy-panel sync from controller state.

        This keeps UI refreshes event-driven and coalesced on the Qt loop so
        rapid state changes do not force synchronous widget rebuild cascades.
        """
        self._request_lazy_canvas_refresh(reason, refresh_table=True)
    def _sync_lazy_loader_sources(self) -> None:
        """Ensure current session images appear in the loader manifest."""
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None:
            return
        current_paths = {str(getattr(img, "path", "")) for img in getattr(self, "images", []) or []}
        if not manifest.roots:
            roots = [Path(path) for path in sorted(path for path in current_paths if path)]
            manifest.add_paths(roots, getattr(self, "_lazy_loader_path_to_ids", {}) or {})
        else:
            missing = [Path(path) for path in sorted(current_paths) if path and not manifest.contains(path)]
            if missing:
                manifest.add_paths(missing, getattr(self, "_lazy_loader_path_to_ids", {}) or {})
    def _lazy_loader_visible_image_ids(self) -> list[int]:
        """Return image ids exposed by the loader manifest."""
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None:
            return [int(getattr(img, "id", -1)) for img in getattr(self, "images", []) or []]
        self._sync_lazy_loader_sources()
        visible = manifest.visible_image_ids()
        if visible:
            return visible
        return [int(getattr(img, "id", -1)) for img in getattr(self, "images", []) or []]
    def _lazy_loader_source_images(self) -> list:
        """Return image objects that are still available to the loader controls."""
        visible_ids = set(self._lazy_loader_visible_image_ids())
        images = list(getattr(self, "images", []) or [])
        filtered = [img for img in images if int(getattr(img, "id", -1)) in visible_ids]
        # Recovery path: if manifest ids become stale after image-id remapping,
        # keep controls usable by falling back to all loaded images.
        return filtered if filtered else images
