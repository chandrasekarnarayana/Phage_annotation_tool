"""Extracted method group 15 for UiExtrasMixin."""

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



class ExtrasLazyTableMixin:
    """Method group 15 extracted from UiExtrasMixin."""

    def _lazy_table_row_specs(self, manager) -> list[LazyTableRowSpec]:
        """Return the complete lazy-table row set from current state.

        This is the single derived source for the loader table. File/folder
        membership comes from the lazy loader manifest, while panel behavior
        comes from controller modality state plus explicit UI/runtime flags.
        """
        specs: list[LazyTableRowSpec] = []
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        hidden_base = set(getattr(self, "_lazy_hidden_base_panel_keys", set()) or set())
        panel_visibility = dict(getattr(self, "_panel_visibility", {}) or {})
        point_visibility = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        groups = self._lazy_sync_groups_state()
        source_images = list(self._lazy_loader_source_images())
        available_ids = {int(getattr(img, "id", -1)) for img in source_images}
        fallback_source_id = int(getattr(getattr(self, "primary_image", None), "id", 0))

        def _normalize_source_id(candidate: object) -> int:
            """Normalize source id for the current workflow."""
            try:
                value = int(candidate)
            except Exception:
                value = fallback_source_id
            if available_ids and value not in available_ids:
                return fallback_source_id if fallback_source_id in available_ids else int(next(iter(available_ids)))
            return value

        for modality in manager.get_all_modalities():
            panel_key = self._panel_key_for_modality_idx(int(modality.idx))
            if panel_key in hidden_base and int(modality.idx) <= 1:
                # Only hide true legacy base rows. If the manager starts empty
                # and users add modalities manually, idx 0/1 are user-created
                # rows and must remain visible/populated in the lazy table.
                legacy_names = {"primary", "support", "frame", "stack"}
                name_norm = str(getattr(modality, "display_name", "")).strip().lower()
                if name_norm in legacy_names:
                    continue
            context = self.controller.ensure_annotation_context_for_panel(panel_key, writable=True)
            binding = self.controller.annotation_binding_for_panel(panel_key)
            panel_name = str(getattr(modality, "display_name", "")).strip() or f"Modality {int(modality.idx) + 1}"
            specs.append(
                LazyTableRowSpec(
                    role_key=int(modality.idx),
                    panel_key=panel_key,
                    panel_name=panel_name,
                    source_image_id=_normalize_source_id(getattr(modality, "image_id", fallback_source_id)),
                    projection_key=str(modality.projection_type.value),
                    group_key=str(groups.get(int(modality.idx), "")),
                    visible=bool(panel_visibility.get(panel_key, True)),
                    show_points=bool(point_visibility.get(panel_key, True)),
                    sync_contrast=bool(self._sync_modes_for_role(int(modality.idx)).get("contrast", True)),
                    sync_view=bool(self._sync_modes_for_role(int(modality.idx)).get("zoom", True)),
                    sync_time=bool(self._sync_modes_for_role(int(modality.idx)).get("playback", True)),
                    annotation_mode=str(context.get("mode", "independent")),
                    annotation_writable=bool(context.get("writable", True)),
                    annotation_context_key=str(context.get("context_key", "")),
                    annotation_binding_path=str(binding.get("path", "")),
                )
            )
        has_support = any(spec.panel_key == "support" for spec in specs)
        _ = has_support  # kept for readability around built-in panel handling below
        for panel_key in ("mean", "std"):
            if panel_key not in builtin:
                continue
            cfg = dict(builtin.get(panel_key, {}) or {})
            panel_name = str(cfg.get("name", "")).strip() or f"{panel_key.title()} Projection"
            projection_key = str(cfg.get("projection", panel_key)).strip().lower() or panel_key
            specs.append(
                LazyTableRowSpec(
                    role_key=f"builtin:{panel_key}",
                    panel_key=panel_key,
                    panel_name=panel_name,
                    source_image_id=_normalize_source_id(cfg.get("image_id", fallback_source_id)),
                    projection_key=projection_key,
                    group_key=str(groups.get(f"builtin:{panel_key}", "")),
                    visible=bool(panel_visibility.get(panel_key, True)),
                    show_points=bool(point_visibility.get(panel_key, True)),
                    sync_contrast=bool(self._sync_modes_for_role(f"builtin:{panel_key}").get("contrast", True)),
                    sync_view=bool(self._sync_modes_for_role(f"builtin:{panel_key}").get("zoom", True)),
                    sync_time=bool(self._sync_modes_for_role(f"builtin:{panel_key}").get("playback", True)),
                    annotation_mode=str(self.controller.ensure_annotation_context_for_panel(panel_key, writable=True).get("mode", "independent")),
                    annotation_writable=bool(self.controller.ensure_annotation_context_for_panel(panel_key, writable=True).get("writable", True)),
                    annotation_context_key=str(self.controller.ensure_annotation_context_for_panel(panel_key, writable=True).get("context_key", "")),
                    annotation_binding_path=str(self.controller.annotation_binding_for_panel(panel_key).get("path", "")),
                )
            )
        return specs
    def _image_index_for_id(self, image_id: int) -> int:
        """Return the current image-list index for an image id.

        Lazy-table source selectors use stable image ids as their row state,
        while display/runtime code still works with image-list indices.
        This keeps the table source-of-truth on image ids and only adapts at
        the display-control boundary when needed.
        """
        want = int(image_id)
        for idx, image in enumerate(getattr(self, "images", []) or []):
            if int(getattr(image, "id", -1)) == want:
                return int(idx)
        return 0
    def _centered_lazy_checkbox(self, table, *, checked: bool, tooltip: str, on_toggled):
        """Create a centered checkbox cell for the lazy table."""
        container = QtWidgets.QWidget(table)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        checkbox = QtWidgets.QCheckBox(container)
        checkbox.setChecked(bool(checked))
        checkbox.setToolTip(str(tooltip))
        checkbox.toggled.connect(on_toggled)
        layout.addWidget(checkbox)
        container._checkbox = checkbox  # type: ignore[attr-defined]
        return container
    def _lazy_checkbox_from_cell(self, widget):
        """Return the actual checkbox stored inside a centered checkbox cell."""
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget
        return getattr(widget, "_checkbox", None)
    def _default_annotation_binding_path_for_panel(self, panel_key: str) -> Path:
        """Return a default annotation filename for one selected lazy-row panel."""
        binding = self.controller.annotation_binding_for_panel(panel_key)
        if binding.get("path"):
            return Path(str(binding["path"]))
        context = self.controller.ensure_annotation_context_for_panel(panel_key, writable=True)
        source_image_id = int(context.get("source_image_id", getattr(self.primary_image, "id", 0)))
        source_image = next(
            (
                img for img in getattr(self, "images", [])
                if int(getattr(img, "id", -1)) == source_image_id
            ),
            self.primary_image,
        )
        source_path = Path(str(getattr(source_image, "path", self.primary_image.path)))
        suffix = str(context.get("panel_key", panel_key)).strip().lower() or "frame"
        return source_path.with_name(f"{source_path.stem}.{suffix}.annotations.json")
    def _auto_detect_annotation_path_for_image(self, image_id: int) -> str:
        """Return the first discovered annotation path for an image, if any."""
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "annotation_entries_for_image"):
            return ""
        entries = list(controller.annotation_entries_for_image(int(image_id)) or [])
        if not entries:
            image = next(
                (
                    img for img in getattr(self, "images", [])
                    if int(getattr(img, "id", -1)) == int(image_id)
                ),
                None,
            )
            if image is not None and hasattr(controller, "build_annotation_index"):
                try:
                    controller.build_annotation_index(Path(str(getattr(image, "path", ""))).parent)
                except Exception:
                    pass
                entries = list(controller.annotation_entries_for_image(int(image_id)) or [])
        if not entries:
            return ""
        return str(getattr(entries[0], "path", "") or "")
    def _auto_bind_detected_annotation_for_panel(self, panel_key: str, source_image_id: int) -> None:
        """Bind the first discovered annotation file for a panel when available."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        existing = dict(self.controller.annotation_binding_for_panel(panel_key) or {})
        if str(existing.get("path", "")).strip():
            return
        detected_path = self._auto_detect_annotation_path_for_image(int(source_image_id))
        if not detected_path:
            self._fallback_share_annotation_binding_for_panel(panel_key, source_image_id)
            return
        detected = Path(detected_path)
        suffix = detected.suffix.lower()
        fmt = "json" if suffix == ".json" else "csv" if suffix == ".csv" else "other"
        self.controller.bind_annotation_file_to_panel(
            panel_key,
            str(detected),
            fmt=fmt,
            mtime=detected.stat().st_mtime if detected.exists() else None,
            annotation_space=str(getattr(self.controller.session_state, "annotation_space", "stack")),
        )
    def _fallback_share_annotation_binding_for_panel(self, panel_key: str, source_image_id: int) -> None:
        """Share an existing annotation binding when a new modality has none."""
        if not panel_key or getattr(self, "controller", None) is None:
            return
        controller = self.controller
        source_id = int(source_image_id)
        current_space = str(getattr(controller.session_state, "annotation_space", "stack")).strip().lower()

        # Default new modality contexts to shared ownership when no dedicated file was detected.
        controller.set_annotation_context_mode_for_panel(panel_key, "shared_source")

        bindings = dict(getattr(controller.session_state, "annotation_file_bindings", {}) or {})
        inherited = {}
        for binding in bindings.values():
            candidate = dict(binding or {})
            if int(candidate.get("source_image_id", -1)) != source_id:
                continue
            if str(candidate.get("annotation_space", "")).strip().lower() != current_space:
                continue
            if not str(candidate.get("path", "")).strip():
                continue
            inherited = candidate
            break
        if not inherited:
            return

        path = str(inherited.get("path", "")).strip()
        fmt = str(inherited.get("format", "") or "").strip().lower() or "other"
        if fmt not in {"json", "csv", "other"}:
            suffix = Path(path).suffix.lower()
            fmt = "json" if suffix == ".json" else "csv" if suffix == ".csv" else "other"
        mtime_value = inherited.get("mtime", None)
        try:
            mtime = float(mtime_value) if mtime_value is not None else None
        except Exception:
            mtime = None

        controller.bind_annotation_file_to_panel(
            panel_key,
            path,
            fmt=fmt,
            mtime=mtime,
            annotation_space=current_space,
        )
