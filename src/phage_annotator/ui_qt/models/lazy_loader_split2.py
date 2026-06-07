"""Split definitions from lazy_loader.py."""

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
    "Table",
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
LAZY_TABLE_COLUMN_TABLE = 5
LAZY_TABLE_COLUMN_ANNOTATION_MODE = 6
LAZY_TABLE_COLUMN_ANNOTATION_FILE = 7
LAZY_TABLE_COLUMN_GROUP = 8
LAZY_TABLE_COLUMN_SYNC_CONTRAST = 9
LAZY_TABLE_COLUMN_SYNC_VIEW = 10
LAZY_TABLE_COLUMN_SYNC_TIME = 11
LAZY_TABLE_HEADER_TOOLTIPS = {
    LAZY_TABLE_COLUMN_SHOW: "Show or hide this panel on the canvas.",
    LAZY_TABLE_COLUMN_POINTS: "Show annotation points on this panel.",
    LAZY_TABLE_COLUMN_TABLE: "Open the annotation table for this panel row.",
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


from phage_annotator.ui_qt.models.lazy_loader_split1 import LazyTableRowSpec

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
        """Handle the allocate group helper flow."""
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
