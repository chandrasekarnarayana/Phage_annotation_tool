"""Extracted method group 16 for UiExtrasMixin."""

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



class LazyAnnotationsMixin:
    """Method group 16 extracted from UiExtrasMixin."""

    def _set_lazy_annotation_context_mode_for_panel(self, panel_key: str, mode: str) -> None:
        """Apply annotation ownership mode for one lazy-table row/panel."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        self.controller.set_annotation_context_mode_for_panel(panel_key, mode)
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        self._request_lazy_canvas_refresh("lazy-annotation-context", refresh_table=True)
        self._status_info("Annotation ownership updated.", source="ui_extra.lazy_loader")
    def _bind_lazy_annotation_file_for_panel(self, panel_key: str) -> None:
        """Bind or rebind one lazy-row annotation context to a file."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        default_path = self._default_annotation_binding_path_for_panel(panel_key)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Annotation File",
            str(default_path),
            "Annotation Files (*.json *.csv)",
        )
        if not path:
            return
        selected = Path(path)
        suffix = selected.suffix.lower()
        fmt = "json" if suffix == ".json" else "csv" if suffix == ".csv" else "other"
        self.controller.bind_annotation_file_to_panel(
            panel_key,
            str(selected),
            fmt=fmt,
            mtime=selected.stat().st_mtime if selected.exists() else None,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._refresh_lazy_modality_table()
        self._status_success("Annotation file binding updated.", source="ui_extra.lazy_loader")
        
        logger = get_action_logger()
        logger.log_action(
            "bind_annotation_file",
            panel="lazy_loader",
            details={"panel_key": panel_key, "file": str(selected), "format": fmt}
        )
    def _load_lazy_annotation_binding_for_panel(self, panel_key: str) -> None:
        """Load annotations from the bound file for one lazy-table row/panel."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        binding = self.controller.annotation_binding_for_panel(panel_key)
        path = str(binding.get("path", "") or "")
        if not path:
            return
        file_path = Path(path)
        if not file_path.exists():
            self._status_warning("Bound annotation file is missing.", source="ui_extra.lazy_loader")
            get_action_logger().log_action(
                "load_annotation_binding",
                panel="lazy_loader",
                details={"panel_key": panel_key, "file": str(file_path)},
                error="File not found"
            )
            return
        context = self.controller.ensure_annotation_context_for_panel(panel_key, writable=True)
        source_image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", 0)))
        cal = self._get_calibration_state(source_image_id)
        pixel_size_nm = cal.pixel_size_um_per_px * 1000.0 if cal.pixel_size_um_per_px else None
        try:
            points, imports = self.controller._parse_annotations_from_paths(
                [file_path],
                image_id=source_image_id,
                pixel_size_nm=pixel_size_nm,
                force_image_id=source_image_id,
                context_panel_key=panel_key,
            )
        except Exception as exc:
            self._status_error(f"Could not load bound annotations: {exc}", source="ui_extra.lazy_loader")
            get_action_logger().log_action(
                "load_annotation_binding",
                panel="lazy_loader",
                details={"panel_key": panel_key, "file": str(file_path)},
                error=str(exc)
            )
            return
        self.controller._record_annotation_imports(imports)
        self.controller.replace_annotations(source_image_id, points)
        self.controller.bind_annotation_file_to_panel(
            panel_key,
            str(file_path),
            fmt=str(binding.get("format", "other")),
            mtime=file_path.stat().st_mtime if file_path.exists() else None,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._request_ui_refresh("lazy-binding-load", table=True, image=True, status=True)
        self._status_success("Loaded bound annotations.", source="ui_extra.lazy_loader")
        get_action_logger().log_action(
            "load_annotation_binding",
            panel="lazy_loader",
            details={"panel_key": panel_key, "file": str(file_path), "point_count": len(points)}
        )
    def _clear_lazy_annotation_binding_for_panel(self, panel_key: str) -> None:
        """Clear the bound annotation file for one lazy-table row/panel."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        self.controller.clear_annotation_binding_for_panel(
            panel_key,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
        self._refresh_lazy_modality_table()
        self._status_info("Annotation file binding cleared.", source="ui_extra.lazy_loader")
