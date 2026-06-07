"""Extracted method group 5 for ExportMixin."""

from __future__ import annotations

import base64
import pathlib
import re
from datetime import datetime
from typing import Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.core import compute_projection
from phage_annotator.core.workspace_snapshot import (
    build_workspace_snapshot,
    extract_ui_workspace_state,
    workspace_layer_registry,
)
from phage_annotator.io.metadata.annotation import format_tokens
from phage_annotator.data.display_mapping import build_norm
from phage_annotator.ui_qt.rendering.export_view import (
    ExportOptions, render_view_to_array, render_layer_to_array,
    render_chunk_to_array, calculate_export_chunks, create_streaming_writer
)
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import cmap_for
from phage_annotator.rendering.scalebar import ScaleBarSpec




class ExportMixinRelinkMixin:
    """Method group 5 extracted from ExportMixin."""

    def _show_project_relink_summary_panel(self, project_path: pathlib.Path) -> None:
        """Update/open persistent Project Relink panel after load."""
        report = dict(getattr(self.controller.session_state, "project_relink_report", {}) or {})
        if not report:
            return
        relinked = list(report.get("relinked", []) or [])
        unresolved = list(report.get("unresolved", []) or [])
        if not relinked and not unresolved:
            return
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
        self.open_panel("advanced_settings", reason="project_relink:load")
        self._status_warning(
            f"Project relink summary: {len(relinked)} relinked, {len(unresolved)} unresolved.",
            timeout_ms=5000,
            source="export.project_relink_summary",
        )
    def _retry_project_relink(self, mode: str) -> None:
        """Retry project load with explicit relink mode."""
        path = getattr(self, "_last_loaded_project_path", None)
        if path is None:
            self._status_warning("No loaded project to relink.", source="export.retry_project_relink")
            return
        mode_value = str(mode or "ask").strip().lower()
        if mode_value not in {"ask", "auto", "manual"}:
            mode_value = "ask"
        ok = self._load_project_path(pathlib.Path(path), relink_mode=mode_value)
        if ok:
            self._status_success(
                "Project reloaded after "
                + ("manual relink." if mode_value == "manual" else "auto relink retry."),
                source="export.retry_project_relink",
            )
