"""State helpers for the lazy loader panel.

This module keeps the loader tree representation separate from the Qt widgets.
The GUI consumes a pandas DataFrame for responsive table/tree rebuilding and
maintains a small undo history for entry removal.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from phage_annotator.ui_qt.models.lazy_loader_split1 import (
    LAZY_TABLE_COLUMN_ANNOTATION_FILE,
    LAZY_TABLE_COLUMN_ANNOTATION_MODE,
    LAZY_TABLE_COLUMN_GROUP,
    LAZY_TABLE_COLUMN_NAME,
    LAZY_TABLE_COLUMN_POINTS,
    LAZY_TABLE_COLUMN_PROJECTION,
    LAZY_TABLE_COLUMN_SHOW,
    LAZY_TABLE_COLUMN_SOURCE,
    LAZY_TABLE_COLUMN_SYNC_CONTRAST,
    LAZY_TABLE_COLUMN_SYNC_TIME,
    LAZY_TABLE_COLUMN_SYNC_VIEW,
    LAZY_TABLE_COLUMN_TABLE,
    LAZY_TABLE_HEADER_TOOLTIPS,
    LAZY_TABLE_HEADERS,
    LazyLoaderEntry,
    LazyLoaderManifest,
    LazyTableRowSpec,
    iter_tiff_paths,
)
from phage_annotator.ui_qt.models.lazy_loader_split2 import normalize_lazy_sync_groups
LAZY_LOADER_FILE_FILTER = "TIFF Images (*.tif *.tiff *.ome.tiff)"
LAZY_LOADER_TREE_HEADER = "Loaded Files / Folders"
LAZY_LOADER_OPEN_FILES_TITLE = "Open Image Files"
LAZY_LOADER_OPEN_FOLDER_TITLE = "Open Folder"

