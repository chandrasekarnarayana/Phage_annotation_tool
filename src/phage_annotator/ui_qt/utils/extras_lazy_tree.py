"""Extracted method group 8 for UiExtrasMixin."""

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



class ExtrasLazyTreeMixin:
    """Method group 8 extracted from UiExtrasMixin."""

    def _refresh_lazy_loader_tree(self) -> None:
        """Rebuild the file/folder browser shown above the lazy modality table."""
        tree = getattr(self, "lazy_loader_tree", None)
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if tree is None or manifest is None:
            return
        self._sync_lazy_loader_sources()
        frame = manifest.to_frame()
        current = tree.currentItem()
        current_path = str(current.data(0, QtCore.Qt.ItemDataRole.UserRole)) if current is not None else ""
        info_icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView)
        controller = getattr(self, "controller", None)
        bindings = dict(getattr(getattr(controller, "session_state", None), "annotation_file_bindings", {}) or {})
        tree.blockSignals(True)
        tree.clear()
        items = {}
        for row in frame.itertuples(index=False):
            item = QtWidgets.QTreeWidgetItem([str(row.name)])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(row.path))
            item.setToolTip(0, str(row.path))
            image_ids = [int(v) for v in tuple(getattr(row, "image_ids", ()) or ())]
            has_auto_annotations = bool(
                controller is not None
                and any(bool(controller.annotation_entries_for_image(image_id)) for image_id in image_ids)
            )
            has_bound_annotations = any(
                int(binding.get("source_image_id", -1)) in image_ids and str(binding.get("path", "")).strip()
                for binding in bindings.values()
            )
            if has_auto_annotations or has_bound_annotations:
                item.setIcon(0, info_icon)
            items[str(row.path)] = item
            parent_path = str(row.parent_path) if row.parent_path else ""
            if parent_path and parent_path in items:
                items[parent_path].addChild(item)
            else:
                tree.addTopLevelItem(item)
        if current_path and current_path in items:
            tree.setCurrentItem(items[current_path])
        tree.expandAll()
        tree.blockSignals(False)
    def _on_lazy_loader_tree_item_changed(self, current, _previous) -> None:
        """Sync active image to the selected lazy-loader tree entry.

        This keeps Add Modality/Add View defaults aligned with the user's
        selected file/folder in the loader browser.
        """
        if current is None or not getattr(self, "images", None):
            return
        path = str(current.data(0, QtCore.Qt.ItemDataRole.UserRole) or "").strip()
        if not path:
            return
        manifest = getattr(self, "_lazy_loader_manifest", None)
        image_ids: list[int] = []
        if manifest is not None and hasattr(manifest, "subtree_image_ids"):
            try:
                image_ids = [int(v) for v in (manifest.subtree_image_ids(path) or [])]
            except Exception:
                image_ids = []
        if not image_ids:
            lookup = dict(getattr(self, "_lazy_loader_path_to_ids", {}) or {})
            image_ids = [int(v) for v in (lookup.get(path, []) or [])]
        if not image_ids:
            return
        active_id = int(getattr(getattr(self, "primary_image", None), "id", image_ids[0]))
        target_id = active_id if active_id in image_ids else int(image_ids[0])
        target_idx = int(self._image_index_for_id(target_id))
        if int(getattr(self, "current_image_idx", -1)) == target_idx:
            return
        self._set_primary_combo(target_idx, refresh_lazy_table=True, schedule_prefetch=False)
        if hasattr(self, "_append_log"):
            try:
                self._append_log(
                    f"[GUI] Lazy loader selection → image id={target_id} path={path}",
                    category="GUI",
                )
            except Exception:
                pass
        if hasattr(getattr(self, "recorder", None), "record"):
            try:
                self.recorder.record(
                    "gui_lazy_loader_select",
                    {"image_id": int(target_id), "path": str(path)},
                )
            except Exception:
                pass
        if hasattr(self, "_auto_contrast"):
            try:
                self._auto_contrast()
            except Exception:
                pass
    def _open_lazy_loader_dialog(self) -> None:
        """Open a small menu that can add files or folders through one button."""
        btn = getattr(self, "lazy_open_btn", None)
        if btn is None:
            return
        menu = QtWidgets.QMenu(btn)
        menu.addAction("Open image…", self._open_lazy_loader_files)
        menu.addAction("Open folder…", self._open_lazy_loader_folder)
        menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))
    def _open_lazy_loader_files(self) -> None:
        """Append selected TIFF files to the lazy loader."""
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            LAZY_LOADER_OPEN_FILES_TITLE,
            str(Path.home()),
            LAZY_LOADER_FILE_FILTER,
        )
        if not paths:
            return
        if hasattr(self, "_append_log"):
            self._append_log(f"[GUI] Open files in lazy loader ({len(paths)} selected)", category="GUI")
        self._add_paths_to_lazy_loader([Path(path) for path in paths])
    def _open_lazy_loader_folder(self) -> None:
        """Append TIFF files discovered in a selected folder to the lazy loader."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            LAZY_LOADER_OPEN_FOLDER_TITLE,
            str(Path.home()),
        )
        if not folder:
            return
        if hasattr(self, "_append_log"):
            self._append_log(f"[GUI] Open folder in lazy loader: {folder}", category="GUI")
        self._add_paths_to_lazy_loader([Path(folder)])
    def _add_paths_to_lazy_loader(self, paths: list[Path]) -> None:
        """Load files/folders into the session and show them in the lazy loader.

        The controller remains the owner of image/session state. This helper
        only discovers metadata, appends images through the controller, and
        requests an asynchronous UI refresh from the resulting state change.
        """
        if getattr(self, "controller", None) is None:
            return
        roots = [Path(path) for path in paths if path]
        if not roots:
            return
        path_to_ids = dict(getattr(self, "_lazy_loader_path_to_ids", {}) or {})
        new_images = []
        base_id = len(getattr(self, "images", []) or [])
        for root in roots:
            for file_path in iter_tiff_paths(root):
                key = str(file_path)
                if key in path_to_ids:
                    continue
                image = read_metadata(file_path)
                image.id = base_id + len(new_images)
                path_to_ids[key] = [int(image.id)]
                new_images.append(image)
        if new_images:
            self.controller.add_images(new_images)
            if hasattr(self, "_append_log"):
                self._append_log(
                    f"[GUI] Lazy loader added {len(new_images)} image(s)",
                    category="GUI",
                )
            if hasattr(getattr(self, "recorder", None), "record"):
                try:
                    self.recorder.record(
                        "gui_lazy_loader_add",
                        {
                            "roots": [str(p) for p in roots],
                            "added_images": int(len(new_images)),
                        },
                    )
                except Exception:
                    pass
        self._lazy_loader_path_to_ids = path_to_ids
        self._lazy_loader_manifest.add_paths(roots, path_to_ids)
        self._schedule_lazy_panel_sync("lazy-loader-open")
    def _undo_lazy_loader_removal(self) -> bool:
        """Restore the latest removed loader entry."""
        manifest = getattr(self, "_lazy_loader_manifest", None)
        if manifest is None:
            return False
        restored = manifest.undo_last_removal()
        if not restored:
            return False
        self._reconcile_lazy_loader_sources()
        self._schedule_lazy_panel_sync("lazy-loader-undo")
        self._status_success("Restored removed loader entry.", source="ui_extra.lazy_loader")
        return True
    def _reconcile_lazy_loader_sources(self) -> None:
        """Move selections away from files removed from the loader manifest."""
        visible_ids = self._lazy_loader_visible_image_ids()
        if not visible_ids:
            return
        fallback_id = int(visible_ids[0])
        if int(getattr(self, "current_image_idx", fallback_id)) not in visible_ids:
            self.current_image_idx = fallback_id
        if int(getattr(self, "support_image_idx", fallback_id)) not in visible_ids:
            self.support_image_idx = fallback_id
        if getattr(self, "controller", None) is None:
            return
        from phage_annotator.session.migration import ensure_modality_system

        manager = ensure_modality_system(self.controller.session_state)
        for modality in manager.get_all_modalities():
            if int(modality.image_id) not in visible_ids:
                modality.image_id = fallback_id
    def _request_lazy_canvas_refresh(self, reason: str, *, refresh_table: bool = True) -> None:
        """Queue a lazy-panel refresh on the Qt event loop.

        ``reason`` is retained for diagnostics and for future routing through
        the shared state core trigger stream.
        """
        self._lazy_apply_table_refresh = bool(getattr(self, "_lazy_apply_table_refresh", False) or refresh_table)
        self._lazy_refresh_reason = str(reason)
        if bool(getattr(self, "lazy_auto_update_chk", None) and self.lazy_auto_update_chk.isChecked()):
            self._lazy_apply_timer.start()
    def _commit_lazy_group_value(self, role_key, text: str) -> None:
        """Persist one edited sync-group value from the lazy table."""
        new_key = self._set_lazy_sync_group_for_role(role_key, text)
        table = getattr(self, "lazy_modality_table", None)
        if table is None:
            return
        for row in range(table.rowCount()):
            if self._role_key_for_lazy_row(row) != role_key:
                continue
            editor = table.cellWidget(row, LAZY_TABLE_COLUMN_GROUP)
            if editor is not None and hasattr(editor, "setText"):
                editor.blockSignals(True)
                try:
                    editor.setText(new_key)
                finally:
                    editor.blockSignals(False)
            break
        self._status_info("Sync group updated.", source="ui_extra.lazy_loader")
