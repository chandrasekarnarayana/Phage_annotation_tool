"""Workspace, recent-file, and annotation-load actions."""

from __future__ import annotations

from phage_annotator.ui_qt.actions.workspace_recent_files import WorkspaceRecentFilesMixin
from phage_annotator.ui_qt.actions.workspace_file_loader import WorkspaceFileLoaderMixin
from phage_annotator.ui_qt.actions.workspace_metadata_handler import WorkspaceMetadataHandlerMixin


class WorkspaceActionsMixin(
    WorkspaceRecentFilesMixin,
    WorkspaceFileLoaderMixin,
    WorkspaceMetadataHandlerMixin,
):
    """Aggregated mixin for workspace I/O, recent files, and annotation loading."""
    pass
