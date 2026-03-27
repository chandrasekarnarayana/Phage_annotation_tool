"""State helpers for the lazy loader panel.

This module keeps the loader tree representation separate from the Qt widgets.
The GUI consumes a pandas DataFrame for responsive table/tree rebuilding and
maintains a small undo history for entry removal.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


TIFF_SUFFIXES = (".tif", ".tiff", ".ome.tiff")
LAZY_LOADER_FILE_FILTER = "TIFF Images (*.tif *.tiff *.ome.tiff)"
LAZY_LOADER_TREE_HEADER = "Loaded Files / Folders"
LAZY_LOADER_OPEN_FILES_TITLE = "Open Image Files"
LAZY_LOADER_OPEN_FOLDER_TITLE = "Open Folder"
LAZY_TABLE_HEADERS = (
    "Show",
    "Ann",
    "Panel",
    "Source Image",
    "Projection",
    "Owner",
    "File",
    "Group",
    "Contrast",
    "Zoom/Pan",
    "Playback",
)
LAZY_TABLE_COLUMN_SHOW = 0
LAZY_TABLE_COLUMN_POINTS = 1
LAZY_TABLE_COLUMN_NAME = 2
LAZY_TABLE_COLUMN_SOURCE = 3
LAZY_TABLE_COLUMN_PROJECTION = 4
LAZY_TABLE_COLUMN_ANNOTATION_MODE = 5
LAZY_TABLE_COLUMN_ANNOTATION_FILE = 6
LAZY_TABLE_COLUMN_GROUP = 7
LAZY_TABLE_COLUMN_SYNC_CONTRAST = 8
LAZY_TABLE_COLUMN_SYNC_VIEW = 9
LAZY_TABLE_COLUMN_SYNC_TIME = 10
LAZY_TABLE_HEADER_TOOLTIPS = {
    LAZY_TABLE_COLUMN_SHOW: "Show or hide this panel on the canvas.",
    LAZY_TABLE_COLUMN_POINTS: "Show annotation points on this panel.",
    LAZY_TABLE_COLUMN_NAME: "Panel label shown in the canvas and controls.",
    LAZY_TABLE_COLUMN_SOURCE: "Source image used to render this panel.",
    LAZY_TABLE_COLUMN_PROJECTION: "Projection applied to the source image for this panel.",
    LAZY_TABLE_COLUMN_ANNOTATION_MODE: "Annotation ownership for this row: independent, shared with source, or read-only.",
    LAZY_TABLE_COLUMN_ANNOTATION_FILE: "Annotation file actions for this row context.",
    LAZY_TABLE_COLUMN_GROUP: "Sync group identifier. Rows with the same group share contrast, zoom/pan, and playback sync settings.",
    LAZY_TABLE_COLUMN_SYNC_CONTRAST: "Contrast sync for all rows in the same group.",
    LAZY_TABLE_COLUMN_SYNC_VIEW: "Zoom/pan sync for all rows in the same group.",
    LAZY_TABLE_COLUMN_SYNC_TIME: "Playback/time sync for all rows in the same group.",
}


@dataclass(frozen=True)
class LazyLoaderEntry:
    """Immutable tree entry shown in the lazy loader browser."""

    path: str
    name: str
    kind: str
    parent_path: Optional[str]
    image_ids: Tuple[int, ...] = ()


@dataclass(frozen=True)
class LazyTableRowSpec:
    """Derived lazy-table row rendered from controller/view state."""

    role_key: Any
    panel_key: str
    panel_name: str
    source_image_id: int
    projection_key: str
    group_key: str
    visible: bool
    show_points: bool
    sync_contrast: bool
    sync_view: bool
    sync_time: bool
    annotation_mode: str = "independent"
    annotation_writable: bool = True
    annotation_context_key: str = ""
    annotation_binding_path: str = ""
    projection_editable: bool = True


def iter_tiff_paths(root: Path) -> List[Path]:
    """Return TIFF files contained in ``root``.

    Direct file selections are returned unchanged when they are TIFFs. Directory
    selections are scanned recursively and sorted for stable UI ordering.
    """
    path = Path(root)
    if path.is_file():
        suffix = path.name.lower()
        return [path] if suffix.endswith(TIFF_SUFFIXES) else []
    if not path.is_dir():
        return []
    files = [candidate for candidate in path.rglob("*") if candidate.is_file()]
    return sorted(
        file_path
        for file_path in files
        if file_path.name.lower().endswith(TIFF_SUFFIXES)
    )


def normalize_lazy_sync_groups(
    row_specs: Sequence[LazyTableRowSpec],
    groups: Dict[Any, Any],
) -> Dict[Any, str]:
    """Return normalized numeric sync groups for the current lazy-table rows.

    The grouping policy is intentionally source-centric:
    rows that render from the same source image default to the same sync group,
    which is scientifically more predictable than assigning a new group to each
    projection row. Existing numeric user assignments are preserved.
    """
    normalized = {
        role_key: str(value).strip()
        for role_key, value in dict(groups or {}).items()
        if str(value).strip()
    }
    assigned_by_source: Dict[int, str] = {}
    next_group = 1

    def _allocate_group() -> str:
        nonlocal next_group
        while str(next_group) in assigned_by_source.values():
            next_group += 1
        group_key = str(next_group)
        next_group += 1
        return group_key

    for row in row_specs:
        existing = str(normalized.get(row.role_key, "")).strip()
        if existing.isdigit():
            assigned_by_source.setdefault(int(row.source_image_id), existing)
            continue
        source_id = int(row.source_image_id)
        group_key = assigned_by_source.get(source_id)
        if group_key is None:
            group_key = _allocate_group()
            assigned_by_source[source_id] = group_key
        normalized[row.role_key] = group_key
    return normalized


class LazyLoaderManifest:
    """Tree model for the lazy loader browser with one-step removal undo."""

    def __init__(self) -> None:
        self._entries: Dict[str, LazyLoaderEntry] = {}
        self._roots: List[str] = []
        self._undo_stack: List[Tuple[List[LazyLoaderEntry], List[str], Optional[str]]] = []

    @property
    def roots(self) -> List[str]:
        """Return root paths in display order."""
        return list(self._roots)

    def clear(self) -> None:
        """Reset the manifest and its undo history."""
        self._entries.clear()
        self._roots.clear()
        self._undo_stack.clear()

    def add_paths(
        self,
        roots: Sequence[Path],
        path_to_image_ids: Dict[str, Sequence[int]],
    ) -> None:
        """Add file or directory roots to the manifest."""
        for root in roots:
            root_path = str(Path(root))
            if root_path not in self._roots:
                self._roots.append(root_path)
            self._add_root(Path(root), path_to_image_ids)

    def remove_path(self, path: str) -> bool:
        """Remove a selected entry and remember it for undo."""
        normalized = str(Path(path))
        if normalized not in self._entries:
            return False
        rows = self._collect_subtree(normalized)
        removed_entries = [self._entries.pop(key) for key in rows]
        removed_roots = [root for root in self._roots if root in rows]
        self._roots = [root for root in self._roots if root not in rows]
        parent_path = removed_entries[0].parent_path if removed_entries else None
        self._undo_stack.append((removed_entries, removed_roots, parent_path))
        return True

    def undo_last_removal(self) -> Optional[str]:
        """Restore the most recently removed subtree.

        Returns the root path of the restored subtree when an undo occurs.
        """
        if not self._undo_stack:
            return None
        removed_entries, removed_roots, _parent = self._undo_stack.pop()
        for entry in sorted(removed_entries, key=lambda item: (item.parent_path is not None, item.path)):
            self._entries[entry.path] = entry
        for root in removed_roots:
            if root not in self._roots:
                self._roots.append(root)
        return removed_entries[0].path if removed_entries else None

    def contains(self, path: str) -> bool:
        """Return whether a path is visible in the manifest."""
        return str(Path(path)) in self._entries

    def visible_image_ids(self) -> List[int]:
        """Return active image ids in tree order."""
        frame = self.to_frame()
        if frame.empty:
            return []
        ids: List[int] = []
        for values in frame["image_ids"]:
            for image_id in values:
                if image_id not in ids:
                    ids.append(int(image_id))
        return ids

    def subtree_image_ids(self, path: str) -> List[int]:
        """Return image ids contributed by one path and its descendants."""
        ids: List[int] = []
        for entry_path in self._collect_subtree(str(Path(path))):
            entry = self._entries.get(entry_path)
            if entry is None:
                continue
            for image_id in entry.image_ids:
                if int(image_id) not in ids:
                    ids.append(int(image_id))
        return ids

    def to_frame(self) -> pd.DataFrame:
        """Render the manifest into a pandas table for the UI layer."""
        rows: List[dict] = []
        for root in self._roots:
            self._append_rows(root, rows, depth=0)
        return pd.DataFrame(rows, columns=["path", "name", "kind", "parent_path", "depth", "image_ids"])

    def _append_rows(self, path: str, rows: List[dict], depth: int) -> None:
        entry = self._entries.get(path)
        if entry is None:
            return
        rows.append(
            {
                "path": entry.path,
                "name": entry.name,
                "kind": entry.kind,
                "parent_path": entry.parent_path,
                "depth": int(depth),
                "image_ids": tuple(entry.image_ids),
            }
        )
        for child_path in self._child_paths(path):
            self._append_rows(child_path, rows, depth + 1)

    def _child_paths(self, parent_path: str) -> List[str]:
        children = [
            entry.path
            for entry in self._entries.values()
            if entry.parent_path == parent_path
        ]
        return sorted(children, key=lambda value: (self._entries[value].kind != "dir", value.lower()))

    def _add_root(
        self,
        root: Path,
        path_to_image_ids: Dict[str, Sequence[int]],
    ) -> None:
        root = Path(root)
        if root.is_dir():
            self._entries[str(root)] = LazyLoaderEntry(
                path=str(root),
                name=root.name or str(root),
                kind="dir",
                parent_path=None,
            )
            for file_path in iter_tiff_paths(root):
                self._ensure_parent_dirs(file_path, root)
                self._entries[str(file_path)] = LazyLoaderEntry(
                    path=str(file_path),
                    name=file_path.name,
                    kind="file",
                    parent_path=str(file_path.parent),
                    image_ids=tuple(int(v) for v in path_to_image_ids.get(str(file_path), ())),
                )
        else:
            self._entries[str(root)] = LazyLoaderEntry(
                path=str(root),
                name=root.name,
                kind="file",
                parent_path=None,
                image_ids=tuple(int(v) for v in path_to_image_ids.get(str(root), ())),
            )

    def _ensure_parent_dirs(self, file_path: Path, root: Path) -> None:
        current = file_path.parent
        root_str = str(root)
        stack: List[Path] = []
        while str(current) != root_str and str(current) not in self._entries:
            stack.append(current)
            if current.parent == current:
                break
            current = current.parent
        parent_path = root_str
        for directory in reversed(stack):
            directory_str = str(directory)
            self._entries[directory_str] = LazyLoaderEntry(
                path=directory_str,
                name=directory.name,
                kind="dir",
                parent_path=parent_path,
            )
            parent_path = directory_str

    def _collect_subtree(self, path: str) -> List[str]:
        rows = [path]
        for child in self._child_paths(path):
            rows.extend(self._collect_subtree(child))
        return rows
